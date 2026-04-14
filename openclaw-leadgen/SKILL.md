---
name: openclaw-leadgen
description: Generate non-official dealer leads from local Google or browser search results using reusable query packs, keyword filters, scoring, and contact-ready dedup export. Use when an OpenClaw agent needs to turn manual or local web search results into reseller prospects without Tavily or other hosted search MCPs.
---

# OpenClaw Leadgen

Use this skill inside a dedicated leadgen agent workspace. The skill does not call Tavily. It assumes the agent can search locally with Google or browser tools, then process those results with the bundled scripts.

## Workflow

1. Work in a dedicated agent workspace. Prefer an isolated agent created with `openclaw agents add <agent-name> --workspace <dir>`.
2. Initialize the workspace once:

```bash
python scripts/bootstrap_workspace.py --workspace-root <agent-workspace>
```

This creates `config/`, `input/`, and `out/`, then copies the default query and filter files into `config/`.

It also creates `results/`, `logs/`, and `scripts/` so the workspace can support browser-only daily runs.

3. Collect local search results into `input/search_results.jsonl`.

Preferred production flow:

```bash
python scripts/run_pipeline.py --workspace-root <agent-workspace> --collect-via-agent --collector-search-engine google
```

This uses the `leadgen` subagent plus the OpenClaw `browser` tool and currently matches the validated Tokyo-server setup.

Optional Bing fallback:

```bash
python scripts/run_pipeline.py --workspace-root <agent-workspace> --collect-bing
```

If you want the `leadgen` subagent to do the searching itself and only hand back raw JSONL, run:

```bash
python scripts/run_pipeline.py --workspace-root <agent-workspace> --collect-via-agent
```

The subagent path should work one query at a time and prefer the OpenClaw `browser` tool so the search flow looks closer to a human browsing session.

You can choose the subagent search engine explicitly:

```bash
python scripts/run_pipeline.py --workspace-root <agent-workspace> --collect-via-agent --collector-search-engine google
```

If you need to inject your own search results, each JSONL row should contain:

```json
{"query":"used rolex in stock shop","title":"Example Dealer","url":"https://example.com","snippet":"Pre-owned Rolex inventory and contact details","source":"google","position":1}
```

Required keys are `query`, `title`, `url`, and `snippet`. Optional keys are `source`, `position`, and `collected_at`.

When Chrome is available on the target machine, prefer browser automation against Google over Tavily-based search.

4. Run the pipeline:

```bash
python scripts/run_pipeline.py --workspace-root <agent-workspace>
```

5. Review results in `out/`:
- `latest_leads.csv`
- `latest_leads.jsonl`
- `latest_summary.md`
- `contact_ready_top20_latest.csv`
- `contact_ready_top20_latest.md`

If you want the browser-only daily wrapper, run:

```bash
python scripts/watch_search.py --workspace-root <agent-workspace> --collector-search-engine google --max-queries 3
```

That wrapper keeps the same collection/filtering logic but also writes dated files into `results/` and `logs/`.

## Collection Rules

- Use the seeded searches from `config/queries.txt` unless the user asks for a different market.
- Prefer the `main -> leadgen -> browser -> Google` path on the machine that runs the agent. Use Tavily only if the user explicitly asks for it.
- Prefer organic Google results in the main production flow. Keep Bing only as a fallback path.
- Preserve the search snippet as `snippet`. Do not fetch or scrape full pages before ranking unless the user asks for deeper enrichment.
- Keep one row per search result. Do not merge results from multiple queries before writing JSONL.
- When you adjust targeting, edit the workspace copy in `config/`, not the bundled assets, unless you are intentionally changing the defaults for every future run.

## Bundled Resources

### `scripts/bootstrap_workspace.py`

Create the standard workspace folders and copy default query/filter assets into `config/`.

### `scripts/filter_search_results.py`

Score and filter raw Google/browser search results into lead candidates. This is the replacement for the old Tavily collector.

### `scripts/collect_bing_results.py`

Use the local OpenClaw browser and Chrome to run Bing searches from `config/queries.txt`, then write normalized raw results to `input/search_results.jsonl`. Treat this as a fallback collector rather than the primary path.

### `scripts/collect_via_agent.py`

Send a collection task to a dedicated subagent such as `leadgen`, wait for it to write `input/search_results.jsonl`, then continue the pipeline locally.

### `scripts/watch_search.py`

Run the browser-only workflow in a dated-results mode and emit `results/` plus `logs/` artifacts.

### `scripts/check_status.py`

Read the latest `logs/` and `results/` artifacts so an agent can quickly report current state.

### `scripts/postprocess_contact_top20.py`

Apply contact-signal filtering and root-domain deduplication to produce a contact-ready shortlist.

### `scripts/run_pipeline.py`

Run the filter and postprocess steps in sequence against a workspace.

### `assets/`

Default seeds and filter lists:
- `queries.txt`
- `include_keywords.txt`
- `exclude_keywords.txt`
- `blocked_domains.txt`
- `trade_config.yaml`
- `strategy_log.md`

## Reporting Back

When you finish a run, report:
- Raw search-result row count
- Lead count after filtering
- Contact-ready Top N count
- Any notable gaps in market coverage or keyword quality

## Guardrails

- Do not hardcode bearer tokens, API keys, or remote host credentials into this skill.
- Keep the raw search-result schema stable even if the search method changes.
- If the search environment on the target machine changes, adapt the collection step instead of rewriting the ranking logic.
