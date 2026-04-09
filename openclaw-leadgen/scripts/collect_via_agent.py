#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path


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


def run_command(command: list[str], expect_json: bool = False) -> object:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n{completed.stderr or completed.stdout}"
        )
    if expect_json:
        return parse_json_output(completed.stdout)
    return completed.stdout


def extract_reply(payload: object) -> str:
    if isinstance(payload, str):
        return payload.strip()
    if not isinstance(payload, dict):
        return ""

    payloads = payload.get("payloads")
    if isinstance(payloads, list):
        for item in payloads:
            if isinstance(item, dict) and isinstance(item.get("text"), str) and item.get("text").strip():
                return item["text"].strip()

    nested = payload.get("result")
    if isinstance(nested, dict):
        nested_payloads = nested.get("payloads")
        if isinstance(nested_payloads, list):
            for item in nested_payloads:
                if isinstance(item, dict) and isinstance(item.get("text"), str) and item.get("text").strip():
                    return item["text"].strip()

    candidates = [
        payload.get("reply"),
        payload.get("response"),
        payload.get("content"),
        payload.get("message"),
        payload.get("output_text"),
        payload.get("text"),
    ]
    if isinstance(nested, dict):
        candidates.extend(
            [
                nested.get("reply"),
                nested.get("response"),
                nested.get("content"),
                nested.get("message"),
                nested.get("output_text"),
                nested.get("text"),
            ]
        )

    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def parse_reply_json(reply_text: str) -> dict:
    text = reply_text.strip()
    if not text:
        raise ValueError("agent returned empty reply")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("agent reply was not a JSON object")
    return payload


def build_prompt(
    workspace_root: Path,
    query: str,
    input_file: Path,
    search_engine: str,
    query_index: int,
    query_total: int,
    results_per_query: int,
) -> str:
    return (
        "你是 leadgen 数据采集 subagent。\n"
        f"工作区: {workspace_root}\n"
        f"当前 query: {query}\n"
        f"输出文件: {input_file}\n"
        f"搜索目标: {search_engine}\n"
        f"这是第 {query_index}/{query_total} 条 query。\n\n"
        "要求:\n"
        "1. 必须使用当前环境里的 `browser` 工具执行真实浏览器搜索。\n"
        "2. 不要优先使用 `web_search` 或 `web_fetch`，也不要直接批量抓网页。\n"
        "3. 在同一个浏览器会话里像真人一样搜索：先打开搜索引擎首页，再输入当前 query，再提交搜索。\n"
        "4. 只处理这一条 query，不要自行扩展到别的 query。\n"
        f"5. 采集最多 {results_per_query} 条有用的自然搜索结果。\n"
        "6. 把结果追加写入输出文件。若文件不存在就创建；若已存在就保留已有行并追加当前 query 的新行。\n"
        "7. 避免重复写入同一个 query/url 组合。\n"
        "8. 每行一个 JSON 对象，字段必须是: query,title,url,snippet,source,position。\n"
        f"9. source 固定写 {search_engine}。\n"
        "10. 如果遇到验证码、block、sorry 页面或无法继续，立即停止当前任务，不要继续重试。\n"
        "11. 不要输出解释、Markdown、代码块或多余文本。\n"
        '12. 成功时只返回 JSON，例如: {"ok":true,"query":"...","rows_added":8,"file":"/abs/path/search_results.jsonl","engine":"google","tool":"browser"}。\n'
        '13. 失败时只返回 JSON，例如: {"ok":false,"query":"...","blocked":true,"engine":"google","tool":"browser","reason":"captcha_or_block","file":"/abs/path/search_results.jsonl"}。\n'
    )


def run_agent_turn(
    *,
    openclaw_bin: str,
    agent_id: str,
    session_id: str,
    thinking: str,
    prompt: str,
    timeout_seconds: int | None,
) -> dict:
    command = [
        openclaw_bin,
        "agent",
        "--agent",
        agent_id,
        "--session-id",
        session_id,
        "--thinking",
        thinking,
        "--json",
        "--message",
        prompt,
    ]
    if timeout_seconds is not None:
        command.extend(["--timeout", str(timeout_seconds)])

    payload = run_command(command, expect_json=True)
    reply_text = extract_reply(payload)
    return parse_reply_json(reply_text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--queries-file", required=True)
    parser.add_argument("--input-file", required=True)
    parser.add_argument("--openclaw-bin", default="openclaw")
    parser.add_argument("--agent-id", default="leadgen")
    parser.add_argument("--session-id", default="leadgen-collector")
    parser.add_argument("--thinking", default="medium")
    parser.add_argument("--max-queries", type=int, default=20)
    parser.add_argument("--results-per-query", type=int, default=10)
    parser.add_argument("--search-engine", default="google")
    parser.add_argument("--agent-timeout-seconds", type=int)
    parser.add_argument("--append-existing", action="store_true")
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root).resolve()
    queries_file = Path(args.queries_file).resolve()
    input_file = Path(args.input_file).resolve()
    input_file.parent.mkdir(parents=True, exist_ok=True)

    queries = read_lines(queries_file)[: args.max_queries]
    if not args.append_existing and input_file.exists():
        input_file.unlink()

    total_rows_added = 0
    processed_queries = 0

    for index, query in enumerate(queries, start=1):
        prompt = build_prompt(
            workspace_root=workspace_root,
            query=query,
            input_file=input_file,
            search_engine=args.search_engine,
            query_index=index,
            query_total=len(queries),
            results_per_query=args.results_per_query,
        )
        result = run_agent_turn(
            openclaw_bin=args.openclaw_bin,
            agent_id=args.agent_id,
            session_id=args.session_id,
            thinking=args.thinking,
            prompt=prompt,
            timeout_seconds=args.agent_timeout_seconds,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))

        if not result.get("ok"):
            reason = result.get("reason") or "subagent collection failed"
            raise SystemExit(f"subagent collection failed at query {index}: {reason}")

        processed_queries += 1
        try:
            total_rows_added += int(result.get("rows_added", 0) or 0)
        except Exception:
            pass

    if not input_file.exists():
        raise SystemExit(f"subagent reported success but output file is missing: {input_file}")

    summary = {
        "ok": True,
        "processed_queries": processed_queries,
        "rows_added": total_rows_added,
        "file": str(input_file),
        "engine": args.search_engine,
        "tool": "browser",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
