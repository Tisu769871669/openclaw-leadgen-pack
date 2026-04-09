#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path


CONFIG_FILES = (
    "queries.txt",
    "include_keywords.txt",
    "exclude_keywords.txt",
    "blocked_domains.txt",
)


def run_step(command: list[str]) -> None:
    subprocess.run(command, check=True)


def ensure_workspace(skill_dir: Path, workspace_root: Path, config_dir: Path) -> None:
    missing = [name for name in CONFIG_FILES if not (config_dir / name).exists()]
    if not missing:
        return
    run_step(
        [
            sys.executable,
            str(skill_dir / "scripts" / "bootstrap_workspace.py"),
            "--workspace-root",
            str(workspace_root),
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--input-file")
    parser.add_argument("--config-dir")
    parser.add_argument("--out-dir")
    parser.add_argument("--collect-via-agent", action="store_true")
    parser.add_argument("--collect-bing", action="store_true")
    parser.add_argument("--collect-google", action="store_true")
    parser.add_argument("--openclaw-bin", default="openclaw")
    parser.add_argument("--browser-profile")
    parser.add_argument("--collector-agent-id", default="leadgen")
    parser.add_argument("--collector-session-id", default="leadgen-collector")
    parser.add_argument("--collector-thinking", default="medium")
    parser.add_argument("--collector-timeout-seconds", type=int)
    parser.add_argument("--collector-search-engine", default="bing")
    parser.add_argument("--search-language", default="en-US")
    parser.add_argument("--search-country", default="us")
    parser.add_argument("--search-timeout-ms", type=int, default=20000)
    parser.add_argument("--search-results-per-query", type=int, default=10)
    parser.add_argument("--max-queries", type=int, default=25)
    parser.add_argument("--min-score", type=int, default=0)
    parser.add_argument("--top-n", type=int, default=20)
    args = parser.parse_args()

    skill_dir = Path(__file__).resolve().parents[1]
    workspace_root = Path(args.workspace_root).resolve()
    default_input = workspace_root / "input" / "search_results.jsonl"
    legacy_input = workspace_root / "input" / "google_results.jsonl"
    if args.input_file:
        input_file = Path(args.input_file).resolve()
    elif default_input.exists() or args.collect_via_agent or args.collect_bing or args.collect_google:
        input_file = default_input
    else:
        input_file = legacy_input
    config_dir = Path(args.config_dir).resolve() if args.config_dir else workspace_root / "config"
    out_dir = Path(args.out_dir).resolve() if args.out_dir else workspace_root / "out"

    ensure_workspace(skill_dir, workspace_root, config_dir)
    if args.collect_via_agent:
        collect_command = [
            sys.executable,
            str(skill_dir / "scripts" / "collect_via_agent.py"),
            "--workspace-root",
            str(workspace_root),
            "--queries-file",
            str(config_dir / "queries.txt"),
            "--input-file",
            str(input_file),
            "--openclaw-bin",
            args.openclaw_bin,
            "--agent-id",
            args.collector_agent_id,
            "--session-id",
            args.collector_session_id,
            "--thinking",
            args.collector_thinking,
            "--max-queries",
            str(args.max_queries),
            "--search-engine",
            args.collector_search_engine,
        ]
        if args.collector_timeout_seconds is not None:
            collect_command.extend(["--agent-timeout-seconds", str(args.collector_timeout_seconds)])
        try:
            run_step(collect_command)
        except subprocess.CalledProcessError as err:
            raise SystemExit(
                "subagent collection failed; check the JSON error above and any debug artifacts in the workspace out/ directory"
            ) from err
    elif args.collect_bing or args.collect_google:
        if args.collect_google and not args.collect_bing:
            print("WARN --collect-google is deprecated; using Bing collector instead.")
        collect_command = [
            sys.executable,
            str(skill_dir / "scripts" / "collect_bing_results.py"),
            "--workspace-root",
            str(workspace_root),
            "--queries-file",
            str(config_dir / "queries.txt"),
            "--output-file",
            str(input_file),
            "--openclaw-bin",
            args.openclaw_bin,
            "--setlang",
            args.search_language,
            "--cc",
            args.search_country,
            "--timeout-ms",
            str(args.search_timeout_ms),
            "--max-results-per-query",
            str(args.search_results_per_query),
            "--max-queries",
            str(args.max_queries),
        ]
        if args.browser_profile:
            collect_command.extend(["--browser-profile", args.browser_profile])
        run_step(collect_command)

    if not input_file.exists():
        raise SystemExit(f"missing input file: {input_file}")

    run_step(
        [
            sys.executable,
            str(skill_dir / "scripts" / "filter_search_results.py"),
            "--input-file",
            str(input_file),
            "--queries-file",
            str(config_dir / "queries.txt"),
            "--include-file",
            str(config_dir / "include_keywords.txt"),
            "--exclude-file",
            str(config_dir / "exclude_keywords.txt"),
            "--blocked-domains-file",
            str(config_dir / "blocked_domains.txt"),
            "--out-dir",
            str(out_dir),
            "--max-queries",
            str(args.max_queries),
            "--min-score",
            str(args.min_score),
        ]
    )

    run_step(
        [
            sys.executable,
            str(skill_dir / "scripts" / "postprocess_contact_top20.py"),
            "--input-csv",
            str(out_dir / "latest_leads.csv"),
            "--out-dir",
            str(out_dir),
            "--top-n",
            str(args.top_n),
        ]
    )

    print(f"OK workspace={workspace_root}")
    print(f"LEADS {out_dir / 'latest_leads.csv'}")
    print(f"TOP20 {out_dir / 'contact_ready_top20_latest.csv'}")


if __name__ == "__main__":
    main()
