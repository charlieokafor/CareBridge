"""Builds an emergency-department noise test set: patient (Ukrainian) and clinician (Irish English) lines mixed with
background chatter, monitor beeps, ventilation hum and a competing Russian speaker, at 10, 3 and 0 dB below the speaker.

Usage (needs edge-tts and numpy): python eval/noise_bench_make.py <output dir> web/audio
Then: python eval/noise_bench_run.py <output dir> <label>   (from the carebridge folder, with faster-whisper installed)"""
import asyncio, json, os, subprocess, sys, wave
import numpy as np
import edge_tts

B = sys.argv[1]; WEB = sys.argv[2]; SR = 16000
SPEECH = [  # id, voice (None = existing app clip), text, language
    ("uk_help", "uk2_help", "Допоможіть, будь ласка. У мене дуже болить у грудях. У мене алергія на пеніцилін.", "uk"),
    ("uk_stomach", "uk2_stomach", "Так, у мене болить живіт праворуч. Також у мене алергія на пеніцилін.", "uk"),
    ("uk_breath", "uk2_breath", "Мені дуже погано, мені важко дихати.", "uk"),
    ("uk_head_m", "uk-UA-OstapNeural", "У мене сильно болить голова і мене нудить.", "uk"),
    ("en_safe", "en-IE-ConnorNeural", "You are safe. We will not give you penicillin.", "en"),
    ("en_dose", "en-IE-EmilyNeural", "Take two tablets of 500 milligram paracetamol every six hours.", "en"),
    ("en_where", "en-IE-ConnorNeural", "Where does it hurt? Show me with your hand.", "en"),
]
BABBLE = [("en-GB-SoniaNeural", "Can someone get bay four a blood gas please, and page the registrar."),
          ("en-US-GuyNeural", "Trauma call in two minutes, resus one, adult male, road traffic collision."),
          ("en-GB-RyanNeural", "I need a porter for cubicle seven, she's going up to the ward now."),
          ("en-US-JennyNeural", "Has anyone seen the portable monitor? It was here a minute ago."),
          ("en-AU-NatashaNeural", "Sorry, you'll have to wait in the waiting room, the doctor will call you."),
          ("en-IE-EmilyNeural", "Bloods are back on bed two, the potassium is a bit high, can you have a look.")]
COMPETE = ("ru-RU-DmitryNeural", "Где мой телефон? Я жду здесь уже два часа, когда нас примут?")

async def tts(voice, text, path):
    await edge_tts.Communicate(text, voice).save(path)

def load(path):
    wav = os.path.join(B, "src", os.path.basename(path).rsplit(".", 1)[0] + ".16k.wav")   # never next to app files
    subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", path, wav], check=True, capture_output=True)
    with wave.open(wav) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768

def save(path, a):
    a = np.clip(a, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((a * 32767).astype(np.int16).tobytes())

def rms(a):
    return float(np.sqrt(np.mean(a ** 2)) + 1e-12)

def active_rms(a):
    f = a[: len(a) // 320 * 320].reshape(-1, 320); e = np.sqrt((f ** 2).mean(1))
    return float(np.sqrt(np.mean(e[e > e.max() * 0.1] ** 2)))

def loop_to(a, n, offset=0):
    a = np.concatenate([a, np.zeros(int(SR * 0.6), np.float32)])
    reps = int(np.ceil((n + offset) / len(a))) + 1
    return np.tile(a, reps)[offset: offset + n]

async def main():
    jobs = []
    for sid, voice, text, lang in SPEECH:
        if not voice.startswith("uk2_"):
            jobs.append(tts(voice, text, f"{B}/src/{sid}.mp3"))
    for i, (v, t) in enumerate(BABBLE):
        jobs.append(tts(v, t, f"{B}/src/babble{i}.mp3"))
    jobs.append(tts(*COMPETE, f"{B}/src/compete.mp3"))
    await asyncio.gather(*jobs)
    rng = np.random.default_rng(7)
    n_bg = SR * 30
    babble = sum(loop_to(load(f"{B}/src/babble{i}.mp3"), n_bg, offset=int(rng.integers(0, SR * 3))) for i in range(len(BABBLE)))
    t = np.arange(n_bg) / SR
    beeps = 0.25 * np.sin(2 * np.pi * 960 * t) * ((t % 1.0) < 0.15)          # bedside monitor
    beeps += 0.15 * np.sin(2 * np.pi * 523 * t) * (((t + 0.4) % 3.0) < 0.25)  # alarm tone
    brown = np.cumsum(rng.normal(0, 1, n_bg)); brown -= np.convolve(brown, np.ones(4000) / 4000, mode="same")
    hvac = brown / np.abs(brown).max() * 0.5 + 0.2 * np.sin(2 * np.pi * 50 * t)
    er = babble / rms(babble) + 0.35 * beeps / rms(beeps) + 0.35 * hvac / rms(hvac)
    compete = loop_to(load(f"{B}/src/compete.mp3"), n_bg, offset=SR)
    meta = {}
    for sid, voice, text, lang in SPEECH:
        src = f"{WEB}/{voice}.wav" if voice.startswith("uk2_") else f"{B}/src/{sid}.mp3"
        s = load(src)
        s = s / max(1e-6, np.abs(s).max()) * 0.5
        lead, tail = int(SR * 1.0), int(SR * 0.7)            # tap-to-talk: a moment of room noise before and after
        speech = np.concatenate([np.zeros(lead, np.float32), s, np.zeros(tail, np.float32)])
        sr_ = active_rms(s)
        cases = {"clean": s}
        for name, snr, comp in (("er_10db", 10, None), ("er_3db", 3, None), ("er_0db", 0, None), ("russian_6db", 12, 6)):
            off = int(rng.integers(0, SR * 8))
            noise = er[off: off + len(speech)]
            noise = noise / rms(noise) * sr_ / (10 ** (snr / 20))
            if comp is not None:
                c = compete[off: off + len(speech)]
                noise = noise + c / active_rms(c) * sr_ / (10 ** (comp / 20))
            cases[name] = speech + noise
        for name, a in cases.items():
            save(f"{B}/mix/{sid}__{name}.wav", a)
            meta[f"{sid}__{name}"] = {"text": text, "lang": lang, "clip": sid, "noise": name}
    json.dump(meta, open(f"{B}/meta.json", "w"), ensure_ascii=False, indent=1)
    print(len(meta), "test files")

asyncio.run(main())
