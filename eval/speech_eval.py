"""Speech and language-detection test. A native macOS voice speaks three patient phrases per language;
the server must detect the right language (among all speech languages) and transcribe the words.

Usage: SSL_CERT_FILE=/etc/ssl/cert.pem .venv-local/bin/python eval/speech_eval.py <app-url> <staff-code>
Writes eval/speech_results.json. Languages without a Mac voice cannot be tested here."""
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from server import phrasebank as pb  # noqa: E402

VOICES = {"ar": "Majed", "bg": "Daria", "bn": "Piya", "de": "Anna", "es": "Mónica", "fr": "Jacques", "hi": "Lekha",
          "hu": "Tünde", "it": "Alice", "ko": "Yuna", "lt": "Ona", "pl": "Zosia", "pt": "Luciana", "ro": "Ioana",
          "ru": "Milena", "sk": "Laura", "tr": "Yelda", "uk": "Lesya", "vi": "Linh", "zh": "Tingting", "en": "Moira"}


def norm(s):
    s = unicodedata.normalize("NFKC", s.lower())
    return re.sub(r"[\W_]+", "", s)


def cer(ref, hyp):
    r, h = norm(ref), norm(hyp)
    if not r:
        return 0.0
    prev = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        cur = [i]
        for j, hc in enumerate(h, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rc != hc)))
        prev = cur
    return prev[-1] / len(r)


def main():
    base, code = sys.argv[1].rstrip("/"), sys.argv[2]
    req = urllib.request.Request(base + "/api/login", data=json.dumps({"name": "Speech test", "code": code}).encode(),
                                 headers={"Content-Type": "application/json"})
    tok = json.loads(urllib.request.urlopen(req, timeout=30).read())["token"]
    speech_langs = [c for c, v in pb._CATALOGUE.items() if v[3] and c in pb.LANGUAGES]   # ignore earlier speech results

    def transcribe(wav, lang=None):
        bnd = uuid.uuid4().hex
        parts = [f'--{bnd}\r\nContent-Disposition: form-data; name="audio"; filename="a.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode() + wav + b"\r\n"]
        fields = {"lang": lang} if lang else {"candidates": ",".join(speech_langs)}
        for k, v in fields.items():
            parts.append(f'--{bnd}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
        body = b"".join(parts) + f"--{bnd}--\r\n".encode()
        r = urllib.request.Request(base + "/api/transcribe", data=body, headers={
            "Authorization": f"Bearer {tok}", "Content-Type": f"multipart/form-data; boundary={bnd}"})
        return json.loads(urllib.request.urlopen(r, timeout=60).read())

    results = {}
    tmp = tempfile.mkdtemp()
    for lang, voice in VOICES.items():
        texts = [pb.phrase("r_pain", lang) or pb.PHRASES["r_pain"]["en"],
                 pb.phrase("r_water", lang) or pb.PHRASES["r_water"]["en"],
                 pb.PAIN_TEMPLATE.get(lang, pb.PAIN_TEMPLATE["en"]).format(n=7)]
        if lang == "en":
            texts = ["Is the pain at you?", "Take two paracetamol tablets every six hours.", "Have you any allergies?"]
        det_ok, cers, ms = 0, [], []
        for i, t in enumerate(texts):
            aiff, wav = os.path.join(tmp, f"{lang}{i}.aiff"), os.path.join(tmp, f"{lang}{i}.wav")
            subprocess.run(["say", "-v", voice, "-o", aiff, t], check=True)
            subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", aiff, wav], check=True)
            data = open(wav, "rb").read()
            try:
                auto = transcribe(data)
                fixed = transcribe(data, lang)
            except Exception as e:  # noqa: BLE001
                print(f"  {lang} clip {i} failed: {e}", flush=True)
                continue
            det_ok += auto["lang"] == lang
            if i < 2:   # the third phrase has a number, which may be written as a word: detection only
                cers.append(cer(t, fixed["text"]))
            ms.append(auto["ms"])
            print(f"  {lang} detect={auto['lang']}({auto['langConfidence']}) cer={cers[-1]:.2f} :: {fixed['text']}", flush=True)
        if not cers:
            continue
        results[lang] = {"detected": det_ok, "of": len(texts), "cer": round(sum(cers) / len(cers), 3),
                         "msAuto": round(sum(ms) / len(ms))}
        print(f"{lang:3} detection {det_ok}/{len(texts)}  CER {results[lang]['cer']:.2f}  {results[lang]['msAuto']} ms", flush=True)
    with open(os.path.join(HERE, "speech_results.json"), "w") as f:
        json.dump(results, f, indent=1)


if __name__ == "__main__":
    main()
