#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlparse


OFFICIAL_PATTERNS = [
    "authorized dealer",
    "official boutique",
    "official site",
    "store locator",
    "brand boutique",
    "official retailer",
    "rolex certified",
    "authorized retailer",
    "official retailer",
    "authorized seller",
    "store locations",
    "find a boutique",
    "find a store",
    "authorized service center",
    "official distributor",
    "official flagship",
    "authorized partner",
    "official showroom",
    "authorized stockist",
    "authorized reseller",
    "official store",
    "official shop",
    "official dealer",
    "official partner",
    "brand store",
    "brand official",
    "official watch dealer",
    "official watch retailer",
    "官方",
    "官网",
    "授权经销商",
    "特约零售商",
    "官方直营",
    "官方门店",
    "门店查询",
    "官方商城",
    "旗舰店",
    "专柜",
]

NON_OFFICIAL_SIGNALS = [
    "pre-owned",
    "second hand",
    "used",
    "consignment",
    "buy sell trade",
    "grey market",
    "gray market",
    "pawn",
    "pawnshop",
    "lombard",
    "reseller",
    "authentic used",
    "in stock",
    "trade-in",
    "平行进口",
    "灰市",
    "水货",
    "二手",
    "渠道商",
    "渠道",
    "典当",
    "寄售",
    "现货",
    "支持验货",
    "thu mua",
    "dong ho cu",
    "dong ho second hand",
    "đồng hồ cũ",
    "комиссионный",
    "бу часы",
]

CONTACT_HINTS = [
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
    "门店",
    "liên hệ",
    "контакты",
]


def read_lines(path: Path) -> list[str]:
    lines: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            value = line.strip()
            if value and not value.startswith("#"):
                lines.append(value)
    return lines


def clean_text(value: object) -> str:
    return " ".join(str(value or "").replace("\n", " ").split()).strip()


def domain_of(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""


def looks_official(title: str, snippet: str, url: str) -> bool:
    haystack = f"{title} {snippet} {url}".lower()
    return any(pattern in haystack for pattern in OFFICIAL_PATTERNS)


def has_non_official_signal(title: str, snippet: str, query: str) -> bool:
    haystack = f"{title} {snippet} {query}".lower()
    return any(pattern in haystack for pattern in NON_OFFICIAL_SIGNALS)


def score_lead(title: str, snippet: str, include_keywords: list[str], exclude_keywords: list[str]) -> int:
    text = f"{title} {snippet}".lower()
    score = 0
    for keyword in include_keywords:
        if keyword.lower() in text:
            score += 8
    for keyword in exclude_keywords:
        if keyword.lower() in text:
            score -= 12
    for keyword in CONTACT_HINTS:
        if keyword.lower() in text:
            score += 4
    return score


def load_rows(path: Path) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        rows = []
        with path.open("r", encoding="utf-8-sig") as handle:
            for raw in handle:
                line = raw.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        return rows
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("results"), list):
            return payload["results"]
        raise SystemExit(f"unsupported json structure: {path}")
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    raise SystemExit(f"unsupported input format: {path}")


def normalize_row(row: dict) -> dict:
    return {
        "query": clean_text(
            row.get("query")
            or row.get("search_query")
            or row.get("keyword")
        ),
        "title": clean_text(row.get("title") or row.get("name")),
        "url": clean_text(row.get("url") or row.get("link")),
        "snippet": clean_text(
            row.get("snippet")
            or row.get("content")
            or row.get("description")
            or row.get("summary")
        ),
        "source": clean_text(row.get("source") or "google"),
        "position": clean_text(row.get("position") or row.get("rank") or row.get("index")),
    }


def write_latest_copy(src: Path, latest: Path) -> None:
    latest.write_bytes(src.read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file", required=True)
    parser.add_argument("--queries-file", required=True)
    parser.add_argument("--include-file", required=True)
    parser.add_argument("--exclude-file", required=True)
    parser.add_argument("--blocked-domains-file", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--max-queries", type=int, default=25)
    parser.add_argument("--min-score", type=int, default=0)
    args = parser.parse_args()

    input_file = Path(args.input_file).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    queries = read_lines(Path(args.queries_file).resolve())[: args.max_queries]
    include_keywords = read_lines(Path(args.include_file).resolve())
    exclude_keywords = read_lines(Path(args.exclude_file).resolve())
    blocked_domains = set(read_lines(Path(args.blocked_domains_file).resolve()))

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    jsonl_path = out_dir / f"leads_{timestamp}.jsonl"
    csv_path = out_dir / f"leads_{timestamp}.csv"
    md_path = out_dir / f"summary_{timestamp}.md"
    latest_jsonl = out_dir / "latest_leads.jsonl"
    latest_csv = out_dir / "latest_leads.csv"
    latest_md = out_dir / "latest_summary.md"

    raw_rows = load_rows(input_file)
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for raw_row in raw_rows:
        row = normalize_row(raw_row)
        query = row["query"]
        title = row["title"]
        url = row["url"]
        snippet = row["snippet"]
        source = row["source"]
        position = row["position"]
        domain = domain_of(url)

        if not url or not domain or not title:
            continue
        if any(domain == blocked or domain.endswith(f".{blocked}") for blocked in blocked_domains):
            continue
        if looks_official(title, snippet, url):
            continue
        if not has_non_official_signal(title, snippet, query):
            continue

        dedupe_key = (domain, url)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        score = score_lead(title, snippet, include_keywords, exclude_keywords)
        if score < args.min_score:
            continue

        rows.append(
            {
                "score": score,
                "domain": domain,
                "title": title,
                "url": url,
                "query": query,
                "snippet": snippet[:360],
                "source": source,
                "position": position,
                "timestamp": timestamp,
            }
        )

    rows.sort(key=lambda item: item["score"], reverse=True)

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    fieldnames = [
        "score",
        "domain",
        "title",
        "url",
        "query",
        "snippet",
        "source",
        "position",
        "timestamp",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    top = rows[:30]
    summary_lines = [
        f"# Leadgen Summary ({timestamp})",
        "",
        f"- Input file: {input_file.name}",
        f"- Query seeds loaded: {len(queries)}",
        f"- Raw rows loaded: {len(raw_rows)}",
        f"- Filtered leads: {len(rows)}",
        f"- Top exported: {len(top)}",
        "- Filter policy: NON-OFFICIAL ONLY (official, authorized, store locator, and blocked domains excluded)",
        "",
        "## Top Leads",
        "",
    ]
    for index, row in enumerate(top, start=1):
        summary_lines.append(f"{index}. [{row['title']}]({row['url']})")
        summary_lines.append(
            f"   - Score: {row['score']} | Domain: {row['domain']} | Source: {row['source'] or 'n/a'}"
        )
        summary_lines.append(f"   - Query: {row['query'] or 'n/a'}")
        summary_lines.append(f"   - Note: {row['snippet']}")
        summary_lines.append("")

    md_path.write_text("\n".join(summary_lines), encoding="utf-8")
    write_latest_copy(jsonl_path, latest_jsonl)
    write_latest_copy(csv_path, latest_csv)
    write_latest_copy(md_path, latest_md)

    print(f"OK raw_rows={len(raw_rows)} leads={len(rows)}")
    print(f"CSV {csv_path}")
    print(f"JSONL {jsonl_path}")
    print(f"MD {md_path}")


if __name__ == "__main__":
    main()
