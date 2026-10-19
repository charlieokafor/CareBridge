#!/bin/bash
# EC2 user-data: installs the CareBridge model server (runs once, as root, on first boot).
# Speech-to-text: faster-whisper. Translation: NLLB-200 via CTranslate2. Meaning check: multilingual MiniLM.
# Voices: Piper (best effort). Log: /var/log/carebridge-setup.log
set -uxo pipefail
exec > >(tee -a /var/log/carebridge-setup.log) 2>&1

ROOT=/opt/carebridge
mkdir -p $ROOT/app $ROOT/models/voices
export HF_HOME=$ROOT/models/hf

# Swap so the translation-model conversion fits in 8 GB of RAM.
if [ ! -f /swapfile ]; then
  fallocate -l 6G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

dnf install -y python3.11 python3.11-pip python3.11-devel gcc-c++ git

python3.11 -m venv $ROOT/venv
. $ROOT/venv/bin/activate
pip install --upgrade pip wheel setuptools
pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
pip install numpy==1.26.4 transformers==4.46.3 huggingface_hub==0.26.5 sentencepiece==0.2.0 protobuf==5.28.3 \
  ctranslate2==4.5.0 faster-whisper==1.1.0 sentence-transformers==3.3.1 \
  fastapi==0.115.6 "uvicorn[standard]==0.32.1" python-multipart==0.0.19 boto3 wordfreq==3.1.1 opencc-python-reimplemented==0.1.7
touch $ROOT/STEP_PIP_DONE

# Translation model -> CTranslate2 int8
if [ ! -f $ROOT/models/nllb-600m/model.bin ]; then
  ct2-transformers-converter --model facebook/nllb-200-distilled-600M \
    --output_dir $ROOT/models/nllb-600m --quantization int8 --force
fi
python - <<'PY'
from transformers import AutoTokenizer
AutoTokenizer.from_pretrained("facebook/nllb-200-distilled-600M")
PY
# Larger translation model: lang_licence.json assigns it to pl, ro, ar, ga, ko and es (the app silently falls back to
# 600M when it is missing). Conversion needs the swap file above.
if [ ! -f $ROOT/models/nllb-1.3b/model.bin ]; then
  ct2-transformers-converter --model facebook/nllb-200-distilled-1.3B \
    --output_dir $ROOT/models/nllb-1.3b --quantization int8 --force || echo "nllb-1.3b conversion failed"
fi
touch $ROOT/STEP_NLLB_DONE

# Speech-to-text models
python - <<'PY'
from faster_whisper import WhisperModel
for size in ("small", "base"):
    WhisperModel(size, device="cpu", compute_type="int8", download_root="/opt/carebridge/models/whisper")
PY
touch $ROOT/STEP_WHISPER_DONE

# Meaning-check model
python - <<'PY'
from sentence_transformers import SentenceTransformer
SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
PY
touch $ROOT/STEP_ST_DONE

# Voices (best effort; the app falls back to the device's own voice)
pip install piper-tts==1.2.0 || echo "piper install failed"
BASE=https://huggingface.co/rhasspy/piper-voices/resolve/main
for v in uk/uk_UA/ukrainian_tts/medium/uk_UA-ukrainian_tts-medium \
         ru/ru_RU/irina/medium/ru_RU-irina-medium \
         pl/pl_PL/gosia/medium/pl_PL-gosia-medium \
         ro/ro_RO/mihai/medium/ro_RO-mihai-medium \
         ar/ar_JO/kareem/medium/ar_JO-kareem-medium \
         en/en_GB/alba/medium/en_GB-alba-medium \
         el/el_GR/rapunzelina/low/el_GR-rapunzelina-low \
         cs/cs_CZ/jirka/medium/cs_CZ-jirka-medium; do
  f=$(basename $v)
  curl -sfL -o $ROOT/models/voices/$f.onnx "$BASE/$v.onnx" || echo "voice $f failed"
  curl -sfL -o $ROOT/models/voices/$f.onnx.json "$BASE/$v.onnx.json" || true
done
touch $ROOT/STEP_VOICES_DONE

cat > /etc/systemd/system/carebridge.service <<'EOF'
[Unit]
Description=CareBridge app and model server
After=network-online.target
Wants=network-online.target
ConditionPathExists=/opt/carebridge/app/server/main.py

[Service]
WorkingDirectory=/opt/carebridge/app
EnvironmentFile=-/opt/carebridge/app.env
Environment=HF_HOME=/opt/carebridge/models/hf
Environment=HF_HUB_OFFLINE=1
Environment=OMP_NUM_THREADS=2
ExecStart=/opt/carebridge/venv/bin/uvicorn server.main:app --host 0.0.0.0 --port 8080 --workers 1
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable carebridge.service
chown -R ec2-user:ec2-user $ROOT/app

# Cost guard: stop the server 3 hours after each start (same as infra/autostop.sh; AUTOSTOP_HOURS=0 turns it off).
# Only the timer starts the stop service: the service itself must never be enabled at boot.
HOURS=${AUTOSTOP_HOURS:-3}
rm -f /etc/systemd/system/multi-user.target.wants/carebridge-autostop.service
if [ "$HOURS" != 0 ]; then
cat > /etc/systemd/system/carebridge-autostop.service <<UNIT
[Unit]
Description=Stop the CareBridge server to save money
[Service]
Type=oneshot
ExecStart=/usr/bin/logger "CareBridge auto-stop: shutting down after ${HOURS}h"
ExecStart=/usr/bin/systemctl poweroff
UNIT
cat > /etc/systemd/system/carebridge-autostop.timer <<UNIT
[Unit]
Description=Stop the CareBridge server ${HOURS} hours after it starts
[Timer]
OnBootSec=${HOURS}h
AccuracySec=1min
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload && systemctl enable --now carebridge-autostop.timer
echo "auto-stop: ${HOURS}h after boot"
fi

touch $ROOT/SETUP_DONE
echo "CareBridge setup finished"
