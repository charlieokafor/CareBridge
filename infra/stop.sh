#!/bin/bash
# Stops the CareBridge server now (nothing is lost; start it again with infra/start.sh).
set -euo pipefail
source "$(dirname "$0")/common.sh"; source "$CB_HOME/state.env"
aws ec2 stop-instances --instance-ids "$INSTANCE_ID" >/dev/null && echo "Stopping $INSTANCE_ID"
