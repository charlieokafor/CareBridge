"""Amazon Translate with vs without the carebridge-medicines terminology, on medicine-heavy clinical sentences.
Scores: medicine name correct in the target language (stem of the curated name), and CareBridge's safety net
(critical checks + MiniLM meaning score on the back-translation). Runs on the server from /opt/carebridge/app."""
import json, os, re, sys, unicodedata
sys.path.insert(0, os.getcwd())
import boto3
from sentence_transformers import SentenceTransformer
from server import safety
TERMS = json.load(open("server/medical_terms.json", encoding="utf-8"))["medicines"]
tr = boto3.client("translate", region_name="eu-west-1")
st = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
SENT = ["Take metformin twice a day with food.", "You are allergic to amoxicillin.", "Do not take ibuprofen with warfarin.",
        "Use the salbutamol inhaler when you are short of breath.", "Take omeprazole every morning before breakfast.",
        "We will give you morphine for the pain.", "Stop taking clopidogrel five days before the operation.",
        "Take two paracetamol tablets every six hours.", "Inject enoxaparin once a day for ten days.",
        "Are you taking apixaban or rivaroxaban?", "You need flucloxacillin four times a day for seven days.",
        "Do not drink alcohol while taking metronidazole.", "Take prednisolone 40 mg every morning.",
        "Ondansetron will stop the vomiting.", "Keep your EpiPen with you at all times.",
        "Codeine can make you constipated.", "Take 75 mg of aspirin once a day.", "Tell us if you take insulin.",
        "Have you ever had a reaction to penicillin?", "Take furosemide in the morning, not at night."]
LANGS = ["uk", "ru", "pl", "ro", "ar", "fr", "es", "de", "hi", "ko", "ga", "ur"]


def norm(s, lang):
    s = unicodedata.normalize("NFKC", s.lower())
    if lang == "ar":
        s = re.sub(r"[ً-ْ]", "", s).replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    return s


def med_ok(en, out, lang):
    """Every medicine in the English sentence appears in the translation (stem of the curated name)."""
    res = []
    for m, row in TERMS.items():
        if re.search(r"\b" + re.escape(m) + r"\b", en, re.I) and row.get(lang):
            name = norm(row[lang], lang); name = name[2:] if lang == "ar" and name.startswith("ال") else name
            stem = name[: max(4, len(name) - 2)] if lang not in ("ko", "hi") else name[: max(2, len(name) - 1)]
            res.append(stem in norm(out, lang))
    return all(res) if res else None


out = {}
for lang in LANGS:
    for mode in ("plain", "terms"):
        kw = {"TerminologyNames": ["carebridge-medicines"]} if mode == "terms" else {}
        rows = []
        for s in SENT:
            f = tr.translate_text(Text=s, SourceLanguageCode="en", TargetLanguageCode=lang, **kw)["TranslatedText"]
            b = tr.translate_text(Text=f, SourceLanguageCode=lang, TargetLanguageCode="en", **kw)["TranslatedText"]
            checks = safety.critical_checks(s, "en", f, lang, b)
            e = st.encode([s, b], normalize_embeddings=True); sim = float((e[0] * e[1]).sum())
            meaning = safety.meaning_verdict(sim)
            rows.append({"en": s, "tr": f, "back": b, "med": med_ok(s, f, lang), "status": safety.turn_status(checks, meaning, []),
                         "failed": [c["name"] for c in checks if c.get("ok") is False], "score": meaning["score"]})
        out[f"{lang}|{mode}"] = rows
        meds = [r["med"] for r in rows if r["med"] is not None]
        print(lang, mode, "medicine right", sum(meds), "/", len(meds), "| ok", sum(r["status"] == "ok" for r in rows),
              "warn", sum(r["status"] == "warn" for r in rows), "fail", sum(r["status"] == "fail" for r in rows), flush=True)
json.dump(out, open("/opt/cb-dev/terminology.json", "w"), ensure_ascii=False, indent=1)
print("TERMS_DONE")
