"""CareBridge engines on AWS managed services, with the self-hosted models as automatic fallback.

Chosen by benchmark (eval/aws_compare, 19 Oct 2026):
  Speech     Amazon Transcribe real-time (streamed fast from the recorded turn) + CareBridge medical vocabulary.
             In emergency-department noise at 5 dB it got 22-28% of words wrong vs 67% for Whisper small.
  Language   first patient sentence, language unknown: Whisper-small's 6 likeliest languages + English transcribed
             in parallel; accepted only when Whisper and Transcribe agree, Transcribe's confidence >= 0.6, enough
             words were recognised and no second language fits almost as well (0 wrong out of 116 noisy clips and
             of 144 real-speaker clips in 18 languages; 68-72% decided automatically, the rest asked).
  Translate  Amazon Translate; the CareBridge medicine terminology only where it measurably helped.
  Voice      Amazon Polly neural voices where Dublin has one; Piper / MMS on the server otherwise.
  Meaning    multilingual MiniLM on the server (unchanged).
Any AWS failure falls back to the self-hosted model for that request, so the app keeps working."""
import asyncio
import io
import logging
import os
import re
import threading
import time
import wave
from concurrent.futures import ThreadPoolExecutor

from .engines import RealEngines, _loud
from .phrasebank import LANGUAGES

log = logging.getLogger("carebridge.aws")
REGION = os.environ.get("CB_AWS_REGION") or os.environ.get("AWS_REGION") or "eu-west-1"
# CareBridge language -> Amazon Transcribe locale (others are recognised by Whisper on the server)
TRANSCRIBE = {"en": "en-IE", "uk": "uk-UA", "ru": "ru-RU", "pl": "pl-PL", "ro": "ro-RO", "ar": "ar-SA",
              "fr": "fr-FR", "es": "es-ES", "de": "de-DE", "hi": "hi-IN", "ko": "ko-KR", "pt": "pt-BR",
              "it": "it-IT", "tr": "tr-TR", "zh": "zh-CN", "vi": "vi-VN", "bg": "bg-BG", "hu": "hu-HU",
              "sk": "sk-SK", "lt": "lt-LT", "lv": "lv-LV", "ka": "ka-GE", "sq": "sq-AL", "so": "so-SO",
              "sw": "sw-KE", "fa": "fa-IR", "prs": "fa-IR", "tl": "tl-PH", "bn": "bn-IN", "pa": "pa-IN",
              "id": "id-ID", "ja": "ja-JP", "ms": "ms-MY", "am": "am-ET", "cs": "cs-CZ", "el": "el-GR",
              "yue": "zh-HK"}
# Whisper (the language second opinion) cannot tell these apart: its answer counts for the whole family and
# Amazon Transcribe's confidence decides within it.
FAMILY = {"yue": "zh"}
VOCAB = {loc: f"carebridge-{loc}" for loc in ("en-IE", "uk-UA", "ru-RU", "pl-PL", "ro-RO", "ar-SA", "fr-FR",
                                               "es-ES", "de-DE", "hi-IN", "ko-KR", "pt-BR", "it-IT", "tr-TR",
                                               "vi-VN", "id-ID", "cs-CZ", "el-GR", "sw-KE", "tl-PH", "bn-IN",
                                               "zh-CN", "zh-HK", "ja-JP")}   # all READY (infra/build_vocab.py)
# Amazon Translate language codes that differ from ours
TRANSLATE_CODE = {"prs": "fa-AF", "ckb": None, "tl": "tl", "zh": "zh", "yue": "zh"}
# Cantonese is written in Hong Kong Traditional characters. Amazon's Traditional Chinese model failed the clinical
# screen (appendicitis -> nephritis, penicillin garbled); its Mandarin model + a character conversion (OpenCC s2hk /
# hk2s) got every term right and read colloquial Cantonese better (eval/aws_compare/results/clinical_screen.json).
_OPENCC = {}


def _chars(text, conv):
    if conv not in _OPENCC:
        import opencc
        _OPENCC[conv] = opencc.OpenCC(conv)
    return _OPENCC[conv].convert(text)
# Terminology helped in these languages and was neutral or worse elsewhere (eval/aws_compare terminology test)
TERMINOLOGY_LANGS = {"ur", "hi", "ko", "ga"}
POLLY = {"en": ("Niamh", "neural"), "ar": ("Hala", "neural"), "pl": ("Ola", "neural"), "fr": ("Lea", "neural"),
         "es": ("Lucia", "neural"), "de": ("Vicki", "neural"), "ko": ("Seoyeon", "neural"), "it": ("Bianca", "neural"),
         "pt": ("Camila", "neural"), "tr": ("Burcu", "neural"), "zh": ("Zhiyu", "neural"),
         "ja": ("Kazuha", "neural"), "cs": ("Jitka", "neural"), "yue": ("Hiujin", "neural")}
# Confidence tiers (mean word confidence), from the 355-clip benchmark: >= 0.8 -> 1.1% wrong
CONF_CLEAR, CONF_UNCLEAR = 0.80, 0.60
CRITICAL_WORD_CONF = 0.90     # a number or medicine heard below this -> the turn is checked before it is spoken
LANG_AGREE_CONF = 0.60
LANG_MIN_WORDS, LANG_MIN_WPS = 3, 0.4     # enough of the sentence recognised in the chosen language
LANG_MARGIN = 0.20                        # a second language that fits almost as well -> ask
# Only Whisper's 6 likeliest languages (+ English) are transcribed in parallel: as safe as all languages on the
# 116-clip test (0 wrong, same 72% automatic) and keeps a 23-language app within Transcribe's stream limit.
LANG_CHECK_TOP = 6
_NUM_RX = re.compile(r"\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|"
                     r"fifty|hundred|thousand|half|once|twice)\b", re.I)


def _pcm16(audio_f32):
    import numpy as np
    return (np.clip(audio_f32, -1, 1) * 32767).astype(np.int16).tobytes()


class AwsEngines:
    name = "aws"

    def __init__(self):
        self.local = RealEngines()          # Whisper (language detection + fallback), NLLB (fallback), MiniLM, voices
        import boto3
        self.translate_client = boto3.client("translate", region_name=REGION)
        self.polly = boto3.client("polly", region_name=REGION)
        self._pool = ThreadPoolExecutor(8)
        self.fallbacks = {"speech": 0, "translation": 0, "voice": 0}

    # status shown on /api/health and the admin screen
    @property
    def status(self):
        s = dict(self.local.status)
        s["speech"] = "ready" if s["speech"] == "ready" else s["speech"]   # Whisper is needed for language detection
        return s

    @property
    def info(self):
        i = dict(self.local.info)
        i.update({"speech": "Amazon Transcribe real-time + CareBridge vocabulary (Whisper: language check, fallback)",
                  "translation": "Amazon Translate (NLLB fallback)", "voice": "Amazon Polly neural + Piper/MMS"})
        return i

    def ready(self):
        return self.local.status["speech"] == "ready" and self.local.status["meaning"] == "ready"

    # -- speech ------------------------------------------------------------------------------------
    def _stream(self, pcm, lang):
        from .aws_transcribe import transcribe_pcm
        loc = TRANSCRIBE[lang]
        return transcribe_pcm(pcm, language_code=loc, vocabularies=VOCAB)

    def _parallel(self, pcm, langs):
        """Transcribe in several languages at once; {lang: result or None}."""
        futs = {l: self._pool.submit(self._stream, pcm, l) for l in langs}
        out = {}
        for l, f in futs.items():
            try:
                out[l] = f.result(timeout=25)
            except Exception as e:  # noqa: BLE001
                log.warning("transcribe %s failed: %s", l, e)
                out[l] = None
        return out

    def _whisper_detect(self, audio, cands):
        """Whisper-small's language probabilities among the candidates (the second opinion)."""
        from .phrasebank import WHISPER_TO_CODE
        with self.local._asr_lock:
            _, _, probs = self.local.whisper.detect_language(audio)
        p = {WHISPER_TO_CODE[w]: v for w, v in probs if w in WHISPER_TO_CODE and WHISPER_TO_CODE[w] in cands}
        for member, head in FAMILY.items():          # "Chinese" from Whisper -> Mandarin or Cantonese
            if member in cands and head in WHISPER_TO_CODE.values():
                hp = next((v for w, v in probs if WHISPER_TO_CODE.get(w) == head), 0.0)
                p[member] = max(p.get(member, 0.0), hp)
        tot = sum(p.values()) or 1.0
        return {k: v / tot for k, v in sorted(p.items(), key=lambda kv: -kv[1])}

    def transcribe(self, data: bytes, lang=None, candidates=None):
        from faster_whisper.audio import decode_audio
        audio = decode_audio(io.BytesIO(data), sampling_rate=16000)
        duration = len(audio) / 16000
        pcm = _pcm16(audio)
        t0 = time.time()
        try:
            if lang:
                if lang not in TRANSCRIBE:
                    return dict(self.local.transcribe(data, lang, candidates), engine="whisper")
                r = self._stream(pcm, lang)
                return self._result(r, lang, duration, guessed=False, t0=t0)
            cands = [c for c in (candidates or list(TRANSCRIBE)) if c in TRANSCRIBE] or ["en"]
            whisper = self._whisper_detect(audio, cands)
            top = list(dict.fromkeys([l for l in whisper if l in TRANSCRIBE][:LANG_CHECK_TOP] + ["en"]))
            results = self._parallel(pcm, [c for c in top if c in cands] or cands[:LANG_CHECK_TOP])
            conf = {l: (r["confidence"] or 0.0) if r and r["words"] else 0.0 for l, r in results.items()}
            ranked = sorted(conf, key=lambda l: -conf[l])
            best = ranked[0]
            if results.get(best) is None:
                raise RuntimeError("no Transcribe result")
            w_top = next(iter(whisper), None)
            fam = lambda l: FAMILY.get(l, l)  # noqa: E731
            agree = fam(w_top) == fam(best) and conf[best] >= LANG_AGREE_CONF
            # Oct 2026, 144 real-speaker clips in 18 languages: the 3 wrong automatic picks recognised only a
            # scrap of the sentence ("Andy." from 9 s of Greek) or had a second language fitting almost as well
            # (a Greek sentence full of English place names). Either way: ask the patient.
            n_words = len(results[best]["words"])
            runner = conf[ranked[1]] if len(ranked) > 1 else 0.0
            if n_words < LANG_MIN_WORDS or n_words / max(duration, 1.0) < LANG_MIN_WPS \
                    or (runner >= LANG_AGREE_CONF and conf[best] - runner < LANG_MARGIN):
                agree = False
            out = self._result(results[best], best, duration, guessed=True, t0=t0)
            # language scores for the "which language?" buttons: Transcribe confidence, best first
            out["langScores"] = {l: round(conf[l], 3) for l in ranked[:4] if conf[l] > 0}
            out["langConfidence"] = round(conf[best], 3) if agree else round(min(conf[best], 0.55), 3)
            out["langCheck"] = {"transcribe": best, "whisper": w_top, "agree": agree}
            out["uncertain"] = not agree
            out["method"] = "parallel Transcribe + Whisper agreement"
            return out
        except Exception as e:  # noqa: BLE001 - AWS unreachable, quota, timeout: Whisper on the server
            log.warning("Transcribe failed, Whisper fallback: %s", e)
            self.fallbacks["speech"] += 1
            return dict(self.local.transcribe(data, lang, candidates), engine="whisper (fallback)")

    def _result(self, r, lang, duration, guessed, t0):
        from .lexicon import lexicon
        text = r["text"]
        conf = r["confidence"] if r["confidence"] is not None else 0.0
        # Critical words heard with low confidence: numbers and medicine names
        lex = lexicon()
        meds = {w.lower() for h in lex.find(text, lang, {"medicine", "brand", "drug_class", "allergen"})
                for w in re.findall(r"\w+", text[h["start"]:h["end"]] if h.get("surface") else "")}
        low = [w for w, c in r["words"] if c is not None and c < CRITICAL_WORD_CONF
               and (_NUM_RX.search(w) or w.lower().strip(".,") in meds)]
        clarity = "unclear" if not text or conf < CONF_UNCLEAR else "noisy" if conf < CONF_CLEAR or low else "clear"
        return {"text": text, "lang": lang, "langConfidence": None, "langScores": {}, "uncertain": False,
                "noSpeech": not text, "duration": round(duration, 2), "asrConfidence": round(conf, 3),
                "clarity": clarity, "lowConfidenceWords": low, "engine": "Amazon Transcribe",
                "ms": int((time.time() - t0) * 1000)}

    # -- translation -------------------------------------------------------------------------------
    def _code(self, lang):
        return TRANSLATE_CODE.get(lang, lang)

    def translate(self, text: str, src: str, tgt: str):
        s, t = self._code(src), self._code(tgt)
        if s and t:
            try:
                kw = {"TerminologyNames": ["carebridge-medicines"]} if {src, tgt} & TERMINOLOGY_LANGS else {}
                if src == "yue":
                    text = _chars(text, "hk2s")
                out = self.translate_client.translate_text(Text=text, SourceLanguageCode=s, TargetLanguageCode=t,
                                                           **kw)["TranslatedText"]
                return _chars(out, "s2hk") if tgt == "yue" else out
            except Exception as e:  # noqa: BLE001
                log.warning("Translate failed, NLLB fallback: %s", e)
                self.fallbacks["translation"] += 1
        return self.local.translate(text, src, tgt)

    def translate_many(self, texts, src, tgt):
        return list(self._pool.map(lambda x: self.translate(x, src, tgt), texts))

    def model_label(self, src, tgt):
        return "Amazon Translate" if self._code(src) and self._code(tgt) else self.local.model_label(src, tgt)

    def similarity(self, a, b):
        return self.local.similarity(a, b)

    # -- voice -------------------------------------------------------------------------------------
    def voice_langs(self):
        return sorted(set(self.local.voice_langs()) | set(POLLY))

    def warm(self, lang):
        if lang not in POLLY:
            self.local.warm(lang)

    def tts(self, text: str, lang: str):
        if lang in POLLY:
            voice, engine = POLLY[lang]
            try:
                r = self.polly.synthesize_speech(Text=text, VoiceId=voice, Engine=engine, OutputFormat="pcm",
                                                 SampleRate="16000")
                pcm = r["AudioStream"].read()
                buf = io.BytesIO()
                with wave.open(buf, "wb") as w:
                    w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(pcm)
                return _loud(buf.getvalue())
            except Exception as e:  # noqa: BLE001
                log.warning("Polly failed, server voice: %s", e)
                self.fallbacks["voice"] += 1
        return self.local.tts(text, lang)
