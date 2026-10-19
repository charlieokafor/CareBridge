#!/bin/bash
# Shared settings for the infra scripts (replaces the Learner Lab env.sh/labcheck).
# Secrets and resource IDs live in $CB_HOME (default ~/carebridge-aws), never in this repo.
# Use only the credentials from aws configure / AWS_PROFILE, not stray environment keys.
[ -n "${CB_KEEP_ENV_CREDS:-}" ] || unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
export CB_HOME="${CB_HOME:-$HOME/carebridge-aws}"
mkdir -p "$CB_HOME"; chmod 700 "$CB_HOME"
export REGION="${CB_REGION:-eu-west-1}"
export AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) \
  || { echo "AWS credentials not working: run 'aws configure' (or set AWS_PROFILE) first."; exit 1; }
export ACCOUNT_ID
