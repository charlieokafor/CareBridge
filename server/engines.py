"""Speech and language engines. Everything runs on our own server inside the hospital's AWS account:
- Speech to text + language detection: faster-whisper (OpenAI Whisper, int8 on CPU)
- Translation: Meta NLLB-200 (distilled) via CTranslate2, int8
- Meaning check: multilingual MiniLM sentence embeddings (cosine similarity)
- Voices: Piper (optional; the app falls back to the device's own voice)

CB_ENGINE=mock gives fast stand-ins so the interface can be developed on a laptop."""
import io
import math
import os
import re
import threading
import time
import wave

from .audio_clean import clean_speech
from .phrasebank import LANGUAGES, WHISPER_MODEL_LANG, WHISPER_TO_CODE

MODELS = os.environ.get("CB_MODELS", "/opt/carebridge/models")
WHISPER_SIZE = os.environ.get("CB_WHISPER", "small")
WHISPER_EN = os.environ.get("CB_WHISPER_EN", "base")
NLLB_DIR = os.environ.get("CB_NLLB", "nllb-600m")
NLLB_TOKENIZER = os.environ.get("CB_NLLB_TOKENIZER", "facebook/nllb-200-distilled-600M")
# Natural voices (Piper) where one exists; Meta MMS-TTS covers the other languages, so every licensed
# language always has a server voice.
VOICES = {
    "uk": "uk_UA-ukrainian_tts-medium", "ru": "ru_RU-irina-medium", "pl": "pl_PL-gosia-medium",
    "ro": "ro_RO-mihai-medium", "ar": "ar_JO-kareem-medium", "en": "en_GB-alba-medium",
    "fr": "fr_FR-siwis-medium", "es": "es_ES-davefx-medium", "de": "de_DE-thorsten-medium",
    "it": "it_IT-paola-medium", "pt": "pt_BR-faber-medium", "sk": "sk_SK-lili-medium",
    "hu": "hu_HU-anna-medium", "tr": "tr_TR-dfki-medium", "vi": "vi_VN-vais1000-medium",
    "sw": "sw_CD-lanfrica-medium", "el": "el_GR-rapunzelina-low", "cs": "cs_CZ-jirka-medium",
}
MMS = {"ga": "gle", "ko": "kor", "ur": "urd-script_arabic", "bn": "ben", "pa": "pan", "ps": "pbu", "so": "som",
       "ig": "ibo", "sq": "sqi", "lt": "lit", "tl": "tgl", "bg": "bul", "hi": "hin", "hu": "hun", "sk": "slk",
       "tr": "tur", "vi": "vie", "sw": "swh", "fr": "fra", "es": "spa", "de": "deu", "it": "ita", "pt": "por",
       "id": "ind", "el": "ell", "cs": "ces", "uk": "ukr", "ru": "rus", "pl": "pol", "ro": "ron", "ar": "ara", "en": "eng"}
PRELOAD = ("en", "uk", "ru", "pl", "ro", "ar")
MAX_EXTRA_VOICES = 4


def _loud(wav_bytes):
    """Normalise to near full scale (at most 4x gain) and add 150 ms of silence in front, so phones in a noisy
    room play it loudly and do not clip the first word while the audio route switches."""
    import numpy as np
    with wave.open(io.BytesIO(wav_bytes)) as r:
        params, frames = r.getparams(), r.readframes(r.getnframes())
    a = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
    peak = float(np.abs(a).max()) if a.size else 0.0
    if peak > 0:
        a = np.clip(a * min(4.0, 0.97 * 32767 / peak), -32767, 32767)
    pad = np.zeros(int(params.framerate * 0.15) * params.nchannels, dtype=np.float32)
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(params.nchannels); w.setsampwidth(2); w.setframerate(params.framerate)
        w.writeframes(np.concatenate([pad, a]).astype(np.int16).tobytes())
    return out.getvalue()
# Language groups the detector confuses on short phrases
CONFUSABLE = [{"uk", "ru", "bg"}, {"hi", "ur", "pa"}, {"es", "pt", "it"}, {"sk", "pl"}]
CLINICAL_PROMPT = ("Hospital conversation in Ireland. Paracetamol, ibuprofen, penicillin, cannula, "
                   "nil by mouth, blood pressure, allergy, consent, X-ray.")


# Noise clean-up before recognition: OFF by default. Every filter tested made recognition worse, and this one
# turned "every six hours" into "86 hours" (eval/aws_compare, Oct 2026; also arXiv 2512.17562, 2603.04710).
CLEAN_AUDIO = os.environ.get("CB_CLEAN", "0") == "1"
CLARITY_UNCLEAR, CLARITY_NOISY = 0.25, 0.5             # below: not translated / translated but not spoken unchecked
CLARITY_NOISY_GUESSED = 0.57                           # the same, when the language was detected rather than given
CLOSEST_VOICE_DB = 10.0                                # sentences this much quieter than the speaker are dropped
_PROMPT_WORDS = set(re.findall(r"[a-z]+", CLINICAL_PROMPT.lower())) - {"in", "by", "x"}


def _real_speech(seg, lang):
    """False for text the model made up from noise: segments it thinks are not speech, stuck repetition, and the
    clinical hint list echoed back ("ibuprofen, penicillin, cannula, nil by mouth...")."""
    if seg.no_speech_prob > 0.6 and seg.avg_logprob < -1.0:
        return False
    if seg.compression_ratio > 2.4:
        return False
    if lang == "en":
        words = re.findall(r"[a-z]+", seg.text.lower())
        if len(words) >= 3 and sum(w in _PROMPT_WORDS for w in words) / len(words) >= 0.5:
            return False
    return True


def _closest_voice(segs, audio):
    """Keeps the sentences spoken by the closest (loudest) voice. A sentence much quieter than that is someone
    else in the room, e.g. staff talking behind the patient just before they speak."""
    if len(segs) < 2:
        return segs
    levels = []
    for s in segs:
        a = audio[int(s.start * 16000): max(int(s.start * 16000) + 1, int(s.end * 16000))]
        levels.append(10 * math.log10(float((a.astype("float64") ** 2).mean()) + 1e-12))
    top = max(levels)
    return [s for s, lv in zip(segs, levels) if lv >= top - CLOSEST_VOICE_DB]


def _split_sentences(text: str):
    parts = re.split(r"(?<=[.!?؟])\s+", text.strip())
    return [p for p in parts if p]


class RealEngines:
    name = "self-hosted"

    def __init__(self):
        self.status = {"speech": "loading", "translation": "loading", "meaning": "loading", "voice": "loading"}
        self.info = {"speech": f"Whisper {WHISPER_SIZE}", "translation": f"NLLB-200 ({NLLB_DIR})",
                     "meaning": "MiniLM multilingual", "voice": "Piper"}
        self._asr_lock, self._mt_lock, self._st_lock, self._tts_lock = (threading.Lock() for _ in range(4))
        self._voices = {}
        from collections import OrderedDict
        self._voice_order = OrderedDict()
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            import ctranslate2
            from transformers import AutoTokenizer
            # Both NLLB sizes stay loaded; each language uses the one that scored best in our evaluation.
            self.translators = {}
            for size in ("600m", "1.3b"):
                path = os.path.join(MODELS, f"nllb-{size}")
                if os.path.exists(os.path.join(path, "model.bin")):
                    self.translators[size] = ctranslate2.Translator(path, device="cpu", compute_type="int8", intra_threads=2)
            self.tokenizer = AutoTokenizer.from_pretrained(NLLB_TOKENIZER)   # NLLB-200 sizes share one tokenizer
            self.info["translation"] = "NLLB-200 (" + " + ".join(self.translators) + ", chosen per language)"
            self.status["translation"] = "ready"
        except Exception as e:  # noqa: BLE001
            self.status["translation"] = f"error: {e}"
        try:
            from faster_whisper import WhisperModel
            self.whisper = WhisperModel(WHISPER_SIZE, device="cpu", compute_type="int8", cpu_threads=2,
                                        download_root=os.path.join(MODELS, "whisper"))
            # A lighter model for clinicians' English keeps turns fast; patients' languages use the larger one.
            self.whisper_en = WhisperModel(WHISPER_EN, device="cpu", compute_type="int8", cpu_threads=2,
                                           download_root=os.path.join(MODELS, "whisper"))
            self.info["speech"] = f"Whisper {WHISPER_SIZE} + {WHISPER_EN} (English)"
            self.status["speech"] = "ready"
        except Exception as e:  # noqa: BLE001
            self.status["speech"] = f"error: {e}"
        try:
            from sentence_transformers import SentenceTransformer
            self.st = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", device="cpu")
            self.status["meaning"] = "ready"
        except Exception as e:  # noqa: BLE001
            self.status["meaning"] = f"error: {e}"
        try:
            for lang in PRELOAD:
                self._voice(lang)
            n = len(self.voice_langs())
            self.status["voice"] = "ready" if n else "device voices"
            self.info["voice"] = f"Piper + MMS-TTS ({n} languages)"
        except Exception as e:  # noqa: BLE001
            self.status["voice"] = "device voices"
            self.info["voice"] = f"device voices ({type(e).__name__})"
        # Warm-up so the first real request is fast
        try:
            import numpy as np
            self.translate("Hello.", "en", "uk")
            self.translate("Привіт.", "uk", "en")
            self.similarity("Hello.", "Hi.")
            for m in (self.whisper, self.whisper_en):
                list(m.transcribe(np.zeros(16000, dtype=np.float32), language="en", beam_size=1)[0])
        except Exception:  # noqa: BLE001
            pass

    def ready(self):
        return all(self.status[k] == "ready" for k in ("speech", "translation", "meaning"))

    # -- speech to text -------------------------------------------------------------------------
    def _recognise(self, model, lang, audio):
        """Transcribes in one language. Returns (average log-probability per token, kept segments): the higher
        the log-probability, the more natural the model finds the text in that language."""
        segs = list(model.transcribe(audio, language=WHISPER_MODEL_LANG.get(lang, LANGUAGES[lang]["whisper"]),
                                     initial_prompt=CLINICAL_PROMPT if lang == "en" else None,
                                     beam_size=1, vad_filter=True, condition_on_previous_text=False,
                                     # No retries and a cap on length: in loud noise the model otherwise keeps
                                     # producing junk until the gateway's 30-second limit; junk is caught by
                                     # _real_speech and the clarity score anyway. 20 s of speech is ~80 tokens.
                                     temperature=0.0, max_new_tokens=160)[0])
        segs = _closest_voice([s for s in segs if _real_speech(s, lang)], audio)
        n = sum(len(s.tokens) for s in segs)
        return (sum(s.avg_logprob * len(s.tokens) for s in segs) / n if n else -5.0), segs

    def transcribe(self, data: bytes, lang=None, candidates=None):
        from faster_whisper.audio import decode_audio
        audio = decode_audio(io.BytesIO(data), sampling_rate=16000)
        duration = len(audio) / 16000
        cleaning, guessed = {}, not lang   # guessed: the language was detected, not given by a speaker button
        if CLEAN_AUDIO:
            audio, cleaning = clean_speech(audio)
        confidence, detected, method = None, None, None
        with self._asr_lock:
            if not lang:
                # Fast language detection with the light model, among the languages we support.
                cands = [c for c in (candidates or list(LANGUAGES)) if LANGUAGES.get(c, {}).get("whisper")]

                def detect(model):
                    _, _, all_probs = model.detect_language(audio)
                    p = {WHISPER_TO_CODE[w]: v for w, v in all_probs if w in WHISPER_TO_CODE}
                    tot = sum(p.get(c, 0.0) for c in cands) or 1.0
                    best = max(cands, key=lambda c: p.get(c, 0.0))
                    return p, tot, best, p.get(best, 0.0) / tot

                probs, total, lang, conf = detect(self.whisper_en)
                if conf < 0.85:   # not sure: the larger model is slower but far better at telling languages apart
                    probs, total, lang, conf = detect(self.whisper)
                confidence = round(conf, 3)
                detected = {c: round(probs.get(c, 0.0) / total, 3) for c in cands if probs.get(c, 0.0) / total >= 0.01}
                # The detector is fooled by close languages (Ukrainian and Russian) and by background chatter in
                # another language (English voices behind a Ukrainian patient). When it is unsure, or the runner-up
                # is a close language, transcribe in both and keep the one the model finds more natural.
                ranked = sorted(cands, key=lambda c: -probs.get(c, 0.0))
                partner = next((c for c in ranked[1:] if probs.get(c, 0.0) / total >= 0.01
                                and any(lang in g and c in g for g in CONFUSABLE)), None)
                if partner is None and conf < 0.9 and len(ranked) > 1:
                    partner = ranked[1]
                if partner:
                    tried = {c: self._recognise(self.whisper, c, audio) for c in (lang, partner)}
                    (lang, (lp1, segs)), (_, (lp2, _)) = sorted(tried.items(), key=lambda kv: -kv[1][0])
                    confidence = round(1 / (1 + math.exp(-(lp1 - lp2) * 30)), 3)
                    detected[lang] = max(detected.get(lang, 0.0), confidence)
                    method = "two-language check"
            if method is None:
                model = self.whisper_en if lang == "en" else self.whisper
                lp1, segs = self._recognise(model, lang, audio)
        text = " ".join(s.text.strip() for s in segs).strip()
        clarity = round(min(1.0, max(0.0, 1 + lp1)), 2)
        # Measured on recordings with emergency-department noise (eval/noise_bench_*.py): correct transcripts
        # scored 0.59 or more, background chatter transcribed by mistake scored under 0.25. When the language had to
        # be guessed, a bystander speaking another language can win the guess (it scored 0.53-0.55), so a guess
        # needs a higher score before it is trusted.
        noisy_below = CLARITY_NOISY_GUESSED if guessed else CLARITY_NOISY
        out = {"text": text, "lang": lang, "langConfidence": confidence, "langScores": detected,
               "uncertain": ((confidence is not None and confidence < 0.6)
                             or (guessed and bool(text) and clarity < noisy_below)),
               "noSpeech": not text, "duration": round(duration, 2), "asrConfidence": clarity,
               "clarity": "unclear" if not text or clarity < CLARITY_UNCLEAR else "noisy" if clarity < noisy_below else "clear"}
        if method:
            out["method"] = method
        if cleaning.get("cleaned"):
            out["cleaned"] = cleaning
        return out

    # -- translation --------------------------------------------------------------------------------
    def _model(self, src, tgt):
        lang = tgt if src == "en" else src
        size = LANGUAGES.get(lang, {}).get("model", "600m")
        return size if size in self.translators else next(iter(self.translators))

    def model_label(self, src, tgt):
        return f"NLLB-200 {self._model(src, tgt).upper()}"

    def translate(self, text: str, src: str, tgt: str):
        sents = _split_sentences(text) or [text]
        with self._mt_lock:
            self.tokenizer.src_lang = LANGUAGES[src]["nllb"]
            batch = [self.tokenizer.convert_ids_to_tokens(self.tokenizer.encode(s)) for s in sents]
            results = self.translators[self._model(src, tgt)].translate_batch(
                batch, target_prefix=[[LANGUAGES[tgt]["nllb"]]] * len(batch), beam_size=2,
                max_decoding_length=256, repetition_penalty=1.1)
            out = [self.tokenizer.decode(self.tokenizer.convert_tokens_to_ids(r.hypotheses[0][1:]),
                                         skip_special_tokens=True) for r in results]
        return " ".join(o.strip() for o in out)

    def translate_many(self, texts, src: str, tgt: str):
        """Translates a list of short texts in one batch (used to build interface text)."""
        with self._mt_lock:
            self.tokenizer.src_lang = LANGUAGES[src]["nllb"]
            batch = [self.tokenizer.convert_ids_to_tokens(self.tokenizer.encode(t)) for t in texts]
            results = self.translators[self._model(src, tgt)].translate_batch(
                batch, target_prefix=[[LANGUAGES[tgt]["nllb"]]] * len(batch), beam_size=4,
                max_decoding_length=256, repetition_penalty=1.1)
            return [self.tokenizer.decode(self.tokenizer.convert_tokens_to_ids(r.hypotheses[0][1:]),
                                          skip_special_tokens=True).strip() for r in results]

    # -- meaning check ------------------------------------------------------------------------------
    def similarity(self, a: str, b: str):
        with self._st_lock:
            emb = self.st.encode([a, b], normalize_embeddings=True)
        return float((emb[0] * emb[1]).sum())

    # -- voice --------------------------------------------------------------------------------------
    def _piper_path(self, lang):
        v = VOICES.get(lang)
        path = os.path.join(MODELS, "voices", f"{v}.onnx") if v else None
        return path if path and os.path.exists(path) and os.path.getsize(path) > 1000 else None

    def _mms_path(self, lang):
        path = os.path.join(MODELS, "mms", lang)
        return path if os.path.exists(os.path.join(path, "config.json")) else None

    def voice_langs(self):
        return sorted(l for l in set(VOICES) | set(MMS) if self._piper_path(l) or self._mms_path(l))

    def _voice(self, lang):
        """Loads (once) and returns ("piper", voice) or ("mms", (model, tokenizer, uroman)) or None.
        The pilot-language voices stay loaded; at most MAX_EXTRA_VOICES others, least recently used first out,
        so memory stays bounded on the 8 GB server."""
        if lang in self._voices:
            self._voice_order.pop(lang, None)
            self._voice_order[lang] = True
            return self._voices[lang]
        extra = [l for l in self._voice_order if l not in PRELOAD]
        while len(extra) >= MAX_EXTRA_VOICES:
            old = extra.pop(0)
            self._voices.pop(old, None)
            self._voice_order.pop(old, None)
            import ctypes
            import gc
            gc.collect()
            try:
                ctypes.CDLL("libc.so.6").malloc_trim(0)   # give freed memory back to the system
            except OSError:
                pass
        found = None
        if self._piper_path(lang):
            from piper.voice import PiperVoice
            path = self._piper_path(lang)
            found = ("piper", PiperVoice.load(path, config_path=path + ".json"))
        elif self._mms_path(lang):
            from transformers import AutoTokenizer, VitsModel
            path = self._mms_path(lang)
            tok = AutoTokenizer.from_pretrained(path)
            rom = None
            if getattr(tok, "is_uroman", False):
                import uroman
                rom = uroman.Uroman()
            found = ("mms", (VitsModel.from_pretrained(path).eval(), tok, rom))
        self._voices[lang] = found
        self._voice_order[lang] = True
        return found

    def warm(self, lang):
        threading.Thread(target=lambda: self._voice(lang), daemon=True).start()

    def tts(self, text: str, lang: str):
        with self._tts_lock:
            try:
                v = self._voice(lang)
            except Exception:  # noqa: BLE001  - a voice that will not load means "no server voice", never an error
                self._voices[lang] = v = None
            if not v:
                return None
            kind, obj = v
            if kind == "piper":
                buf = io.BytesIO()
                with wave.open(buf, "wb") as wf:
                    obj.synthesize(text, wf)
                return _loud(buf.getvalue())
            import numpy as np
            import torch
            model, tok, rom = obj
            inputs = tok(rom.romanize_string(text) if rom else text, return_tensors="pt")
            with torch.no_grad():
                audio = model(**inputs).waveform[0].numpy()
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(model.config.sampling_rate)
                wf.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
            return _loud(buf.getvalue())


class MockEngines:
    """Instant stand-ins for interface development (no models)."""
    name = "mock"

    def __init__(self):
        self.status = {"speech": "ready", "translation": "ready", "meaning": "ready", "voice": "device voices"}
        self.info = {"speech": "mock", "translation": "mock", "meaning": "mock", "voice": "device voices"}

    def ready(self):
        return True

    def transcribe(self, data, lang=None, candidates=None):
        time.sleep(0.4)
        if lang in (None, "uk") and len(data) > 60000:
            return {"text": "Так, у мене болить живіт з правого боку. У мене алергія на пеніцилін.", "lang": "uk",
                    "langConfidence": 0.94, "langScores": {"uk": 0.94, "ru": 0.05}, "duration": 4.2, "asrConfidence": 0.9,
                    "noSpeech": False, "clarity": "clear"}
        return {"text": "Is the pain at you? Have you had anything to eat or drink since midnight?", "lang": lang or "en",
                "langConfidence": 0.98, "langScores": {"en": 0.98}, "duration": 3.1, "asrConfidence": 0.93, "noSpeech": False,
                "clarity": "clear"}

    def translate(self, text, src, tgt):
        time.sleep(0.2)
        if tgt == "en" and src == "uk":
            return "Yes, my stomach hurts on the right side. I'm allergic to penicillin."
        return f"[{tgt}] {text}"

    def translate_many(self, texts, src, tgt):
        return [f"[{tgt}] {t}" for t in texts]

    def model_label(self, src, tgt):
        return "mock"

    def similarity(self, a, b):
        return 0.91

    def tts(self, text, lang):
        return None

    def warm(self, lang):
        pass

    def voice_langs(self):
        return []


def load_engines():
    kind = os.environ.get("CB_ENGINE", "aws")
    if kind == "mock":
        return MockEngines()
    if kind == "aws":
        from .aws_engines import AwsEngines
        return AwsEngines()
    return RealEngines()
