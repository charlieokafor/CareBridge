"""Drug-name test set: 10 medicines x 2 patient sentences x 6 languages, two voices, mixed with the
emergency-department noise from make_set.py at clean / 10 dB / 5 dB. Usage: python make_med_set.py OUT"""
import asyncio, json, os, sys, wave
import numpy as np, edge_tts
from faster_whisper.audio import decode_audio
OUT = sys.argv[1]; NS = OUT; SR = 16000
os.makedirs(f"{OUT}/src", exist_ok=True); os.makedirs(f"{OUT}/mix", exist_ok=True)
DRUGS = {  # (form used in the sentence, form expected in the transcript's stem match)
 "en": ["amoxicillin", "metformin", "warfarin", "salbutamol", "omeprazole", "ibuprofen", "insulin", "clopidogrel", "apixaban", "codeine"],
 "uk": ["амоксицилін", "метформін", "варфарин", "сальбутамол", "омепразол", "ібупрофен", "інсулін", "клопідогрель", "апіксабан", "кодеїн"],
 "ru": ["амоксициллин", "метформин", "варфарин", "сальбутамол", "омепразол", "ибупрофен", "инсулин", "клопидогрель", "апиксабан", "кодеин"],
 "pl": ["amoksycylinę", "metforminę", "warfarynę", "salbutamol", "omeprazol", "ibuprofen", "insulinę", "klopidogrel", "apiksaban", "kodeinę"],
 "ro": ["amoxicilină", "metformină", "warfarină", "salbutamol", "omeprazol", "ibuprofen", "insulină", "clopidogrel", "apixaban", "codeină"],
 "ar": ["أموكسيسيلين", "الميتفورمين", "الوارفارين", "سالبوتامول", "أوميبرازول", "إيبوبروفين", "الأنسولين", "كلوبيدوجريل", "أبيكسابان", "الكودايين"],
}
TEMPL = {
 "en": ["I'm allergic to {d}.", "I take {d} every day."],
 "uk": ["У мене алергія на {d}.", "Я щодня приймаю {d}."],
 "ru": ["У меня аллергия на {d}.", "Я каждый день принимаю {d}."],
 "pl": ["Jestem uczulony na {d}.", "Codziennie biorę {d}."],
 "ro": ["Sunt alergic la {d}.", "Iau {d} în fiecare zi."],
 "ar": ["عندي حساسية من {d}.", "آخذ {d} كل يوم."],
}
VOICES = {"en": ["en-IE-EmilyNeural", "en-IE-ConnorNeural"], "uk": ["uk-UA-PolinaNeural", "uk-UA-OstapNeural"],
          "ru": ["ru-RU-SvetlanaNeural", "ru-RU-DmitryNeural"], "pl": ["pl-PL-ZofiaNeural", "pl-PL-MarekNeural"],
          "ro": ["ro-RO-AlinaNeural", "ro-RO-EmilNeural"], "ar": ["ar-EG-SalmaNeural", "ar-EG-ShakirNeural"]}


def load(p): return decode_audio(p, sampling_rate=SR).astype(np.float32)


def save(p, a):
    a = np.clip(a, -1, 1)
    with wave.open(p, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((a * 32767).astype(np.int16).tobytes())


def rms(a): return float(np.sqrt(np.mean(a ** 2)) + 1e-12)


def active_rms(a):
    f = a[: len(a) // 320 * 320].reshape(-1, 320); e = np.sqrt((f ** 2).mean(1)); return float(np.sqrt(np.mean(e[e > e.max() * 0.1] ** 2)))


items = []
for lang, ds in DRUGS.items():
    for i, d in enumerate(ds):
        for j, t in enumerate(TEMPL[lang]):
            items.append((f"med_{lang}_{i}_{j}", lang, t.format(d=d), d, VOICES[lang][(i + j) % 2]))


async def gen():
    sem = asyncio.Semaphore(8)
    async def one(sid, voice, text):
        p = f"{OUT}/src/{sid}.mp3"
        if os.path.exists(p): return
        async with sem:
            for a in range(4):
                try: await edge_tts.Communicate(text, voice).save(p); return
                except Exception: await asyncio.sleep(2)
    BAB = [("en-GB-SoniaNeural", "Can someone get bay four a blood gas please, and page the registrar."),
           ("en-US-GuyNeural", "Trauma call in two minutes, resus one, adult male, road traffic collision."),
           ("en-GB-RyanNeural", "I need a porter for cubicle seven, she's going up to the ward now."),
           ("en-US-JennyNeural", "Has anyone seen the portable monitor? It was here a minute ago."),
           ("en-AU-NatashaNeural", "Sorry, you'll have to wait in the waiting room, the doctor will call you."),
           ("en-IE-EmilyNeural", "Bloods are back on bed two, the potassium is a bit high, can you have a look.")]
    await asyncio.gather(*[one(s, v, t) for s, l, t, d, v in items], *[one(f"babble{k}", v, t) for k, (v, t) in enumerate(BAB)])
asyncio.run(gen())
# Same emergency-department background as the main benchmark: staff chatter + monitor beeps + alarm + ventilation
rng = np.random.default_rng(11); n_bg = SR * 30
def loop_to(a, n, off=0):
    a = np.concatenate([a, np.zeros(int(SR * 0.6), np.float32)]); return np.tile(a, int(np.ceil((n + off) / len(a))) + 1)[off: off + n]
bab = sum(loop_to(load(f"{NS}/src/babble{k}.mp3"), n_bg, int(rng.integers(0, SR * 3))) for k in range(6))
t = np.arange(n_bg) / SR
beeps = 0.25 * np.sin(2 * np.pi * 960 * t) * ((t % 1.0) < 0.15) + 0.15 * np.sin(2 * np.pi * 523 * t) * (((t + 0.4) % 3.0) < 0.25)
brown = np.cumsum(rng.normal(0, 1, n_bg)); brown -= np.convolve(brown, np.ones(4000) / 4000, mode="same")
hvac = brown / np.abs(brown).max() * 0.5 + 0.2 * np.sin(2 * np.pi * 50 * t)
er = bab / rms(bab) + 0.35 * beeps / rms(beeps) + 0.35 * hvac / rms(hvac)
meta = {}
for sid, lang, text, drug, voice in items:
    s = load(f"{OUT}/src/{sid}.mp3"); s = s / max(1e-6, np.abs(s).max()) * 0.5
    sp = np.concatenate([np.zeros(int(SR * 0.6), np.float32), s, np.zeros(int(SR * 0.5), np.float32)]); sr_ = active_rms(s)
    for name, snr in (("clean", None), ("er_10db", 10), ("er_5db", 5)):
        a = sp
        if snr is not None:
            off = int(rng.integers(0, SR * 8)); nz = er[off: off + len(sp)]; a = sp + nz / rms(nz) * sr_ / 10 ** (snr / 20)
        save(f"{OUT}/mix/{sid}__{name}.wav", a)
        meta[f"{sid}__{name}"] = {"text": text, "lang": lang, "drug": drug, "noise": name, "kind": "drug"}
json.dump(meta, open(f"{OUT}/meta.json", "w"), ensure_ascii=False, indent=1); print(len(meta), "files")
