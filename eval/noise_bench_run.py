"""Runs every noise-bench file through CareBridge's real transcribe() and scores what the user would experience:
correct, asked to repeat, asked which language, shown for checking, or WRONG BUT SPOKEN (must stay at zero).
Modes: "first" = language detected automatically, "locked" = English or the patient's language, "button" = the
speaker pressed their Tap to talk button, so the language is known.
Usage: python eval/noise_bench_run.py <bench dir> <label>   (run from the carebridge folder; FOCUS=20,12 TRIM=14 to tune)"""
import json, os, re, sys, time, unicodedata
B, label = sys.argv[1], sys.argv[2]
os.environ.setdefault("CB_MODELS", os.path.join(os.path.dirname(B), "models"))
sys.path.insert(0, os.getcwd())
from server.engines import RealEngines
import server.audio_clean as ac  # tuning knobs for experiments
if os.environ.get("FOCUS"): ac.FOCUS_DB, ac.FOCUS_KEEP_DB = map(float, os.environ["FOCUS"].split(","))
if os.environ.get("TRIM"): ac.TRIM_DB = float(os.environ["TRIM"])
eng = RealEngines()
while eng.status["speech"] == "loading": time.sleep(1)
assert eng.status["speech"] == "ready", eng.status
EMERGENCY = ["en", "uk", "ru", "pl", "ro", "ar", "fr", "de", "hi", "ko", "es", "ur"]
def norm(s): return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", s.lower()))
def cer(ref, hyp):
    r, h = norm(ref), norm(hyp)
    prev = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        cur = [i]
        for j, hc in enumerate(h, 1): cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rc != hc)))
        prev = cur
    return prev[-1] / max(1, len(r))
meta = json.load(open(f"{B}/meta.json")); out = {}
for key, m in sorted(meta.items()):
    data = open(f"{B}/mix/{key}.wav", "rb").read()
    row = {}
    for mode, cands in (("first", EMERGENCY), ("locked", ["en", "uk"]), ("button", None)):
        t0 = time.time(); r = eng.transcribe(data, m["lang"], None) if mode == "button" else eng.transcribe(data, None, cands)
        row[mode] = {"lang": r["lang"], "ok_lang": r["lang"] == m["lang"], "cer": round(cer(m["text"], r["text"]), 3),
                     "text": r["text"], "noSpeech": r.get("noSpeech", False), "conf": r.get("asrConfidence"), "clarity": r.get("clarity"), "uncertain": r.get("uncertain"), "s": round(time.time() - t0, 1)}
    out[key] = row
    f, l, b = row["first"], row["locked"], row["button"]
    print(f"{key:24} first {f['lang']:2} {'OK ' if f['ok_lang'] else 'BAD'} {f['cer']:.2f} | locked {l['cer']:.2f} | button {b['cer']:.2f} clarity {b['conf']} {'NOSPEECH' if b['noSpeech'] else ''}| {b['text'][:60]}", flush=True)
json.dump(out, open(f"{B}/result_{label}.json", "w"), ensure_ascii=False, indent=1)
for noise in ("clean", "er_10db", "er_3db", "er_0db", "russian_6db"):
    rows = [v for k, v in out.items() if k.endswith("__" + noise)]
    print(f"{label:9} {noise:12} lang ok {sum(r['first']['ok_lang'] for r in rows)}/{len(rows)}  "
          f"CER first {sum(r['first']['cer'] for r in rows)/len(rows):.2f}  locked {sum(r['locked']['cer'] for r in rows)/len(rows):.2f}  button {sum(r['button']['cer'] for r in rows)/len(rows):.2f}")

def outcome(r, want_lang):
    if r.get("clarity") == "unclear" or r["noSpeech"]: return "asked to repeat"
    if r.get("uncertain"): return "asked which language"
    good = r["cer"] < 0.3 and r["lang"] == want_lang
    if r.get("clarity") == "noisy": return "check first" + ("" if good else " (wrong words shown)")
    return "correct" if good else "WRONG BUT SPOKEN"
from collections import Counter
for mode in ("first", "button"):
    c = Counter(outcome(v[mode], meta[k]["lang"]) for k, v in out.items())
    print(f"{label} {mode:6}: " + ", ".join(f"{n} {k}" for k, n in c.most_common()))
    for k, v in out.items():
        if outcome(v[mode], meta[k]["lang"]) == "WRONG BUT SPOKEN": print("   !!", k, v[mode]["lang"], v[mode]["conf"], v[mode]["text"][:80])
print("seconds per clip (button mode): %.1f avg, %.1f max" % (sum(v["button"]["s"] for v in out.values())/len(out), max(v["button"]["s"] for v in out.values())))
