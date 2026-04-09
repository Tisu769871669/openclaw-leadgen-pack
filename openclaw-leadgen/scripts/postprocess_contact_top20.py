#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
from pathlib import Path
from urllib.parse import urlparse


CONTACT_SIGNALS = [
    "contact",
    "whatsapp",
    "wechat",
    "telegram",
    "zalo",
    "phone",
    "tel",
    "address",
    "email",
    "联系方式",
    "微信",
    "电话",
    "地址",
    "到店",
    "liên hệ",
    "контакты",
]

SECOND_LEVEL_SUFFIXES = {
    "com.cn",
    "net.cn",
    "org.cn",
    "com.vn",
    "com.ru",
    "com.tw",
    "com.hk",
    "com.sg",
    "co.uk",
    "com.au",
}


def root_domain(host: str) -> str:
    hostname = (host or "").lower().strip(".")
    if not hostname:
        return ""
    parts = hostname.split(".")
    if len(parts) <= 2:
        return hostname
    tail_two = ".".join(parts[-2:])
    tail_three = ".".join(parts[-3:])
    if tail_two in SECOND_LEVEL_SUFFIXES and len(parts) >= 3:
        return ".".join(parts[-3:])
    if tail_three in SECOND_LEVEL_SUFFIXES and len(parts) >= 4:
        return ".".join(parts[-4:])
    return ".".join(parts[-2:])


def has_contact_signal(row: dict) -> bool:
    haystack = " ".join(
        [
            row.get("title", ""),
            row.get("snippet", ""),
            row.get("url", ""),
            row.get("query", ""),
        ]
    ).lower()
    return any(signal in haystack for signal in CONTACT_SIGNALS)


def write_latest_copy(src: Path, latest: Path) -> None:
    latest.write_bytes(src.read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--top-n", type=int, default=20)
    args = parser.parse_args()

    input_csv = Path(args.input_csv).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    with input_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    rows = [row for row in rows if has_contact_signal(row)]
    rows.sort(key=lambda row: float(row.get("score", 0) or 0), reverse=True)

    picked: list[dict] = []
    seen_domains: set[str] = set()
    for row in rows:
        host = urlparse(row.get("url", "")).netloc
        current_root_domain = root_domain(host)
        if not current_root_domain or current_root_domain in seen_domains:
            continue
        seen_domains.add(current_root_domain)
        row["root_domain"] = current_root_domain
        picked.append(row)
        if len(picked) >= args.top_n:
            break

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_csv = out_dir / f"contact_ready_top20_{timestamp}.csv"
    out_md = out_dir / f"contact_ready_top20_{timestamp}.md"
    latest_csv = out_dir / "contact_ready_top20_latest.csv"
    latest_md = out_dir / "contact_ready_top20_latest.md"

    fieldnames = [
        "score",
        "root_domain",
        "domain",
        "title",
        "url",
        "query",
        "snippet",
        "source",
        "position",
        "timestamp",
    ]
    with out_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in picked:
            writer.writerow({key: row.get(key, "") for key in fieldnames})

    lines = [
        f"# Contact Ready Top20 ({timestamp})",
        "",
        f"- Source file: {input_csv.name}",
        f"- After contact filter: {len(rows)}",
        f"- After website dedup: {len(picked)}",
        "",
    ]
    for index, row in enumerate(picked, start=1):
        lines.append(f"{index}. [{row.get('title', '')}]({row.get('url', '')})")
        lines.append(
            f"   - Score: {row.get('score', '')} | Root domain: {row.get('root_domain', '')}"
        )
        lines.append(f"   - Query: {row.get('query', '')}")
        lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")
    write_latest_copy(out_csv, latest_csv)
    write_latest_copy(out_md, latest_md)

    print(f"OK source={input_csv}")
    print(f"OK contact_filtered={len(rows)} dedup_top={len(picked)}")
    print(f"CSV {out_csv}")
    print(f"MD {out_md}")


if __name__ == "__main__":
    main()
