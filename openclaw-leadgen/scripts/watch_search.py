#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path


def run_step(command: list[str]) -> None:
    subprocess.run(command, check=True)


def copy_if_exists(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return True


def file_row_count(csv_path: Path) -> int:
    if not csv_path.exists():
        return 0
    lines = csv_path.read_text(encoding="utf-8-sig").splitlines()
    return max(0, len(lines) - 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--skill-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--collector-agent-id", default="leadgen")
    parser.add_argument("--collector-session-id", default="leadgen-collector")
    parser.add_argument("--collector-thinking", default="medium")
    parser.add_argument("--collector-search-engine", default="google")
    parser.add_argument("--max-queries", type=int, default=3)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--product-label", default="watch-leads")
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root).resolve()
    skill_root = Path(args.skill_root).resolve()
    out_dir = workspace_root / "out"
    results_dir = workspace_root / "results"
    logs_dir = workspace_root / "logs"
    results_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    run_step(
        [
            sys.executable,
            str(skill_root / "scripts" / "run_pipeline.py"),
            "--workspace-root",
            str(workspace_root),
            "--collect-via-agent",
            "--collector-agent-id",
            args.collector_agent_id,
            "--collector-session-id",
            args.collector_session_id,
            "--collector-thinking",
            args.collector_thinking,
            "--collector-search-engine",
            args.collector_search_engine,
            "--max-queries",
            str(args.max_queries),
            "--top-n",
            str(args.top_n),
        ]
    )

    date_str = dt.date.today().isoformat()
    csv_result = results_dir / f"{date_str}_{args.product_label}.csv"
    report_result = results_dir / f"{date_str}_{args.product_label}_report.md"
    status_log = logs_dir / f"{date_str}_status.json"
    search_log = logs_dir / f"{date_str}_search_log.json"

    copy_if_exists(out_dir / "latest_leads.csv", csv_result)
    copy_if_exists(out_dir / "latest_summary.md", report_result)

    status_payload = {
        "date": date_str,
        "engine": args.collector_search_engine,
        "max_queries": args.max_queries,
        "product_label": args.product_label,
        "latest_leads_csv": str(out_dir / "latest_leads.csv"),
        "latest_summary_md": str(out_dir / "latest_summary.md"),
        "contact_ready_csv": str(out_dir / "contact_ready_top20_latest.csv"),
        "raw_rows": file_row_count(out_dir / "latest_leads.csv"),
        "status": "ok",
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    search_payload = {
        "date": date_str,
        "engine": args.collector_search_engine,
        "collector_agent_id": args.collector_agent_id,
        "collector_session_id": args.collector_session_id,
        "max_queries": args.max_queries,
        "product_label": args.product_label,
        "workspace_root": str(workspace_root),
        "out_dir": str(out_dir),
        "results_dir": str(results_dir),
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
    }

    status_log.write_text(json.dumps(status_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    search_log.write_text(json.dumps(search_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"OK watch_search workspace={workspace_root}")
    print(f"CSV {csv_result}")
    print(f"REPORT {report_result}")
    print(f"STATUS {status_log}")
    print(f"SEARCH_LOG {search_log}")


if __name__ == "__main__":
    main()
