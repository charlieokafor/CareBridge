"""Generates patient-facing interface text for the machine-translated languages with NLLB-200 on our
server (Amazon Translate since Oct 2026), and merges it to server/phrasebank_auto.json. Run once after adding languages:

    SSL_CERT_FILE=/etc/ssl/cert.pem .venv-local/bin/python eval/build_auto_phrasebank.py <app-url> <staff-code>

The output is labelled machine-translated in the app and is never treated as a pre-checked phrase."""
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from server import phrasebank as pb  # noqa: E402


def main():
    base, code = sys.argv[1].rstrip("/"), sys.argv[2]
    only = sys.argv[3].split(",") if len(sys.argv) > 3 else None     # optional: just these languages

    def post(path, body, tok=None):
        h = {"Content-Type": "application/json", **({"Authorization": f"Bearer {tok}"} if tok else {})}
        req = urllib.request.Request(base + path, data=json.dumps(body).encode(), headers=h)
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())

    tok = post("/api/login", {"name": "Phrasebank builder", "code": code})["token"]
    ui_keys = list(pb.EN_UI)
    phrase_ids = pb.QUICK_REPLIES + pb.CLINICIAN_PHRASES
    texts = [pb.EN_UI[k] for k in ui_keys] + [pb.PHRASES[p]["en"] for p in phrase_ids] + ["My pain is 7 out of 10."]
    path = os.path.join(os.path.dirname(HERE), "server", "phrasebank_auto.json")
    out = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    for lang in pb.PATIENT_LANGS:
        if lang in pb.DRAFTED_LANGS or (only and lang not in only):
            continue
        tr = post("/api/translate-batch", {"texts": texts, "src": "en", "tgt": lang}, tok)["translations"]
        ui = dict(zip(ui_keys, tr[:len(ui_keys)]))
        phrases = dict(zip(phrase_ids, tr[len(ui_keys):len(ui_keys) + len(phrase_ids)]))
        pain = tr[-1]
        pain = pain.replace("7", "{n}", 1) if "7" in pain else "{n}/10"
        out[lang] = {"ui": ui, "phrases": phrases, "pain": pain}
        print(f"{lang:4} {pb.LANGUAGES[lang]['name']:20} {ui['consent_q']}")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"Saved {len(out)} languages to {path}")


if __name__ == "__main__":
    main()
