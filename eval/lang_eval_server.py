"""Runs ON THE SERVER: scores every language with both NLLB models on 20 clinical sentences.

For each language and model: English -> language -> English, then the meaning score (MiniLM) and the
critical-detail checks for every sentence. A language is licensed on the fastest model that passes;
languages that fail both are removed. Writes /opt/carebridge/lang_eval.json.

This is a round-trip screen, not a substitute for interpreter rating (Safety Ladder step 1)."""
import json
import sys
import time

sys.path.insert(0, "/opt/carebridge/app")
import ctranslate2  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402
from transformers import AutoTokenizer  # noqa: E402

from server import safety  # noqa: E402
from server.phrasebank import LANGUAGES, PATIENT_LANGS  # noqa: E402

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
MODELS = {"600m": "/opt/carebridge/models/nllb-600m", "1.3b": "/opt/carebridge/models/nllb-1.3b"}
PASS_AVG, PASS_OK = 88, 0.9

tok = AutoTokenizer.from_pretrained("facebook/nllb-200-distilled-600M")
st = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", device="cpu")
translators = {k: ctranslate2.Translator(p, device="cpu", compute_type="int8", intra_threads=2) for k, p in MODELS.items()}


def translate(tr, texts, src, tgt):
    tok.src_lang = LANGUAGES[src]["nllb"]
    batch = [tok.convert_ids_to_tokens(tok.encode(t)) for t in texts]
    res = tr.translate_batch(batch, target_prefix=[[LANGUAGES[tgt]["nllb"]]] * len(batch), beam_size=2,
                             max_decoding_length=256, repetition_penalty=1.1)
    return [tok.decode(tok.convert_tokens_to_ids(r.hypotheses[0][1:]), skip_special_tokens=True).strip() for r in res]


results = {}
for lang in PATIENT_LANGS:
    results[lang] = {}
    for name, tr in translators.items():
        t0 = time.time()
        fwd = translate(tr, SENTENCES, "en", lang)
        back = translate(tr, fwd, lang, "en")
        secs = (time.time() - t0) / len(SENTENCES)
        emb = st.encode(SENTENCES + back, normalize_embeddings=True)
        rows, scores, oks = [], [], 0
        for i, s in enumerate(SENTENCES):
            sim = float((emb[i] * emb[len(SENTENCES) + i]).sum())
            m = safety.meaning_verdict(sim)
            checks = safety.critical_checks(s, "en", fwd[i], lang, back[i])
            ok = m["score"] >= 80 and all(c["ok"] for c in checks)
            oks += ok
            scores.append(m["score"])
            rows.append({"en": s, "tr": fwd[i], "back": back[i], "score": m["score"],
                         "failed": [c["name"] for c in checks if not c["ok"]]})
        results[lang][name] = {"avg": round(sum(scores) / len(scores), 1), "min": min(scores),
                               "okRate": round(oks / len(SENTENCES), 2), "secsPerSentence": round(secs, 2), "rows": rows}
        print(f"{lang:4} {name:5} avg={results[lang][name]['avg']:5} min={min(scores):3} ok={oks}/20 {secs:.2f}s", flush=True)
    passing = [n for n in ("600m", "1.3b") if results[lang][n]["avg"] >= PASS_AVG and results[lang][n]["okRate"] >= PASS_OK]
    results[lang]["decision"] = passing[0] if passing else "remove"
    print(f"     -> {results[lang]['decision']}", flush=True)
    with open("/opt/carebridge/lang_eval.json", "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
print("DONE", flush=True)
