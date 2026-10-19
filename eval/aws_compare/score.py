"""Scores every system on the noise test set. Usage: python score.py SET_DIR  (reads whisper_*.json, transcribe_*.json)
Writes SET_DIR/summary.json and prints tables. CER = character error rate (works across scripts), WER = word error rate.
A clip "fails" when CER > 0.3 (too wrong to use) or the wrong language came back."""
import glob, json, os, re, sys, unicodedata
from collections import defaultdict
D = sys.argv[1]
meta = json.load(open(f"{D}/meta.json"))
NOISES = ["clean", "er_10db", "er_5db", "er_0db", "russian"]
DIG = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven",
       "8": "eight", "9": "nine"}


def norm_words(s):
    s = unicodedata.normalize("NFKC", s.lower())
    s = re.sub(r"[ً-ْ]", "", s)            # Arabic diacritics
    s = re.sub(r"[^\w\s]|_", " ", s)
    return s.split()


def ed(a, b):
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def cer(ref, hyp):
    r, h = "".join(norm_words(ref)), "".join(norm_words(hyp))
    return min(1.0, ed(r, h) / max(1, len(r)))


def wer(ref, hyp):
    r, h = norm_words(ref), norm_words(hyp)
    return min(1.0, ed(r, h) / max(1, len(r)))


systems = {}
for f in sorted(glob.glob(f"{D}/whisper_*.json") + glob.glob(f"{D}/transcribe_*.json")):
    systems[os.path.basename(f)[:-5]] = json.load(open(f))
summary = {}
for name, res in systems.items():
    agg = defaultdict(lambda: defaultdict(list))
    for k, r in res.items():
        m = meta[k]
        c, w = cer(m["text"], r.get("text", "")), wer(m["text"], r.get("text", ""))
        lang_ok = r.get("lang") in (None, m["lang"]) if "auto" not in name else r.get("lang") == m["lang"]
        fail = c > 0.3 or not lang_ok
        for grp in (("noise", m["noise"]), ("lang", m["lang"]), ("kind", m["kind"]), ("all", "all"),
                    ("kind_noise", m["kind"] + "|" + m["noise"])):
            a = agg[grp[0]][grp[1]]
            a.append((c, w, fail, lang_ok, r.get("s") or r.get("jobSeconds") or 0))
    out = {}
    for g, d in agg.items():
        out[g] = {kk: {"n": len(v), "cer": round(sum(x[0] for x in v) / len(v), 3), "wer": round(sum(x[1] for x in v) / len(v), 3),
                       "fail": round(sum(x[2] for x in v) / len(v), 3), "langOk": round(sum(x[3] for x in v) / len(v), 3),
                       "secs": round(sum(x[4] for x in v) / len(v), 2)} for kk, v in d.items()}
    summary[name] = out
json.dump(summary, open(f"{D}/summary.json", "w"), indent=1)
print(f"{'system':16} " + " ".join(f"{n:>16}" for n in NOISES) + "   (WER / fail rate; real speakers + clinical)")
for name, s in summary.items():
    print(f"{name:16} " + " ".join(f"{s['noise'].get(n, {}).get('wer', float('nan')):7.1%} /{s['noise'].get(n, {}).get('fail', float('nan')):6.0%}" for n in NOISES)
          + f"   n={s['all']['all']['n']} {s['all']['all']['secs']}s/clip")
print("\nby language (WER, all noise levels):")
langs = ["en", "uk", "pl", "ro", "ru", "ar"]
print(f"{'system':16} " + " ".join(f"{l:>7}" for l in langs))
for name, s in summary.items():
    print(f"{name:16} " + " ".join(f"{s['lang'].get(l, {}).get('wer', float('nan')):7.1%}" for l in langs))
