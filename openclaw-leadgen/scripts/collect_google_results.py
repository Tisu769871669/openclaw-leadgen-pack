#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus


CONSENT_JS = """
() => {
  const labels = ['Accept all', 'I agree', 'Accept', '同意', '接受', '接受全部'];
  const elements = Array.from(document.querySelectorAll('button, input[type="button"], input[type="submit"]'));
  for (const element of elements) {
    const label = (element.innerText || element.value || '').trim();
    if (!label) continue;
    if (labels.some((candidate) => label === candidate || label.includes(candidate))) {
      element.click();
      return { clicked: true, label };
    }
  }
  return { clicked: false };
}
""".strip()


EXTRACT_RESULTS_JS = """
() => {
  function normalizeUrl(raw) {
    try {
      const url = new URL(raw, location.href);
      if ((url.hostname === 'www.google.com' || url.hostname.endsWith('.google.com')) && url.pathname === '/url' && url.searchParams.get('q')) {
        return url.searchParams.get('q');
      }
      return url.href;
    } catch (_) {
      return String(raw || '');
    }
  }

  function pickSnippet(block, title) {
    const selectors = ['div.VwiC3b', 'span.aCOpRe', 'div[data-sncf="1"]', 'div.yXK7lf', 'div.ITZIwc'];
    for (const selector of selectors) {
      const node = block.querySelector(selector);
      const text = (node?.innerText || '').trim();
      if (text) return text;
    }
    const lines = (block.innerText || '')
      .split('\\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .filter((line) => line !== title && !/^https?:/i.test(line));
    return lines.slice(1, 4).join(' ');
  }

  const seen = new Set();
  const results = [];
  const blocks = Array.from(document.querySelectorAll('#search .g, #search div.MjjYud, #rso div.g, #rso div.MjjYud'));
  for (const block of blocks) {
    const titleNode = block.querySelector('h3');
    const linkNode = titleNode?.closest('a') || block.querySelector('a[href]');
    const title = (titleNode?.innerText || '').trim();
    let url = normalizeUrl(linkNode?.href || '');
    if (!title || !url) continue;
    if (url.includes('/search?') || url.includes('google.com/preferences')) continue;
    if (seen.has(url)) continue;
    seen.add(url);
    results.push({
      title,
      url,
      snippet: pickSnippet(block, title),
      position: results.length + 1
    });
  }

  return {
    pageTitle: document.title,
    resultCount: results.length,
    results
  };
}
""".strip()


HTML_DUMP_JS = "() => document.documentElement.outerHTML"


def read_lines(path: Path) -> list[str]:
    rows: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if line and not line.startswith("#"):
                rows.append(line)
    return rows


def parse_json_output(stdout: str) -> object:
    text = stdout.strip()
    if not text:
        raise ValueError("empty JSON output")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start_object = text.find("{")
        start_array = text.find("[")
        starts = [index for index in (start_object, start_array) if index >= 0]
        if not starts:
            raise
        start = min(starts)
        return json.loads(text[start:])


def run_command(command: list[str], expect_json: bool = False, check: bool = True) -> object:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n{completed.stderr or completed.stdout}"
        )
    if expect_json:
        return parse_json_output(completed.stdout)
    return completed.stdout


def browser_json(browser_prefix: list[str], args: list[str]) -> object:
    return run_command([*browser_prefix, "--json", *args], expect_json=True)


def browser_run(browser_prefix: list[str], args: list[str], check: bool = True) -> None:
    run_command([*browser_prefix, *args], expect_json=False, check=check)


def sanitize_filename(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in value.lower()).strip("_")
    return cleaned[:80] or "query"


def maybe_accept_google_consent(browser_prefix: list[str], target_id: str) -> bool:
    payload = browser_json(browser_prefix, ["evaluate", "--target-id", target_id, "--fn", CONSENT_JS])
    result = payload.get("result") if isinstance(payload, dict) else None
    clicked = bool(isinstance(result, dict) and result.get("clicked"))
    if clicked:
        time.sleep(1.5)
    return clicked


def extract_results(browser_prefix: list[str], target_id: str) -> dict:
    payload = browser_json(browser_prefix, ["evaluate", "--target-id", target_id, "--fn", EXTRACT_RESULTS_JS])
    result = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(result, dict):
        raise RuntimeError(f"unexpected evaluate output for target {target_id}: {payload}")
    return result


def dump_html(browser_prefix: list[str], target_id: str, path: Path) -> None:
    payload = browser_json(browser_prefix, ["evaluate", "--target-id", target_id, "--fn", HTML_DUMP_JS])
    result = payload.get("result") if isinstance(payload, dict) else None
    if isinstance(result, str):
        path.write_text(result, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--queries-file")
    parser.add_argument("--output-file")
    parser.add_argument("--openclaw-bin", default="openclaw")
    parser.add_argument("--browser-profile")
    parser.add_argument("--max-queries", type=int, default=20)
    parser.add_argument("--max-results-per-query", type=int, default=10)
    parser.add_argument("--timeout-ms", type=int, default=20000)
    parser.add_argument("--hl", default="en")
    parser.add_argument("--gl", default="us")
    parser.add_argument("--debug-html-dir")
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root).resolve()
    queries_file = Path(args.queries_file).resolve() if args.queries_file else workspace_root / "config" / "queries.txt"
    output_file = Path(args.output_file).resolve() if args.output_file else workspace_root / "input" / "google_results.jsonl"
    debug_html_dir = Path(args.debug_html_dir).resolve() if args.debug_html_dir else workspace_root / "out" / "google-debug"

    queries = read_lines(queries_file)[: args.max_queries]
    output_file.parent.mkdir(parents=True, exist_ok=True)
    debug_html_dir.mkdir(parents=True, exist_ok=True)

    openclaw_bin = args.openclaw_bin
    browser_prefix = [openclaw_bin, "browser"]
    if args.browser_profile:
        browser_prefix.extend(["--browser-profile", args.browser_profile])

    print(f"Starting OpenClaw browser for {len(queries)} queries...", flush=True)
    run_command([*browser_prefix, "start"], check=True)

    rows: list[dict] = []
    opened_targets: list[str] = []

    try:
        for index, query in enumerate(queries, start=1):
            print(f"[{index}/{len(queries)}] Google search: {query}", flush=True)
            target_id = ""
            try:
                search_url = (
                    "https://www.google.com/search?"
                    f"hl={args.hl}&gl={args.gl}&num={args.max_results_per_query}&q={quote_plus(query)}"
                )
                tab = browser_json(browser_prefix, ["open", search_url])
                if isinstance(tab, dict):
                    target_id = str(tab.get("targetId") or tab.get("id") or "").strip()
                if not target_id:
                    raise RuntimeError(f"could not resolve target id for query: {query}")
                opened_targets.append(target_id)

                browser_run(browser_prefix, ["wait", "--target-id", target_id, "--load", "domcontentloaded", "--timeout-ms", str(args.timeout_ms)], check=False)
                browser_run(browser_prefix, ["wait", "--target-id", target_id, "--time", "2500"], check=False)
                maybe_accept_google_consent(browser_prefix, target_id)
                browser_run(browser_prefix, ["wait", "--target-id", target_id, "--time", "1500"], check=False)

                result = extract_results(browser_prefix, target_id)
                extracted = list(result.get("results") or [])[: args.max_results_per_query]
                if not extracted:
                    dump_html(browser_prefix, target_id, debug_html_dir / f"{sanitize_filename(query)}.html")
                    print("  -> 0 results, dumped debug HTML", flush=True)
                else:
                    print(f"  -> {len(extracted)} results", flush=True)

                for item in extracted:
                    rows.append(
                        {
                            "query": query,
                            "title": str(item.get("title") or "").strip(),
                            "url": str(item.get("url") or "").strip(),
                            "snippet": str(item.get("snippet") or "").strip(),
                            "source": "google",
                            "position": item.get("position"),
                            "page_title": result.get("pageTitle") or "",
                        }
                    )
            except Exception as err:
                print(f"  -> failed: {err}", file=sys.stderr, flush=True)
                if target_id:
                    dump_html(browser_prefix, target_id, debug_html_dir / f"{sanitize_filename(query)}.html")
                continue

        with output_file.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    finally:
        for target_id in opened_targets:
            run_command([*browser_prefix, "close", target_id], check=False)

    print(f"OK queries={len(queries)} rows={len(rows)}")
    print(f"OUTPUT {output_file}")
    print(f"DEBUG_HTML {debug_html_dir}")


if __name__ == "__main__":
    main()
