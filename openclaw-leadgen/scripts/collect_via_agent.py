#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path


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
    queries_file: Path,
    input_file: Path,
    max_queries: int,
    search_engine: str,
) -> str:
    return (
        "你是 leadgen 数据采集 subagent。\n"
        f"工作区: {workspace_root}\n"
        f"查询词文件: {queries_file}\n"
        f"输出文件: {input_file}\n"
        f"搜索引擎: {search_engine}\n"
        f"仅处理前 {max_queries} 条 query。\n\n"
        "要求:\n"
        "1. 使用本机 OpenClaw 浏览器和本地 Chrome 进行网页搜索。\n"
        "2. 像真人一样从搜索引擎首页进入，在同一个浏览器会话里逐条搜索，不要直接机械批量拼接搜索结果 URL。\n"
        "3. 把原始搜索结果写入输出文件，每行一个 JSON 对象。\n"
        "4. 每个 JSON 对象字段必须是: query,title,url,snippet,source,position。\n"
        f"5. source 固定写 {search_engine}。\n"
        "6. 如果遇到验证码、block、sorry 页面或无法继续，立即停止，不要继续重试。\n"
        "7. 不要输出任何解释、Markdown 或多余文本。\n"
        '8. 成功时只返回 JSON，例如: {"ok":true,"rows":12,"file":"/abs/path/search_results.jsonl","engine":"bing"}。\n'
        '9. 失败时只返回 JSON，例如: {"ok":false,"blocked":true,"engine":"bing","reason":"captcha_or_block","file":"/abs/path/search_results.jsonl"}。\n'
    )


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
    parser.add_argument("--search-engine", default="bing")
    parser.add_argument("--agent-timeout-seconds", type=int)
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root).resolve()
    queries_file = Path(args.queries_file).resolve()
    input_file = Path(args.input_file).resolve()
    input_file.parent.mkdir(parents=True, exist_ok=True)

    prompt = build_prompt(
        workspace_root=workspace_root,
        queries_file=queries_file,
        input_file=input_file,
        max_queries=args.max_queries,
        search_engine=args.search_engine,
    )

    command = [
        args.openclaw_bin,
        "agent",
        "--agent",
        args.agent_id,
        "--session-id",
        args.session_id,
        "--thinking",
        args.thinking,
        "--json",
        "--message",
        prompt,
    ]
    if args.agent_timeout_seconds is not None:
        command.extend(["--timeout", str(args.agent_timeout_seconds)])

    payload = run_command(command, expect_json=True)
    reply_text = extract_reply(payload)
    result = parse_reply_json(reply_text)

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if not result.get("ok"):
        reason = result.get("reason") or "subagent collection failed"
        raise SystemExit(f"subagent collection failed: {reason}")

    if not input_file.exists():
        raise SystemExit(f"subagent reported success but output file is missing: {input_file}")


if __name__ == "__main__":
    main()
