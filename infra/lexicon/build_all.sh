#!/bin/bash
# Rebuilds the CareBridge Clinical Lexicon end to end and publishes it. Run from the repo root.
#   1. build_lexicon.py  (on the server: Wikidata via QLever; cached, polite to the public service)
#   2. curate.py         (core medicines, Irish brands, look-alike/sound-alike pairs, lay words, review decisions)
#   3. fill_gaps.py      (missing names in the active languages via Amazon Translate, marked "machine")
#   4. publish: s3://$BUCKET/lexicon/lexicon.json.gz (versioned; the server loads it at start or on reload)
#      + server/data/lexicon.json.gz (bundled fallback) + Transcribe vocabularies / Translate terminology
set -euo pipefail
source "$(dirname "$0")/../common.sh"; source "$CB_HOME/state.env"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; W=$(mktemp -d)
aws s3 sync "$ROOT/infra/lexicon" "s3://$BUCKET/dev/lex/src" --exclude '.cache/*' --only-show-errors
"$ROOT/infra/remote.sh" "aws s3 sync s3://$BUCKET/dev/lex/src /opt/cb-dev/lex/src --region $REGION --only-show-errors && cd /opt/cb-dev/lex/src && /opt/carebridge/venv/bin/python build_lexicon.py /opt/cb-dev/lex/raw.json.gz && aws s3 cp /opt/cb-dev/lex/raw.json.gz s3://$BUCKET/lexicon/raw/lexicon-wikidata.json.gz --region $REGION --only-show-errors" 3000
aws s3 cp "s3://$BUCKET/lexicon/raw/lexicon-wikidata.json.gz" "$W/raw.json.gz" --only-show-errors
python3 "$ROOT/infra/lexicon/curate.py" "$W/raw.json.gz" "$W/curated.json.gz"
python3 "$ROOT/infra/lexicon/fill_gaps.py" "$W/curated.json.gz" "$W/lexicon.json.gz" --region "$REGION"
aws s3 cp "$W/lexicon.json.gz" "s3://$BUCKET/lexicon/lexicon.json.gz" --only-show-errors
cp "$W/lexicon.json.gz" "$ROOT/server/data/lexicon.json.gz"
python3 "$ROOT/infra/build_vocab.py" --region "$REGION"
echo "Lexicon published. Running servers pick it up on restart, or: POST /api/lexicon/reload"
