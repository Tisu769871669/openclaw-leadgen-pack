# OpenClaw Leadgen Refactor Pack

This directory now contains the refactored leadgen workflow as an OpenClaw skill package.

## Primary package

- `openclaw-leadgen/`
  - `SKILL.md`: agent instructions for the leadgen workflow
  - `scripts/bootstrap_workspace.py`: create `config/`, `input/`, and `out/`
  - `scripts/collect_bing_results.py`: use OpenClaw browser plus local Chrome to collect Bing results
  - `scripts/filter_search_results.py`: score and filter raw local browser search results
  - `scripts/postprocess_contact_top20.py`: contact-signal filter plus root-domain dedup
  - `scripts/run_pipeline.py`: run the pipeline end to end
  - `assets/*.txt`: default query seeds and include/exclude/block lists

## Installation target

- Skill directory: `~/.openclaw/skills/openclaw-leadgen`
- Suggested dedicated agent workspace: `~/.openclaw/workspace-leadgen`

## Install on an OpenClaw server

Upload this folder to the target machine, then run:

```bash
bash ./install_skill_on_server.sh leadgen
```

The install script:

- copies `openclaw-leadgen/` into `~/.openclaw/skills/openclaw-leadgen`
- bootstraps the workspace with `config/`, `input/`, and `out/`
- tries to create an isolated OpenClaw agent with the provided name

## Tokyo server note

The Tokyo server already has headless Chrome available at `/usr/bin/google-chrome`.

- Prefer browser-driven Bing collection for this refactor.
- Treat `~/.openclaw/workspace/skills/tavily-search` as legacy.
- Keep Tavily out of the new leadgen skill unless you intentionally want a fallback path.

Optional environment variables:

- `OPENCLAW_HOME`
- `OPENCLAW_SKILLS_DIR`
- `LEADGEN_WORKSPACE`
- `LEADGEN_AGENT_MODEL`

## Runtime flow

1. Use the built-in collector to fetch Bing results with the local OpenClaw browser and Chrome:

```bash
python3 ~/.openclaw/skills/openclaw-leadgen/scripts/collect_bing_results.py --workspace-root ~/.openclaw/workspace-leadgen
```

2. Or run collection plus filtering in one step:

```bash
python3 ~/.openclaw/skills/openclaw-leadgen/scripts/run_pipeline.py --workspace-root ~/.openclaw/workspace-leadgen --collect-bing
```

3. If you want the `leadgen` subagent itself to collect data with the local browser, run:

```bash
python3 ~/.openclaw/skills/openclaw-leadgen/scripts/run_pipeline.py --workspace-root ~/.openclaw/workspace-leadgen --collect-via-agent
```

4. If you already have raw search results, save them to `input/search_results.jsonl` inside the leadgen agent workspace and run:

```bash
python3 ~/.openclaw/skills/openclaw-leadgen/scripts/run_pipeline.py --workspace-root ~/.openclaw/workspace-leadgen
```

5. Review outputs in `out/`:
   - `latest_leads.csv`
   - `latest_leads.jsonl`
   - `latest_summary.md`
   - `contact_ready_top20_latest.csv`
   - `contact_ready_top20_latest.md`
   - `bing-debug/` when Bing extraction returns zero results

## Input schema

Each JSONL line should look like:

```json
{"query":"used rolex in stock shop","title":"Example Dealer","url":"https://example.com","snippet":"Pre-owned Rolex inventory with WhatsApp contact","source":"google","position":1}
```

Required fields:

- `query`
- `title`
- `url`
- `snippet`

Optional fields:

- `source`
- `position`
- `collected_at`

## Legacy files kept for reference

These older Tavily-based files are still here for comparison and migration reference:

- `leadgen_tavily.py`
- `postprocess_contact_top20.py`
- `run_leadgen.sh`
- `install_on_server.sh`

They are no longer the preferred path for the refactored workflow.
