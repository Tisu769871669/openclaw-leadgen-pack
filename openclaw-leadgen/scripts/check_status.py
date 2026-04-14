#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def newest_file(directory: Path, suffix: str) -> Path | None:
    matches = sorted(directory.glob(f"*{suffix}"))
    return matches[-1] if matches else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", required=True)
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root).resolve()
    logs_dir = workspace_root / "logs"
    results_dir = workspace_root / "results"

    latest_status = newest_file(logs_dir, "_status.json")
    latest_search = newest_file(logs_dir, "_search_log.json")
    latest_csv = newest_file(results_dir, ".csv")
    latest_report = newest_file(results_dir, "_report.md")

    status_payload = json.loads(latest_status.read_text(encoding="utf-8")) if latest_status and latest_status.exists() else {}
    search_payload = json.loads(latest_search.read_text(encoding="utf-8")) if latest_search and latest_search.exists() else {}

    print(json.dumps({
        "latest_status": str(latest_status) if latest_status else "",
        "latest_search_log": str(latest_search) if latest_search else "",
        "latest_csv": str(latest_csv) if latest_csv else "",
        "latest_report": str(latest_report) if latest_report else "",
        "status_payload": status_payload,
        "search_payload": search_payload,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
