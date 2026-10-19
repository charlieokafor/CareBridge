#!/bin/bash
# Runs a shell command on the CareBridge server through AWS Systems Manager (no SSH needed,
# works on Wi-Fi that blocks port 22). Usage: infra/remote.sh 'command' [timeout-seconds]
set -euo pipefail
source "$(dirname "$0")/common.sh"
source $CB_HOME/state.env
CMD="$1"; WAIT="${2:-120}"
PARAMS=$(python3 -c 'import json,sys; print(json.dumps({"commands": [sys.argv[1]], "executionTimeout": [sys.argv[2]]}))' "$CMD" "$WAIT")
CID=$(aws ssm send-command --instance-ids "$INSTANCE_ID" --document-name AWS-RunShellScript \
      --parameters "$PARAMS" --query Command.CommandId --output text)
for _ in $(seq 1 $((WAIT / 2 + 5))); do
  sleep 2
  STATUS=$(aws ssm get-command-invocation --command-id "$CID" --instance-id "$INSTANCE_ID" --query Status --output text 2>/dev/null || echo Pending)
  case "$STATUS" in Pending|InProgress|Delayed) continue ;; esac
  aws ssm get-command-invocation --command-id "$CID" --instance-id "$INSTANCE_ID" --query StandardOutputContent --output text
  ERR=$(aws ssm get-command-invocation --command-id "$CID" --instance-id "$INSTANCE_ID" --query StandardErrorContent --output text)
  [ -n "$ERR" ] && [ "$ERR" != "None" ] && echo "--- stderr ---" && echo "$ERR"
  [ "$STATUS" = "Success" ] && exit 0 || { echo "($STATUS)"; exit 1; }
done
echo "Timed out waiting for the command ($CID)"; exit 1
