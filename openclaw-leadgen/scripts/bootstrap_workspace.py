#!/usr/bin/env python3
import argparse
import shutil
from pathlib import Path


DEFAULT_ASSETS = (
    "queries.txt",
    "include_keywords.txt",
    "exclude_keywords.txt",
    "blocked_domains.txt",
    "trade_config.yaml",
    "strategy_log.md",
)


def copy_asset(src: Path, dst: Path, force: bool) -> None:
    if dst.exists() and not force:
        return
    shutil.copyfile(src, dst)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    skill_dir = Path(args.skill_dir).resolve()
    workspace_root = Path(args.workspace_root).resolve()
    config_dir = workspace_root / "config"
    input_dir = workspace_root / "input"
    out_dir = workspace_root / "out"
    results_dir = workspace_root / "results"
    logs_dir = workspace_root / "logs"
    scripts_dir = workspace_root / "scripts"
    assets_dir = skill_dir / "assets"

    for path in (workspace_root, config_dir, input_dir, out_dir, results_dir, logs_dir, scripts_dir):
        path.mkdir(parents=True, exist_ok=True)

    for name in DEFAULT_ASSETS:
        src = assets_dir / name
        if not src.exists():
            raise SystemExit(f"missing asset: {src}")
        copy_asset(src, config_dir / name, args.force)

    print(f"OK workspace={workspace_root}")
    print(f"CONFIG {config_dir}")
    print(f"INPUT {input_dir}")
    print(f"OUT {out_dir}")
    print(f"RESULTS {results_dir}")
    print(f"LOGS {logs_dir}")


if __name__ == "__main__":
    main()
