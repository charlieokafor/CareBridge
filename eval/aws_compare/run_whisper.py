"""Runs every test file through Whisper variants and the real CareBridge pipeline. Writes OUT/whisper_<variant>.json.
Variants: <size>_<mode>, size small|base|medium|turbo, mode raw|clean|vad|df ; or app_auto (real app, language guessed).
Usage: python run_whisper.py OUT variant[,variant...]   (run from /opt/carebridge/app; SUBSET=n limits FLEURS clips)"""
import io, json, os, sys, time
import numpy as np
OUT, variants = sys.argv[1], sys.argv[2].split(",")
sys.path.insert(0, os.getcwd())
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio
from server.audio_clean import clean_speech
meta = json.load(open(f"{OUT}/meta.json"))
SUB = os.environ.get("SUBSET")
keys = [k for k in sorted(meta) if not SUB or meta[k]["kind"] == "clinical"
        or int(meta[k]["clip"].rsplit("_", 1)[1]) < int(SUB)]
models = {}


def model(size):
    if size not in models:
        models[size] = WhisperModel(size, device="cpu", compute_type="int8", cpu_threads=2,
                                    download_root="/opt/carebridge/models/whisper")
    return models[size]


df = None


def deepfilter(a):
    global df
    import torch
    from df.enhance import enhance, init_df
    if df is None:
        df = init_df()
    m, st, _ = df; sr = st.sr()
    x = np.interp(np.arange(0, len(a), 16000 / sr), np.arange(len(a)), a).astype(np.float32)
    y = enhance(m, st, torch.from_numpy(x)[None])[0].numpy()
    return np.interp(np.arange(0, len(y), sr / 16000), np.arange(len(y)), y).astype(np.float32)


for v in variants:
    path = f"{OUT}/whisper_{v}.json"
    out = json.load(open(path)) if os.path.exists(path) else {}
    if v.startswith("app_") and "eng" not in globals():
        from server.engines import RealEngines
        eng = RealEngines()
        while eng.status["speech"] == "loading":
            time.sleep(1)
    for k in keys:
        if k in out:
            continue
        m = meta[k]; data = open(f"{OUT}/mix/{k}.wav", "rb").read(); t0 = time.time()
        if v.startswith("app_"):   # app_auto: language guessed; app_button: language known (Tap to talk)
            r = eng.transcribe(data, m["lang"]) if v == "app_button" else \
                eng.transcribe(data, None, ["en", "uk", "ru", "pl", "ro", "ar", "fr", "de", "hi", "ko", "es", "ur"])
            out[k] = {"text": r["text"], "lang": r["lang"], "clarity": r.get("clarity"), "uncertain": r.get("uncertain"),
                      "noSpeech": r.get("noSpeech"), "s": round(time.time() - t0, 2)}
        else:
            size, _, mode = v.partition("_")
            a = decode_audio(io.BytesIO(data), sampling_rate=16000)
            if mode == "clean":
                a, _ = clean_speech(a)
            if mode == "df":
                a = deepfilter(a)
            name = {"turbo": "large-v3-turbo"}.get(size, size)
            # same decoding as the app (server/engines.py _recognise): greedy, no retries, length cap
            segs, info = model(name).transcribe(a, language=m["lang"], beam_size=1, vad_filter=(mode == "vad"),
                                                condition_on_previous_text=False, temperature=0.0, max_new_tokens=160)
            out[k] = {"text": " ".join(s.text.strip() for s in segs).strip(), "lang": m["lang"],
                      "s": round(time.time() - t0, 2)}
        if len(out) % 20 == 0:
            json.dump(out, open(path, "w"), ensure_ascii=False); print(v, len(out), flush=True)
    json.dump(out, open(path, "w"), ensure_ascii=False); print("done", v, len(out), flush=True)
