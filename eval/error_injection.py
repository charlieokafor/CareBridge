"""Error-injection stress test for the CareBridge safety net (rung 0 of the Safety Ladder).

1. Translate 20 clinical sentences (English -> Ukrainian) and record any false alarms.
2. Plant dangerous errors into the correct Ukrainian translations: a changed dose, a deleted "not",
   left swapped for right, a swapped medicine.
3. Run each corrupted translation through the safety net (back-translation + checks + meaning score)
   and count how many are caught.

Usage: SSL_CERT_FILE=/etc/ssl/cert.pem python3 eval/error_injection.py <app-url> <staff-code>
Writes eval/results.json and eval/results.csv."""
import csv
import json
import os
import re
import sys
import urllib.request

SENTENCES = [
    "Take two 500 milligram paracetamol tablets every six hours.",
    "Do not eat or drink anything after midnight.",
    "The pain is in your left leg.",
    "Take one ibuprofen tablet twice a day after food.",
    "You are allergic to penicillin.",
    "Do not take more than eight tablets in 24 hours.",
    "We will operate on your right knee tomorrow.",
    "Take 10 units of insulin before breakfast.",
    "Your blood pressure is 150 over 90.",
    "Do not drive for 24 hours after the anaesthetic.",
    "The X-ray shows a fracture in your left wrist.",
    "Take 5 ml of the syrup three times a day.",
    "You must not take aspirin with this medicine.",
    "Come back in 7 days to have the stitches removed.",
    "Do not lift anything heavy for six weeks.",
    "Your temperature is 39 degrees.",
    "Take the antibiotic for 5 days, even if you feel better.",
    "The pain on your right side may be appendicitis.",
    "Do not stop taking warfarin without asking your doctor.",
    "Press this button if the pain in your chest gets worse.",
]

UK_NUMBER_WORDS = {"одну": "дві", "одна": "дві", "один": "два", "дві": "три", "два": "три", "три": "п'ять",
                   "шість": "вісім", "шести": "восьми", "вісім": "шість", "восьми": "шести", "двічі": "чотири рази",
                   "тричі": "шість разів", "п'ять": "десять", "сім": "сімнадцять"}
UK_MEDS = {"парацетамол": "ібупрофен", "ібупрофен": "парацетамол", "пеніцилін": "амоксицилін",
           "інсулін": "гепарин", "аспірин": "парацетамол", "варфарин": "аспірин", "антибіотик": "знеболювальне"}


def corruptions(uk: str):
    out = []
    m = re.search(r"\d+", uk)
    if m:
        out.append(("dose/number changed", uk[:m.start()] + str(int(m.group()) * 10) + uk[m.end():]))
    else:
        for w, r in UK_NUMBER_WORDS.items():
            mm = re.search(rf"(?<!\w){w}(?!\w)", uk, re.I)
            if mm:
                out.append(("dose/number changed", uk[:mm.start()] + r + uk[mm.end():]))
                break
    if re.search(r"(?<!\w)[Нн]е(?!\w)", uk):
        dropped = re.sub(r"(?<!\w)Не\s+(\w)", lambda x: x.group(1).upper(), uk, count=1)
        dropped = re.sub(r"(?<!\w)не\s+", "", dropped, count=1) if dropped == uk else dropped
        out.append(("'not' deleted", dropped))
    if re.search(r"лів|прав", uk):
        swapped = re.sub(r"лів|прав", lambda x: "прав" if x.group() == "лів" else "лів", uk)
        if swapped != uk:
            out.append(("left/right swapped", swapped))
    for med, other in UK_MEDS.items():
        if med in uk.lower():
            out.append(("medicine swapped", re.sub(med, other, uk, flags=re.I)))
            break
    return out


def main():
    base, code = sys.argv[1].rstrip("/"), sys.argv[2]

    def post(path, body, tok=None):
        h = {"Content-Type": "application/json"}
        if tok:
            h["Authorization"] = f"Bearer {tok}"
        req = urllib.request.Request(base + path, data=json.dumps(body).encode(), headers=h)
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read())

    tok = post("/api/login", {"name": "Error-injection test", "code": code})["token"]
    rows, clean_flags, planted, caught, blocked = [], 0, 0, 0, 0
    for s in SENTENCES:
        clean = post("/api/eval/check", {"source": s, "srcLang": "en", "tgtLang": "uk"}, tok)
        if clean["status"] != "ok":
            clean_flags += 1
        rows.append({"kind": "clean", "error": "", "source": s, "translation": clean["translation"],
                     "back": clean["back"], "status": clean["status"], "score": clean["meaning"]["score"],
                     "failed_checks": ", ".join(c["name"] for c in clean["checks"] if not c["ok"])})
        print(f"CLEAN {clean['status']:4} {clean['meaning']['score']:3}  {s}")
        for kind, bad in corruptions(clean["translation"]):
            r = post("/api/eval/check", {"source": s, "srcLang": "en", "tgtLang": "uk", "translation": bad}, tok)
            planted += 1
            hit = r["status"] != "ok"
            caught += hit
            blocked += r["status"] == "fail"
            rows.append({"kind": "planted", "error": kind, "source": s, "translation": bad, "back": r["back"],
                         "status": r["status"], "score": r["meaning"]["score"],
                         "failed_checks": ", ".join(c["name"] for c in r["checks"] if not c["ok"])})
            print(f"  {'CAUGHT' if hit else 'MISSED'} {r['status']:4} {r['meaning']['score']:3}  {kind}: {r['back']}")
    summary = {"sentences": len(SENTENCES), "false_alarms": clean_flags, "planted": planted, "caught": caught,
               "blocked_as_fail": blocked, "missed": planted - caught}
    print(json.dumps(summary, indent=2))
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "results.json"), "w") as f:
        json.dump({"summary": summary, "rows": rows}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(here, "results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
