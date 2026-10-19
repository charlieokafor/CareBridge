#!/bin/bash
# Starts the CareBridge server (it stops itself 4 hours later) and waits until the website answers (~3 min).
set -euo pipefail
source "$(dirname "$0")/common.sh"; source "$CB_HOME/state.env"
aws ec2 start-instances --instance-ids "$INSTANCE_ID" >/dev/null
echo "Starting $INSTANCE_ID..."; aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
for _ in $(seq 1 60); do curl -s --max-time 5 "$APP_URL/api/health" | grep -q '"ready":true' && { echo "Live at $APP_URL (auto-stops in 4 h)"; exit 0; }; sleep 5; done
echo "Server running but app not ready yet; try $APP_URL in a minute."
