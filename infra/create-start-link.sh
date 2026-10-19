#!/bin/bash
# Creates the "start link": a web address that starts the server when it has been auto-stopped. Safe to re-run.
set -euo pipefail
source "$(dirname "$0")/common.sh"
HERE="$(cd "$(dirname "$0")" && pwd)"
STATE=$CB_HOME/state.env; source "$STATE"; source "$CB_HOME/secrets.env"
save() { grep -v "^$1=" "$STATE" > "$STATE.tmp" || true; echo "$1=$2" >> "$STATE.tmp"; mv "$STATE.tmp" "$STATE"; export "$1=$2"; }
if [ -z "${START_KEY:-}" ]; then echo "START_KEY=$(openssl rand -hex 12)" >> "$CB_HOME/secrets.env"; source "$CB_HOME/secrets.env"; fi
if ! aws iam get-role --role-name carebridge-start >/dev/null 2>&1; then
  aws iam create-role --role-name carebridge-start --assume-role-policy-document \
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
  aws iam attach-role-policy --role-name carebridge-start --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
  sleep 12
fi
aws iam put-role-policy --role-name carebridge-start --policy-name start-server --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[
    {\"Effect\":\"Allow\",\"Action\":\"ec2:StartInstances\",\"Resource\":\"arn:aws:ec2:*:$ACCOUNT_ID:instance/*\",\"Condition\":{\"StringEquals\":{\"aws:ResourceTag/Project\":\"CareBridge\"}}},
    {\"Effect\":\"Allow\",\"Action\":\"ec2:DescribeInstances\",\"Resource\":\"*\"}]}"
ZIP=$(mktemp -d)/fn.zip; (cd "$HERE/start-link" && python3 -c "import zipfile,sys;z=zipfile.ZipFile(sys.argv[1],'w');z.write('lambda_function.py')" "$ZIP")
ENVV="Variables={INSTANCE_ID=$INSTANCE_ID,APP_URL=$APP_URL,START_KEY=$START_KEY}"
if aws lambda get-function --function-name carebridge-start >/dev/null 2>&1; then
  aws lambda update-function-code --function-name carebridge-start --zip-file "fileb://$ZIP" >/dev/null
  aws lambda wait function-updated --function-name carebridge-start
  aws lambda update-function-configuration --function-name carebridge-start --environment "$ENVV" >/dev/null
else
  aws lambda create-function --function-name carebridge-start --runtime python3.12 --handler lambda_function.lambda_handler \
    --role "arn:aws:iam::$ACCOUNT_ID:role/carebridge-start" --zip-file "fileb://$ZIP" --timeout 10 --environment "$ENVV" >/dev/null
  aws lambda wait function-active --function-name carebridge-start
  aws lambda create-function-url-config --function-name carebridge-start --auth-type NONE >/dev/null
  aws lambda add-permission --function-name carebridge-start --statement-id public-url --action lambda:InvokeFunctionUrl \
    --principal '*' --function-url-auth-type NONE >/dev/null
  aws lambda add-permission --function-name carebridge-start --statement-id public-invoke --action lambda:InvokeFunction \
    --principal '*' --invoked-via-function-url >/dev/null 2>&1 || true
fi
URL=$(aws lambda get-function-url-config --function-name carebridge-start --query FunctionUrl --output text)
save START_URL "${URL}?key=$START_KEY"
echo "Start link: ${URL}?key=$START_KEY"
