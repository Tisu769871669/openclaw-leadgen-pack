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

3. Collect local Bing search results into `input/search_results.jsonl`.

Prefer the bundled collector:

```bash
python scripts/collect_bing_results.py --workspace-root <agent-workspace>
```

Or run the full pipeline in one step:

```bash
python scripts/run_pipeline.py --workspace-root <agent-workspace> --collect-bing
```

If you need to inject your own search results, each JSONL row should contain:

```json
{"query":"used rolex in stock shop","title":"Example Dealer","url":"https://example.com","snippet":"Pre-owned Rolex inventory and contact details","source":"google","position":1}
```

Required keys are `query`, `title`, `url`, and `snippet`. Optional keys are `source`, `position`, and `collected_at`.

When Chrome is available on the target machine, prefer browser automation against Bing over Tavily-based search.

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

## Collection Rules

- Use the seeded searches from `config/queries.txt` unless the user asks for a different market.
- Prefer the local browser path on the machine that runs the agent. Use Tavily only if the user explicitly asks for it.
- Prefer organic Bing results. Do not include forums, social feeds, or marketplaces unless the user explicitly wants them.
- Preserve the search snippet as `snippet`. Do not fetch or scrape full pages before ranking unless the user asks for deeper enrichment.
- Keep one row per search result. Do not merge results from multiple queries before writing JSONL.
- When you adjust targeting, edit the workspace copy in `config/`, not the bundled assets, unless you are intentionally changing the defaults for every future run.

## Bundled Resources

### `scripts/bootstrap_workspace.py`

Create the standard workspace folders and copy default query/filter assets into `config/`.

### `scripts/filter_search_results.py`

Score and filter raw Google/browser search results into lead candidates. This is the replacement for the old Tavily collector.

### `scripts/collect_bing_results.py`

Use the local OpenClaw browser and Chrome to run Bing searches from `config/queries.txt`, then write normalized raw results to `input/search_results.jsonl`.

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
