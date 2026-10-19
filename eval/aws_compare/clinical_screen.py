"""Clinical safety screen for a new patient language, through the live app (POST /api/eval/check).
The team's 20 clinical sentences (eval/lang_eval_server.py) go English -> language -> English with the app's
translator, and CareBridge's own safety net scores each one exactly as in a consultation: critical-detail checks
(numbers, doses, sides, negations), the lexicon medicine check and the meaning score.
A language is switched on when the safety net would let at least 90% of sentences through unflagged and no
sentence loses a critical detail silently (a lost detail must be caught = flagged, never "ok").
Usage: python clinical_screen.py BASE_URL STAFF_CODE OUT.json lang1,lang2,..."""
import json, os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
SENT = ["Take two 500 milligram paracetamol tablets every six hours.", "Do not eat or drink anything after midnight.",
        "The pain is in your left leg.", "Take one ibuprofen tablet twice a day after food.", "You are allergic to penicillin.",
        "Do not take more than eight tablets in 24 hours.", "We will operate on your right knee tomorrow.",
        "Take 10 units of insulin before breakfast.", "Your blood pressure is 150 over 90.",
        "Do not drive for 24 hours after the anaesthetic.", "The X-ray shows a fracture in your left wrist.",
        "Take 5 ml of the syrup three times a day.", "You must not take aspirin with this medicine.",
        "Come back in 7 days to have the stitches removed.", "Do not lift anything heavy for six weeks.",
        "Your temperature is 39 degrees.", "Take the antibiotic for 5 days, even if you feel better.",
        "The pain on your right side may be appendicitis.", "Do not stop taking warfarin without asking your doctor.",
        "Press this button if the pain in your chest gets worse."]
base, code, out, langs = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3], sys.argv[4].split(",")


def post(path, body, tok=None):
    h = {"Content-Type": "application/json", **({"Authorization": f"Bearer {tok}"} if tok else {})}
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), headers=h)
    for a in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read())
        except OSError:
            if a == 3:
                raise
            time.sleep(3 * (a + 1))


tok = post("/api/login", {"name": "Clinical screen", "code": code})["token"]
res = json.load(open(out)) if os.path.exists(out) else {}


def one(args):
    lang, s = args
    r = post("/api/eval/check", {"source": s, "srcLang": "en", "tgtLang": lang}, tok)
    failed = [c["name"] for c in r["checks"] if c.get("ok") is False]
    warned = [c["name"] for c in r["checks"] if c.get("warn")]
    return {"en": s, "tr": r["translation"], "back": r["back"], "score": r["meaning"]["score"],
            "failed": failed, "warned": warned, "status": r["status"]}


with ThreadPoolExecutor(6) as pool:
    for lang in langs:
        if lang in res:
            continue
        rows = list(pool.map(one, [(lang, s) for s in SENT]))
        ok = sum(r["status"] == "ok" for r in rows)
        res[lang] = {"okRate": round(ok / len(rows), 2), "avgScore": round(sum(r["score"] for r in rows) / len(rows), 1),
                     "flagged": [r for r in rows if r["status"] != "ok"], "rows": rows}
        print(f"{lang:4} ok {ok}/20  meaning {res[lang]['avgScore']}  flagged: "
              + "; ".join(f"{r['en'][:40]}… {r['failed'] or r['warned'] or r['status']}" for r in res[lang]["flagged"]),
              flush=True)
        json.dump(res, open(out, "w"), ensure_ascii=False, indent=1)
