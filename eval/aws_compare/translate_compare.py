"""NLLB (CareBridge's self-hosted translator) vs Amazon Translate. Runs ON THE SERVER from /opt/carebridge/app.
1. Clinical: the 20 sentences from eval/lang_eval_server.py, English -> language -> English with each engine, scored
   by CareBridge's own safety net (critical-detail checks + MiniLM meaning score), exactly as the app would.
2. General quality: FLORES-200 devtest (human reference translations), 100 sentences per language, both directions,
   scored with chrF++ (sacrebleu). Usage: python translate_compare.py OUT.json"""
import json, os, sys, time
sys.path.insert(0, os.getcwd())
import boto3, sacrebleu
from server import safety
from server.engines import RealEngines
OUT = sys.argv[1]
LANGS = ["uk", "ru", "pl", "ro", "ar", "ga", "fr", "es", "ur", "ko", "de", "hi"]   # the app's active patient languages
FL = {"en": "eng_Latn", "uk": "ukr_Cyrl", "pl": "pol_Latn", "ro": "ron_Latn", "ru": "rus_Cyrl", "ar": "arb_Arab",
      "ga": "gle_Latn", "fr": "fra_Latn", "es": "spa_Latn", "ur": "urd_Arab", "ko": "kor_Hang", "de": "deu_Latn",
      "hi": "hin_Deva"}
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
eng = RealEngines()
while "loading" in (eng.status["translation"], eng.status["meaning"]):
    time.sleep(1)
aws = boto3.client("translate", region_name=os.environ.get("CB_TRANSLATE_REGION", "eu-north-1"))


def amazon(text, src, tgt):
    return aws.translate_text(Text=text, SourceLanguageCode=src, TargetLanguageCode=tgt)["TranslatedText"]


ENGINES = {"nllb": eng.translate, "amazon": amazon}
fl_dir = "/opt/cb-bench/flores200_dataset/devtest"
flores = {l: open(f"{fl_dir}/{c}.devtest", encoding="utf-8").read().splitlines()[:100] for l, c in FL.items()}
res = json.load(open(OUT)) if os.path.exists(OUT) else {}
for lang in LANGS:
    if lang in res:
        continue
    r = {}
    for name, tr in ENGINES.items():
        rows, t0 = [], time.time()
        try:
            for s in SENT:
                fwd = tr(s, "en", lang); back = tr(fwd, lang, "en")
                checks = safety.critical_checks(s, "en", fwd, lang, back)
                meaning = safety.meaning_verdict(eng.similarity(s, back))
                failed = [c["name"] for c in checks if c.get("ok") is False]
                rows.append({"en": s, "tr": fwd, "back": back, "score": meaning["score"], "failed": failed,
                             "status": safety.turn_status(checks, meaning, [])})
            secs = (time.time() - t0) / (2 * len(SENT))
            hyp_x = [tr(s, "en", lang) for s in flores["en"]]
            hyp_en = [tr(s, lang, "en") for s in flores[lang]]
            r[name] = {"clinical": rows, "avgScore": round(sum(x["score"] for x in rows) / len(rows), 1),
                       "okRate": round(sum(x["status"] == "ok" for x in rows) / len(rows), 2),
                       "failedChecks": sum(bool(x["failed"]) for x in rows), "secsPerSentence": round(secs, 2),
                       "chrf_en_to_x": round(sacrebleu.corpus_chrf(hyp_x, [flores[lang]], word_order=2).score, 1),
                       "chrf_x_to_en": round(sacrebleu.corpus_chrf(hyp_en, [flores["en"]], word_order=2).score, 1),
                       "chars": sum(len(s) for s in SENT) * 2 + sum(len(s) for s in flores["en"] + flores[lang])}
        except Exception as e:
            r[name] = {"error": f"{type(e).__name__}: {e}"[:300]}
        print(lang, name, {k: v for k, v in r[name].items() if k != "clinical"}, flush=True)
    res[lang] = r
    json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1)
print("TRANSLATE_DONE")
