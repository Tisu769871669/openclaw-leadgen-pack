#!/usr/bin/env bash
set -euo pipefail
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
DST_DIR="/root/.openclaw/workspace/leadgen"
mkdir -p "$DST_DIR/out"
cp -f "$SRC_DIR/leadgen_tavily.py" "$DST_DIR/leadgen_tavily.py"
cp -f "$SRC_DIR/postprocess_contact_top20.py" "$DST_DIR/postprocess_contact_top20.py"
cp -f "$SRC_DIR/run_leadgen.sh" "$DST_DIR/run_leadgen.sh"
cp -f "$SRC_DIR/queries.txt" "$DST_DIR/queries.txt"
cp -f "$SRC_DIR/include_keywords.txt" "$DST_DIR/include_keywords.txt"
cp -f "$SRC_DIR/exclude_keywords.txt" "$DST_DIR/exclude_keywords.txt"
cp -f "$SRC_DIR/blocked_domains.txt" "$DST_DIR/blocked_domains.txt"
chmod +x "$DST_DIR/leadgen_tavily.py" "$DST_DIR/postprocess_contact_top20.py" "$DST_DIR/run_leadgen.sh"
echo "Installed to $DST_DIR"
