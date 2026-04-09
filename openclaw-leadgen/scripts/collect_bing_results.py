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
  const labels = ['Accept', 'Accept all', 'I agree', '同意', '接受', '接受全部'];
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
  function pickSnippet(block) {
    const selectors = ['.b_caption p', '.b_snippet', 'p'];
    for (const selector of selectors) {
      const node = block.querySelector(selector);
      const text = (node?.innerText || '').trim();
      if (text) return text;
    }
    return '';
  }

  const seen = new Set();
  const results = [];
  const blocks = Array.from(document.querySelectorAll('#b_results li.b_algo'));
  for (const block of blocks) {
    const linkNode = block.querySelector('h2 a');
    const title = (linkNode?.innerText || '').trim();
    const url = (linkNode?.href || '').trim();
    if (!title || !url) continue;
    if (seen.has(url)) continue;
    seen.add(url);
    results.push({
      title,
      url,
      snippet: pickSnippet(block),
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
SEARCH_INPUT_READY_SELECTOR = "#sb_form_q, input[name='q'], textarea[name='q'], input[type='search'], textarea[type='search']"
PAGE_META_JS = """
() => ({
  url: location.href,
  title: document.title,
  text: (document.body?.innerText || '').slice(0, 4000)
})
""".strip()


def read_lines(path: Path) -> list[str]:
    rows: list[str] = []
    with path.open("r", encoding="utf-8-sig") as handle:
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


def maybe_accept_consent(browser_prefix: list[str], target_id: str) -> bool:
    payload = browser_json(browser_prefix, ["evaluate", "--target-id", target_id, "--fn", CONSENT_JS])
    result = payload.get("result") if isinstance(payload, dict) else None
    clicked = bool(isinstance(result, dict) and result.get("clicked"))
    if clicked:
        time.sleep(1.5)
    return clicked


def fetch_page_meta(browser_prefix: list[str], target_id: str) -> dict:
    payload = browser_json(browser_prefix, ["evaluate", "--target-id", target_id, "--fn", PAGE_META_JS])
    result = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(result, dict):
        return {}
    return result


def is_bing_block_page(page_meta: dict) -> bool:
    url = str(page_meta.get("url") or "").lower()
    title = str(page_meta.get("title") or "").lower()
    text = str(page_meta.get("text") or "").lower()
    if "bing.com/challenge" in url or "bing.com/ck/a" in url:
        return True
    signals = (
        "verify you are human",
        "unusual traffic",
        "captcha",
        "security check",
        "enable javascript and cookies to continue",
    )
    haystack = f"{title}\n{text}"
    return any(signal in haystack for signal in signals)


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


def build_submit_search_js(query: str) -> str:
    query_json = json.dumps(query, ensure_ascii=False)
    return f"""
() => {{
  const query = {query_json};
  const input = document.querySelector("{SEARCH_INPUT_READY_SELECTOR}");
  if (!input) {{
    return {{ submitted: false, reason: "input-not-found" }};
  }}
  input.focus();
  if ("value" in input) {{
    input.value = "";
    input.dispatchEvent(new Event("input", {{ bubbles: true }}));
    input.value = query;
    input.dispatchEvent(new Event("input", {{ bubbles: true }}));
    input.dispatchEvent(new Event("change", {{ bubbles: true }}));
  }}
  const button = document.querySelector("#sb_form_go, button[type='submit'], input[type='submit']");
  if (button) {{
    button.click();
    return {{ submitted: true, method: "button-click" }};
  }}
  const form = input.form || input.closest("form");
  if (form) {{
    form.submit();
    return {{ submitted: true, method: "form-submit" }};
  }}
  input.dispatchEvent(new KeyboardEvent("keydown", {{ key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true }}));
  input.dispatchEvent(new KeyboardEvent("keypress", {{ key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true }}));
  input.dispatchEvent(new KeyboardEvent("keyup", {{ key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true }}));
  return {{ submitted: true, method: "enter-key" }};
}}
""".strip()


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
    parser.add_argument("--setlang", default="en-US")
    parser.add_argument("--cc", default="us")
    parser.add_argument("--debug-html-dir")
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root).resolve()
    queries_file = Path(args.queries_file).resolve() if args.queries_file else workspace_root / "config" / "queries.txt"
    output_file = Path(args.output_file).resolve() if args.output_file else workspace_root / "input" / "search_results.jsonl"
    debug_html_dir = Path(args.debug_html_dir).resolve() if args.debug_html_dir else workspace_root / "out" / "bing-debug"

    queries = read_lines(queries_file)[: args.max_queries]
    output_file.parent.mkdir(parents=True, exist_ok=True)
    debug_html_dir.mkdir(parents=True, exist_ok=True)

    browser_prefix = [args.openclaw_bin, "browser"]
    if args.browser_profile:
        browser_prefix.extend(["--browser-profile", args.browser_profile])

    print(f"Starting OpenClaw browser for {len(queries)} Bing queries...", flush=True)
    run_command([*browser_prefix, "start"], check=True)

    rows: list[dict] = []
    target_id = ""
    homepage_url = f"https://www.bing.com/?setlang={quote_plus(args.setlang)}&cc={quote_plus(args.cc)}"

    try:
        tab = browser_json(browser_prefix, ["open", homepage_url])
        if isinstance(tab, dict):
            target_id = str(tab.get("targetId") or tab.get("id") or "").strip()
        if not target_id:
            raise RuntimeError("could not resolve Bing tab target id")

        for index, query in enumerate(queries, start=1):
            print(f"[{index}/{len(queries)}] Bing search: {query}", flush=True)
            try:
                browser_run(browser_prefix, ["navigate", "--target-id", target_id, homepage_url], check=False)
                browser_run(browser_prefix, ["wait", "--target-id", target_id, "--load", "domcontentloaded", "--timeout-ms", str(args.timeout_ms)], check=False)
                browser_run(browser_prefix, ["wait", SEARCH_INPUT_READY_SELECTOR, "--target-id", target_id, "--timeout-ms", str(args.timeout_ms)], check=False)
                browser_run(browser_prefix, ["wait", "--target-id", target_id, "--time", "1200"], check=False)
                maybe_accept_consent(browser_prefix, target_id)
                browser_run(browser_prefix, ["wait", "--target-id", target_id, "--time", "800"], check=False)

                submit_payload = browser_json(browser_prefix, ["evaluate", "--target-id", target_id, "--fn", build_submit_search_js(query)])
                submit_result = submit_payload.get("result") if isinstance(submit_payload, dict) else None
                if isinstance(submit_result, dict) and not submit_result.get("submitted"):
                    raise RuntimeError(f"could not submit Bing search: {submit_result}")

                browser_run(browser_prefix, ["wait", "--target-id", target_id, "--load", "domcontentloaded", "--timeout-ms", str(args.timeout_ms)], check=False)
                browser_run(browser_prefix, ["wait", "#b_results", "--target-id", target_id, "--timeout-ms", str(args.timeout_ms)], check=False)
                browser_run(browser_prefix, ["wait", "--target-id", target_id, "--time", "1500"], check=False)

                page_meta = fetch_page_meta(browser_prefix, target_id)
                if is_bing_block_page(page_meta):
                    dump_path = debug_html_dir / f"{sanitize_filename(query)}.html"
                    dump_html(browser_prefix, target_id, dump_path)
                    raise RuntimeError(
                        "bing returned a block or verification page; "
                        f"debug HTML saved to {dump_path}"
                    )

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
                            "source": "bing",
                            "position": item.get("position"),
                            "page_title": result.get("pageTitle") or "",
                        }
                    )
            except Exception as err:
                print(f"  -> failed: {err}", file=sys.stderr, flush=True)
                dump_html(browser_prefix, target_id, debug_html_dir / f"{sanitize_filename(query)}.html")
                break
    finally:
        if target_id:
            run_command([*browser_prefix, "close", target_id], check=False)

    with output_file.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"OK queries={len(queries)} rows={len(rows)}")
    print(f"OUTPUT {output_file}")
    print(f"DEBUG_HTML {debug_html_dir}")


if __name__ == "__main__":
    main()
