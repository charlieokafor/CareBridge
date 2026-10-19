#!/bin/bash
# Deploys the CareBridge app code to the EC2 server and restarts it.
# Goes through S3 + Systems Manager, so it works on Wi-Fi that blocks SSH.
# Usage: infra/deploy.sh [nllb-600m|nllb-1.3b]
set -euo pipefail
source "$(dirname "$0")/common.sh"
source $CB_HOME/state.env
source $CB_HOME/secrets.env
HERE="$(cd "$(dirname "$0")/.." && pwd)"
NLLB="${1:-nllb-600m}"
TOKENIZER="facebook/nllb-200-distilled-600M"; [ "$NLLB" = "nllb-1.3b" ] && TOKENIZER="facebook/nllb-200-distilled-1.3B"

# Bundle = code + server settings (secrets travel inside the private, encrypted bucket, never in the command)
BUILD="$(mktemp -d)"
trap 'rm -rf "$BUILD"' EXIT
mkdir -p "$BUILD/app"
cp -R "$HERE/server" "$HERE/web" "$BUILD/app/"
find "$BUILD/app" \( -name __pycache__ -o -name .DS_Store \) -prune -exec rm -rf {} +
( umask 077; cat > "$BUILD/app.env" <<ENV
STAFF_CODE=$STAFF_CODE
TOKEN_SECRET=$TOKEN_SECRET
ORIGIN_SECRET=$ORIGIN_SECRET
CB_TABLE=$TABLE
CB_BUCKET=$BUCKET
AWS_REGION=$REGION
AWS_DEFAULT_REGION=$REGION
CB_NLLB=$NLLB
CB_ENGINE=${CB_ENGINE:-aws}
CB_AWS_REGION=$REGION
CB_NLLB_TOKENIZER=$TOKENIZER
ENV
)
COPYFILE_DISABLE=1 tar -C "$BUILD" -czf "$BUILD/bundle.tgz" app app.env
aws s3 cp "$BUILD/bundle.tgz" "s3://$BUCKET/deploy/bundle.tgz" --only-show-errors

"$HERE/infra/remote.sh" "set -e
aws s3 cp s3://$BUCKET/deploy/bundle.tgz /tmp/bundle.tgz --region $REGION --only-show-errors
rm -rf /tmp/cb && mkdir -p /tmp/cb && tar -xzf /tmp/bundle.tgz -C /tmp/cb
/opt/carebridge/venv/bin/python -m compileall -q /tmp/cb/app/server >/dev/null || { echo 'Python syntax error: not deployed'; exit 1; }
rsync -a --delete /tmp/cb/app/ /opt/carebridge/app/
install -m 600 /tmp/cb/app.env /opt/carebridge/app.env
rm -rf /tmp/cb /tmp/bundle.tgz
systemctl daemon-reload && systemctl restart carebridge
echo restarted" 120

echo "Deployed ($NLLB). Waiting for the models to load..."
for _ in $(seq 1 60); do
  out=$(curl -s --max-time 5 "$APP_URL/api/health" || true)
  if echo "$out" | grep -q '"ready":true'; then echo "$out"; echo "Live at $APP_URL"; exit 0; fi
  sleep 5
done
echo "Server not ready yet. Last health: $out"
