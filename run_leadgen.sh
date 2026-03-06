#!/usr/bin/env bash
set -euo pipefail
BASE_DIR="/root/.openclaw/workspace/leadgen"
OUT_DIR="$BASE_DIR/out"
mkdir -p "$OUT_DIR"
cd "$BASE_DIR"
python3 leadgen_tavily.py \
  --queries-file queries.txt \
  --include-file include_keywords.txt \
  --exclude-file exclude_keywords.txt \
  --blocked-domains-file blocked_domains.txt \
  --max-results 5 \
  --max-queries 25 \
  --out-dir "$OUT_DIR"
