#!/bin/bash
# Runs ON THE SERVER (via infra/remote.sh): downloads natural Piper voices and Meta MMS-TTS voices so every
# licensed language has a server voice. Safe to re-run. Log: /var/log/carebridge-voices.log
set -u
exec > >(tee -a /var/log/carebridge-voices.log) 2>&1
ROOT=/opt/carebridge
. $ROOT/venv/bin/activate
pip install --quiet uroman==1.3.1.1 || pip install --quiet uroman || echo "uroman install failed"
BASE=https://huggingface.co/rhasspy/piper-voices/resolve/main
for v in fr/fr_FR/siwis/medium/fr_FR-siwis-medium es/es_ES/davefx/medium/es_ES-davefx-medium \
         de/de_DE/thorsten/medium/de_DE-thorsten-medium it/it_IT/paola/medium/it_IT-paola-medium \
         pt/pt_BR/faber/medium/pt_BR-faber-medium sk/sk_SK/lili/medium/sk_SK-lili-medium \
         hu/hu_HU/anna/medium/hu_HU-anna-medium tr/tr_TR/dfki/medium/tr_TR-dfki-medium \
         vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium sw/sw_CD/lanfrica/medium/sw_CD-lanfrica-medium; do
  f=$(basename $v)
  [ -s $ROOT/models/voices/$f.onnx ] && continue
  curl -sfL -o $ROOT/models/voices/$f.onnx "$BASE/$v.onnx" && curl -sfL -o $ROOT/models/voices/$f.onnx.json "$BASE/$v.onnx.json" \
    && echo "piper ok $f" || { echo "piper missing $f"; rm -f $ROOT/models/voices/$f.onnx*; }
done
HF_HOME=$ROOT/models/hf python - <<'PY'
import os
from huggingface_hub import snapshot_download
MMS = {"ga": "gle", "ko": "kor", "ur": "urd-script_arabic", "bn": "ben", "pa": "pan", "ps": "pbu", "so": "som",
       "ig": "ibo", "sq": "sqi", "lt": "lit", "tl": "tgl", "bg": "bul", "hi": "hin"}
piper = {"fr", "es", "de", "it", "pt", "sk", "hu", "tr", "vi", "sw"}
fallback = {"hu": "hun", "sk": "slk", "tr": "tur", "vi": "vie", "sw": "swh", "fr": "fra", "es": "spa", "de": "deu",
            "it": "ita", "pt": "por"}
for lang, code in fallback.items():   # MMS only where the Piper voice failed to download
    if not any(f.startswith({"fr": "fr_FR", "es": "es_ES", "de": "de_DE", "it": "it_IT", "pt": "pt_BR", "sk": "sk_SK",
                             "hu": "hu_HU", "tr": "tr_TR", "vi": "vi_VN", "sw": "sw_CD"}[lang]) and f.endswith(".onnx")
               for f in os.listdir("/opt/carebridge/models/voices")):
        MMS[lang] = code
for lang, code in MMS.items():
    dest = f"/opt/carebridge/models/mms/{lang}"
    if os.path.exists(f"{dest}/config.json"):
        continue
    try:
        snapshot_download(f"facebook/mms-tts-{code}", local_dir=dest, allow_patterns=["*.json", "*.safetensors", "*.bin", "*.txt", "*.model"])
        print("mms ok", lang, code, flush=True)
    except Exception as e:
        print("mms missing", lang, code, type(e).__name__, flush=True)
PY
echo VOICES_DONE
