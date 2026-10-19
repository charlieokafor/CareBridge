"""Noise test set for the Whisper vs Amazon Transcribe comparison.
Speech: (1) real human speakers from Google FLEURS (read sentences) in en/uk/pl/ro/ru/ar, (2) CareBridge's clinical
lines (the app's Ukrainian demo clips + neural TTS). Noise: emergency-department mix (staff chatter, monitor beeps,
alarm, ventilation) at 10/5/0 dB SNR, and a competing Russian speaker. Usage: python make_set.py OUT N_PER_LANG"""
import asyncio, csv, json, os, sys, tarfile, wave
import numpy as np, edge_tts
from huggingface_hub import hf_hub_download
from faster_whisper.audio import decode_audio
OUT, N = sys.argv[1], int(sys.argv[2]); SR = 16000
os.makedirs(f"{OUT}/src", exist_ok=True); os.makedirs(f"{OUT}/mix", exist_ok=True)
FLEURS = {"en": "en_us", "uk": "uk_ua", "pl": "pl_pl", "ro": "ro_ro", "ru": "ru_ru", "ar": "ar_eg"}
MED = [("med_uk_help", "app:uk2_help", "Допоможіть, будь ласка. У мене дуже болить у грудях. У мене алергія на пеніцилін.", "uk"),
       ("med_uk_stomach", "app:uk2_stomach", "Так, у мене болить живіт праворуч. Також у мене алергія на пеніцилін.", "uk"),
       ("med_uk_breath", "app:uk2_breath", "Мені дуже погано, мені важко дихати.", "uk"),
       ("med_uk_head", "uk-UA-OstapNeural", "У мене сильно болить голова і мене нудить.", "uk"),
       ("med_en_safe", "en-IE-ConnorNeural", "You are safe. We will not give you penicillin.", "en"),
       ("med_en_dose", "en-IE-EmilyNeural", "Take two tablets of 500 milligram paracetamol every six hours.", "en"),
       ("med_en_where", "en-IE-ConnorNeural", "Where does it hurt? Show me with your hand.", "en"),
       ("med_pl_allergy", "pl-PL-ZofiaNeural", "Jestem uczulona na penicylinę i biorę metforminę dwa razy dziennie.", "pl"),
       ("med_ro_pain", "ro-RO-EmilNeural", "Mă doare foarte tare în partea dreaptă a abdomenului de ieri seară.", "ro"),
       ("med_ru_chest", "ru-RU-SvetlanaNeural", "У меня болит грудь и немеет левая рука.", "ru"),
       ("med_ar_allergy", "ar-EG-SalmaNeural", "عندي حساسية من البنسلين وأشعر بألم شديد في صدري.", "ar")]
BABBLE = [("en-GB-SoniaNeural", "Can someone get bay four a blood gas please, and page the registrar."),
          ("en-US-GuyNeural", "Trauma call in two minutes, resus one, adult male, road traffic collision."),
          ("en-GB-RyanNeural", "I need a porter for cubicle seven, she's going up to the ward now."),
          ("en-US-JennyNeural", "Has anyone seen the portable monitor? It was here a minute ago."),
          ("en-AU-NatashaNeural", "Sorry, you'll have to wait in the waiting room, the doctor will call you."),
          ("en-IE-EmilyNeural", "Bloods are back on bed two, the potassium is a bit high, can you have a look.")]
COMPETE = ("ru-RU-DmitryNeural", "Где мой телефон? Я жду здесь уже два часа, когда нас примут?")


def load(p):
    return decode_audio(p, sampling_rate=SR).astype(np.float32)


def save(p, a):
    a = np.clip(a, -1, 1)
    with wave.open(p, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((a * 32767).astype(np.int16).tobytes())


def rms(a):
    return float(np.sqrt(np.mean(a ** 2)) + 1e-12)


def active_rms(a):
    f = a[: len(a) // 320 * 320].reshape(-1, 320); e = np.sqrt((f ** 2).mean(1))
    return float(np.sqrt(np.mean(e[e > e.max() * 0.1] ** 2)))


def loop_to(a, n, offset=0):
    a = np.concatenate([a, np.zeros(int(SR * 0.6), np.float32)])
    return np.tile(a, int(np.ceil((n + offset) / len(a))) + 1)[offset: offset + n]


async def tts(v, t, p):
    if os.path.exists(p):
        return
    err = None
    for _ in range(3):
        try:
            await edge_tts.Communicate(t, v).save(p); return
        except Exception as e:
            err = e; await asyncio.sleep(2)
    raise err


speech = []  # (id, path, text, lang, kind)
for lang, fl in FLEURS.items():
    tsv = hf_hub_download("google/fleurs", f"data/{fl}/test.tsv", repo_type="dataset")
    tgz = hf_hub_download("google/fleurs", f"data/{fl}/audio/test.tar.gz", repo_type="dataset")
    rows = [r for r in csv.reader(open(tsv, encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE)]
    rows = [r for r in rows if len(r) > 5 and 64000 <= int(r[5]) <= 192000]   # 4-12 s (samples at 16 kHz)
    seen, want = set(), {}
    for r in rows:   # distinct sentences
        if r[0] in seen:
            continue
        seen.add(r[0]); want[r[1]] = r
        if len(want) == N:
            break
    n = 0
    with tarfile.open(tgz) as tf:
        for m in tf:
            name = os.path.basename(m.name)
            if name in want:
                p = f"{OUT}/src/fleurs_{lang}_{n}.wav"; n += 1
                open(p + ".raw", "wb").write(tf.extractfile(m).read()); save(p, load(p + ".raw")); os.remove(p + ".raw")
                speech.append((os.path.basename(p)[:-4], p, want[name][2], lang, "fleurs"))
    print(lang, n, flush=True)


async def gen():
    await asyncio.gather(*[tts(v, t, f"{OUT}/src/{i}.mp3") for i, v, t, _ in MED if not v.startswith("app:")],
                         *[tts(v, t, f"{OUT}/src/babble{k}.mp3") for k, (v, t) in enumerate(BABBLE)],
                         tts(*COMPETE, f"{OUT}/src/compete.mp3"))
asyncio.run(gen())
for i, v, t, l in MED:
    speech.append((i, f"/opt/carebridge/app/web/audio/{v[4:]}.wav" if v.startswith("app:") else f"{OUT}/src/{i}.mp3",
                   t, l, "clinical"))

rng = np.random.default_rng(7); n_bg = SR * 30
babble = sum(loop_to(load(f"{OUT}/src/babble{k}.mp3"), n_bg, int(rng.integers(0, SR * 3))) for k in range(len(BABBLE)))
t = np.arange(n_bg) / SR
beeps = 0.25 * np.sin(2 * np.pi * 960 * t) * ((t % 1.0) < 0.15) + 0.15 * np.sin(2 * np.pi * 523 * t) * (((t + 0.4) % 3.0) < 0.25)
brown = np.cumsum(rng.normal(0, 1, n_bg)); brown -= np.convolve(brown, np.ones(4000) / 4000, mode="same")
hvac = brown / np.abs(brown).max() * 0.5 + 0.2 * np.sin(2 * np.pi * 50 * t)
er = babble / rms(babble) + 0.35 * beeps / rms(beeps) + 0.35 * hvac / rms(hvac)
compete = loop_to(load(f"{OUT}/src/compete.mp3"), n_bg, SR)
meta = {}
for sid, path, text, lang, kind in speech:
    s = load(path); s = s / max(1e-6, np.abs(s).max()) * 0.5
    sp = np.concatenate([np.zeros(SR, np.float32), s, np.zeros(int(SR * 0.7), np.float32)]); sr_ = active_rms(s)
    cases = {"clean": sp}
    for name, snr, comp in (("er_10db", 10, None), ("er_5db", 5, None), ("er_0db", 0, None), ("russian", 12, 6)):
        off = int(rng.integers(0, SR * 8)); nz = er[off: off + len(sp)]; nz = nz / rms(nz) * sr_ / 10 ** (snr / 20)
        if comp:
            c = compete[off: off + len(sp)]; nz = nz + c / active_rms(c) * sr_ / 10 ** (comp / 20)
        cases[name] = sp + nz
    for name, a in cases.items():
        save(f"{OUT}/mix/{sid}__{name}.wav", a)
        meta[f"{sid}__{name}"] = {"text": text, "lang": lang, "clip": sid, "noise": name, "kind": kind}
json.dump(meta, open(f"{OUT}/meta.json", "w"), ensure_ascii=False, indent=1)
print(len(meta), "files")
