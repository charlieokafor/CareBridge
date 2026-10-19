"""Language check on real speakers for the languages added in Oct 2026 (+ five existing ones as a regression check).
Google FLEURS test recordings, clean and in the emergency-department noise mix at 5 dB (same recipe as make_set.py),
sent to the running app exactly like a patient's first sentence (POST /api/transcribe, language unknown, every
patient language a candidate). Runs ON THE SERVER: python lid_newlangs.py OUT_DIR N_PER_LANG"""
import csv, json, os, sys, tarfile, time, urllib.request, uuid, wave
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from huggingface_hub import hf_hub_download
from faster_whisper.audio import decode_audio

OUT, N = sys.argv[1], int(sys.argv[2]); SR = 16000
os.makedirs(OUT, exist_ok=True)
FLEURS = {"pt": "pt_br", "zh": "cmn_hans_cn", "yue": "yue_hant_hk", "it": "it_it", "tr": "tr_tr", "vi": "vi_vn",
          "tl": "fil_ph", "bn": "bn_in", "sw": "sw_ke", "id": "id_id", "ja": "ja_jp", "cs": "cs_cz", "el": "el_gr",
          "en": "en_us", "uk": "uk_ua", "pl": "pl_pl", "ar": "ar_eg", "ru": "ru_ru"}
env = dict(l.strip().split("=", 1) for l in open("/opt/carebridge/app.env") if "=" in l)
BASE = "http://127.0.0.1:8080"
H = {"x-cb-origin": env.get("ORIGIN_SECRET", "")}


def save(p, a):
    a = np.clip(a, -1, 1)
    with wave.open(p, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((a * 32767).astype(np.int16).tobytes())


def load(p):
    return decode_audio(p, sampling_rate=SR).astype(np.float32)


rms = lambda a: float(np.sqrt(np.mean(a ** 2)) + 1e-12)  # noqa: E731


def active_rms(a):
    f = a[: len(a) // 320 * 320].reshape(-1, 320); e = np.sqrt((f ** 2).mean(1))
    return float(np.sqrt(np.mean(e[e > e.max() * 0.1] ** 2)))


# emergency-department noise: staff chatter + monitor beeps + ventilation (as in make_set.py)
rng = np.random.default_rng(11); n_bg = SR * 30
bab = [load(f"/opt/cb-dev/medset/src/babble{k}.mp3") for k in range(6) if os.path.exists(f"/opt/cb-dev/medset/src/babble{k}.mp3")]
babble = sum(np.tile(np.concatenate([b, np.zeros(int(SR * .6), np.float32)]), 20)[int(rng.integers(0, SR * 3)):][:n_bg] for b in bab)
t = np.arange(n_bg) / SR
beeps = 0.25 * np.sin(2 * np.pi * 960 * t) * ((t % 1.0) < 0.15) + 0.15 * np.sin(2 * np.pi * 523 * t) * (((t + 0.4) % 3.0) < 0.25)
brown = np.cumsum(rng.normal(0, 1, n_bg)); brown -= np.convolve(brown, np.ones(4000) / 4000, mode="same")
hvac = brown / np.abs(brown).max() * 0.5 + 0.2 * np.sin(2 * np.pi * 50 * t)
er = babble / rms(babble) + 0.35 * beeps / rms(beeps) + 0.35 * hvac / rms(hvac)

meta_p = f"{OUT}/meta.json"
meta = json.load(open(meta_p)) if os.path.exists(meta_p) else {}
for lang, fl in FLEURS.items():
    if any(m["lang"] == lang for m in meta.values()):
        continue
    tsv = hf_hub_download("google/fleurs", f"data/{fl}/test.tsv", repo_type="dataset")
    tgz = hf_hub_download("google/fleurs", f"data/{fl}/audio/test.tar.gz", repo_type="dataset")
    rows = [r for r in csv.reader(open(tsv, encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE)]
    rows = [r for r in rows if len(r) > 5 and 64000 <= int(r[5]) <= 192000]
    want, seen = {}, set()
    for r in rows[::7]:             # spread over speakers
        if r[0] not in seen:
            seen.add(r[0]); want[r[1]] = r
        if len(want) == N:
            break
    n = 0
    with tarfile.open(tgz) as tf:
        for m in tf:
            if os.path.basename(m.name) in want:
                raw = f"{OUT}/tmp.wav"; open(raw, "wb").write(tf.extractfile(m).read())
                s = load(raw); s = s / max(1e-6, np.abs(s).max()) * 0.5
                sp = np.concatenate([np.zeros(SR // 2, np.float32), s, np.zeros(SR // 2, np.float32)])
                off = int(rng.integers(0, SR * 8)); nz = er[off: off + len(sp)]
                nz = nz / rms(nz) * active_rms(s) / 10 ** (5 / 20)
                for cond, a in (("clean", sp), ("er_5db", sp + nz)):
                    k = f"{lang}_{n}__{cond}"; save(f"{OUT}/{k}.wav", a)
                    meta[k] = {"lang": lang, "cond": cond, "text": want[os.path.basename(m.name)][2]}
                n += 1
    os.remove(os.path.realpath(tgz))          # FLEURS archives are large: keep only the clips
    print(lang, n, flush=True)
    json.dump(meta, open(meta_p, "w"), ensure_ascii=False)


def post_json(path, body, tok=None):
    h = {"Content-Type": "application/json", **H, **({"Authorization": f"Bearer {tok}"} if tok else {})}
    with urllib.request.urlopen(urllib.request.Request(BASE + path, json.dumps(body).encode(), h), timeout=60) as r:
        return json.loads(r.read())


tok = post_json("/api/login", {"name": "Language test", "code": env["STAFF_CODE"]})["token"]
cfg = json.loads(urllib.request.urlopen(urllib.request.Request(BASE + "/api/config", headers={**H, "Authorization": f"Bearer {tok}"})).read())
cands = ",".join(["en"] + cfg["patientLangs"])


def transcribe(k):
    b = uuid.uuid4().hex
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"candidates\"\r\n\r\n{cands}\r\n"
            f"--{b}\r\nContent-Disposition: form-data; name=\"audio\"; filename=\"a.wav\"\r\nContent-Type: audio/wav\r\n\r\n").encode() \
        + open(f"{OUT}/{k}.wav", "rb").read() + f"\r\n--{b}--\r\n".encode()
    h = {**H, "Authorization": f"Bearer {tok}", "Content-Type": f"multipart/form-data; boundary={b}"}
    t0 = time.time()
    for a in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(BASE + "/api/transcribe", body, h), timeout=90) as r:
                return k, json.loads(r.read()), time.time() - t0
        except Exception as e:  # noqa: BLE001
            err = e; time.sleep(3)
    return k, {"error": str(err)}, time.time() - t0


res = {}
with ThreadPoolExecutor(3) as ex:
    for k, r, secs in ex.map(transcribe, sorted(meta)):
        m = meta[k]
        res[k] = {**m, "got": r.get("lang"), "uncertain": r.get("uncertain"), "langCheck": r.get("langCheck"),
                  "langScores": r.get("langScores"), "engine": r.get("engine"), "text_out": r.get("text"),
                  "secs": round(secs, 1), "error": r.get("error")}
        auto = not r.get("uncertain")
        print(f"{k:22} -> {r.get('lang')!s:4} {'AUTO' if auto else 'ask '} {'WRONG' if auto and r.get('lang') != m['lang'] else ''}"
              f" {r.get('langCheck')} {secs:.1f}s", flush=True)
json.dump(res, open(f"{OUT}/results.json", "w"), ensure_ascii=False, indent=1)
auto = [r for r in res.values() if not r["uncertain"] and not r["error"]]
wrong = [k for k, r in res.items() if not r["uncertain"] and r["got"] != r["lang"]]
print(f"\n{len(res)} clips | automatic {len(auto)} ({len(auto) / len(res):.0%}) | wrong automatic {len(wrong)}: {wrong}")
for lang in FLEURS:
    rs = [r for r in res.values() if r["lang"] == lang]
    a = [r for r in rs if not r["uncertain"]]
    asked_right = sum(1 for r in rs if r["uncertain"] and r["lang"] in (r["langScores"] or {}))
    print(f"{lang:4} auto {len(a)}/{len(rs)}  wrong {sum(r['got'] != lang for r in a)}  "
          f"asked-with-right-option {asked_right}/{len(rs) - len(a)}")
