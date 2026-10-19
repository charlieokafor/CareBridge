#!/bin/bash
# Creates the CareBridge AWS resources in a standard AWS account (region from $CB_REGION, default eu-west-1).
# Safe to re-run: anything already recorded in $CB_HOME/state.env is skipped.
set -euo pipefail
source "$(dirname "$0")/common.sh"

HERE="$(cd "$(dirname "$0")" && pwd)"
STATE=$CB_HOME/state.env
SECRETS=$CB_HOME/secrets.env
touch "$STATE"; source "$STATE"
save() { grep -v "^$1=" "$STATE" > "$STATE.tmp" || true; echo "$1=$2" >> "$STATE.tmp"; mv "$STATE.tmp" "$STATE"; export "$1=$2"; }
TAGS="Key=Project,Value=CareBridge"

# Secrets for the app (staff sign-in code, token signing key, API Gateway -> server shared secret)
if [ ! -f "$SECRETS" ]; then
  ( umask 077
    echo "STAFF_CODE=$(LC_ALL=C tr -dc 0-9 </dev/urandom | head -c6)" > "$SECRETS"
    echo "TOKEN_SECRET=$(openssl rand -hex 32)" >> "$SECRETS"
    echo "ORIGIN_SECRET=$(openssl rand -hex 24)" >> "$SECRETS" )
fi
source "$SECRETS"

# SSH key (backup access to the server)
if [ -z "${KEY_NAME:-}" ]; then
  ( umask 077; aws ec2 create-key-pair --key-name carebridge-key --key-type ed25519 \
      --query KeyMaterial --output text > $CB_HOME/carebridge-key.pem )
  save KEY_NAME carebridge-key
fi

# Firewall: app port open (API Gateway reaches it; requests without the shared secret are refused),
# SSH only from this laptop's current IP.
VPC_ID=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)
if [ -z "${SG_ID:-}" ]; then
  SG=$(aws ec2 create-security-group --group-name carebridge-sg --description "CareBridge app server" \
        --vpc-id "$VPC_ID" --query GroupId --output text)
  aws ec2 authorize-security-group-ingress --group-id "$SG" --protocol tcp --port 8080 --cidr 0.0.0.0/0 >/dev/null
  aws ec2 authorize-security-group-ingress --group-id "$SG" --protocol tcp --port 22 \
      --cidr "$(curl -s https://checkip.amazonaws.com)/32" >/dev/null
  save SG_ID "$SG"
fi

# S3: exported patient-record documents and deploy bundles (private)
if [ -z "${BUCKET:-}" ]; then
  B="carebridge-$ACCOUNT_ID-$(openssl rand -hex 3)"
  if [ "$REGION" = us-east-1 ]; then aws s3api create-bucket --bucket "$B" >/dev/null
  else aws s3api create-bucket --bucket "$B" --create-bucket-configuration LocationConstraint="$REGION" >/dev/null; fi
  aws s3api put-public-access-block --bucket "$B" --public-access-block-configuration \
      BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
  aws s3api put-bucket-encryption --bucket "$B" --server-side-encryption-configuration \
      '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
  save BUCKET "$B"
fi

# DynamoDB: sessions, turns and audit events (single table; encrypted at rest by default)
if [ -z "${TABLE:-}" ]; then
  aws dynamodb create-table --table-name carebridge \
      --attribute-definitions AttributeName=pk,AttributeType=S AttributeName=sk,AttributeType=S \
      --key-schema AttributeName=pk,KeyType=HASH AttributeName=sk,KeyType=RANGE \
      --billing-mode PAY_PER_REQUEST --tags "$TAGS" >/dev/null
  save TABLE carebridge
fi

# IAM role for the server (Learner Lab provided LabRole; a normal account needs its own):
# Systems Manager for remote commands, plus this app's DynamoDB table and S3 bucket only.
if [ -z "${PROFILE:-}" ]; then
  aws iam get-role --role-name carebridge-server >/dev/null 2>&1 || aws iam create-role --role-name carebridge-server --assume-role-policy-document \
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
  aws iam attach-role-policy --role-name carebridge-server --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
  aws iam put-role-policy --role-name carebridge-server --policy-name carebridge-data --policy-document "{
    \"Version\":\"2012-10-17\",\"Statement\":[
     {\"Effect\":\"Allow\",\"Action\":[\"dynamodb:*Item\",\"dynamodb:Query\",\"dynamodb:Scan\",\"dynamodb:Batch*\",\"dynamodb:DescribeTable\"],
      \"Resource\":\"arn:aws:dynamodb:*:$ACCOUNT_ID:table/$TABLE\"},
     {\"Effect\":\"Allow\",\"Action\":[\"s3:GetObject\",\"s3:PutObject\",\"s3:ListBucket\"],
      \"Resource\":[\"arn:aws:s3:::carebridge-$ACCOUNT_ID-*\",\"arn:aws:s3:::carebridge-$ACCOUNT_ID-*/*\"]}]}"
  if ! aws iam get-instance-profile --instance-profile-name carebridge-server >/dev/null 2>&1; then
    aws iam create-instance-profile --instance-profile-name carebridge-server >/dev/null
    aws iam add-role-to-instance-profile --instance-profile-name carebridge-server --role-name carebridge-server
  fi
  # Managed speech/translation services, for comparing with (or switching to) the self-hosted models
  aws iam put-role-policy --role-name carebridge-server --policy-name carebridge-aws-ai --policy-document \
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["translate:TranslateText","polly:SynthesizeSpeech","polly:DescribeVoices","transcribe:StartStreamTranscription","transcribe:StartStreamTranscriptionWebSocket"],"Resource":"*"}]}'
  sleep 15   # IAM propagation
  save PROFILE carebridge-server
fi

# EC2 server (default m7i-flex.large = 2 vCPU / 8 GB; override with CB_INSTANCE_TYPE)
if [ -z "${INSTANCE_ID:-}" ]; then
  AMI=$(aws ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
        --query Parameter.Value --output text)
  IID=$(aws ec2 run-instances --image-id "$AMI" --instance-type "${CB_INSTANCE_TYPE:-m7i-flex.large}" --key-name "$KEY_NAME" \
        --security-group-ids "$SG_ID" --iam-instance-profile Name="$PROFILE" \
        --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=40,VolumeType=gp3,DeleteOnTermination=true}' \
        --user-data "file://$HERE/ec2-setup.sh" \
        --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=carebridge-server},{$TAGS}]" \
        --query 'Instances[0].InstanceId' --output text)
  save INSTANCE_ID "$IID"
fi

# Fixed public address so the website survives the lab stopping/starting the server
if [ -z "${EIP_ALLOC:-}" ]; then
  read -r ALLOC IP < <(aws ec2 allocate-address --domain vpc --query '[AllocationId,PublicIp]' --output text)
  save EIP_ALLOC "$ALLOC"; save EIP "$IP"
fi
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
aws ec2 associate-address --instance-id "$INSTANCE_ID" --allocation-id "$EIP_ALLOC" >/dev/null

# API Gateway: the public https:// address. Adds the shared-secret header the server requires.
if [ -z "${API_ID:-}" ]; then
  API=$(aws apigatewayv2 create-api --name carebridge --protocol-type HTTP --tags Project=CareBridge \
        --query ApiId --output text)
  PARAMS="{\"overwrite:header.x-cb-origin\":\"$ORIGIN_SECRET\"}"
  INT_PROXY=$(aws apigatewayv2 create-integration --api-id "$API" --integration-type HTTP_PROXY \
        --integration-method ANY --integration-uri "http://$EIP:8080/{proxy}" --payload-format-version 1.0 \
        --timeout-in-millis 30000 --request-parameters "$PARAMS" --query IntegrationId --output text)
  INT_ROOT=$(aws apigatewayv2 create-integration --api-id "$API" --integration-type HTTP_PROXY \
        --integration-method ANY --integration-uri "http://$EIP:8080/" --payload-format-version 1.0 \
        --timeout-in-millis 30000 --request-parameters "$PARAMS" --query IntegrationId --output text)
  aws apigatewayv2 create-route --api-id "$API" --route-key 'ANY /{proxy+}' --target "integrations/$INT_PROXY" >/dev/null
  aws apigatewayv2 create-route --api-id "$API" --route-key 'ANY /' --target "integrations/$INT_ROOT" >/dev/null
  aws apigatewayv2 create-stage --api-id "$API" --stage-name '$default' --auto-deploy >/dev/null
  save API_ID "$API"
  save APP_URL "https://$API.execute-api.$REGION.amazonaws.com"
fi

echo "Done."
echo "  Server:  $INSTANCE_ID  ($EIP)"
echo "  Website: $APP_URL"
echo "  Table:   $TABLE   Bucket: $BUCKET"
