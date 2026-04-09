#!/usr/bin/env bash
set -euo pipefail

AGENT_NAME="${1:-leadgen}"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_SRC="$SRC_DIR/openclaw-leadgen"

OPENCLAW_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
SKILLS_DIR="${OPENCLAW_SKILLS_DIR:-$OPENCLAW_HOME/skills}"
WORKSPACE_ROOT="${LEADGEN_WORKSPACE:-$OPENCLAW_HOME/workspace-leadgen}"
SKILL_DST="$SKILLS_DIR/openclaw-leadgen"

mkdir -p "$SKILL_DST"
cp -R "$SKILL_SRC"/. "$SKILL_DST"/

python3 "$SKILL_DST/scripts/bootstrap_workspace.py" --workspace-root "$WORKSPACE_ROOT"

if [ -x /usr/bin/google-chrome ]; then
  echo "Detected Chrome: $(/usr/bin/google-chrome --version 2>/dev/null || echo /usr/bin/google-chrome)"
  echo "Preferred search path: browser automation against Bing"
fi

if [ -d "$OPENCLAW_HOME/workspace/skills/tavily-search" ]; then
  echo "Legacy Tavily skill detected at: $OPENCLAW_HOME/workspace/skills/tavily-search"
fi

if command -v openclaw >/dev/null 2>&1; then
  AGENTS_JSON="$(openclaw agents list --json)"
  if printf '%s' "$AGENTS_JSON" | python3 -c '
import json
import sys

target = sys.argv[1]
agents = json.load(sys.stdin)
sys.exit(0 if any(agent.get("id") == target for agent in agents) else 1)
' "$AGENT_NAME"
  then
    echo "Agent already exists: $AGENT_NAME"
  else
    ADD_ARGS=(agents add "$AGENT_NAME" --workspace "$WORKSPACE_ROOT" --non-interactive)
    if [ -n "${LEADGEN_AGENT_MODEL:-}" ]; then
      ADD_ARGS+=(--model "$LEADGEN_AGENT_MODEL")
    fi
    openclaw "${ADD_ARGS[@]}"
    echo "Created agent: $AGENT_NAME"
  fi
else
  echo "openclaw CLI not found; skill installed but agent not created"
fi

echo "Installed skill to: $SKILL_DST"
echo "Workspace root: $WORKSPACE_ROOT"
echo "Recommended pipeline command:"
echo "python3 $SKILL_DST/scripts/run_pipeline.py --workspace-root $WORKSPACE_ROOT"
