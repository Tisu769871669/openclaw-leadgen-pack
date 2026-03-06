#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import json
import os
import re
import urllib.request
from urllib.parse import urlparse


def read_lines(path):
    out = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            s = line.strip()
            if s and not s.startswith('#'):
                out.append(s)
    return out


def load_tavily_key():
    key = os.getenv('TAVILY_API_KEY', '').strip()
    if key:
        return key
    override = '/root/.config/systemd/user/openclaw-gateway.service.d/override.conf'
    if os.path.exists(override):
        txt = open(override, 'r', encoding='utf-8').read()
        m = re.search(r'Environment=TAVILY_API_KEY=([^\n]+)', txt)
        if m:
            return m.group(1).strip().strip('"')
    return ''


def call_tavily(api_key, query, max_results=5, timeout=25):
    payload = {
        'api_key': api_key,
        'query': query,
        'search_depth': 'basic',
        'max_results': max_results,
        'include_answer': False,
        'include_images': False,
        'include_raw_content': False,
    }
    req = urllib.request.Request(
        'https://api.tavily.com/search',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8', 'ignore'))


def domain_of(url):
    try:
        return (urlparse(url).netloc or '').lower()
    except Exception:
        return ''


OFFICIAL_PATTERNS = [
    'authorized dealer', 'official boutique', 'official site', 'store locator',
    'brand boutique', 'official retailer', 'rolex certified',
    '授权经销商', '特约零售商', '官方直营', '官方门店', '门店查询', '官方商城', '旗舰店', '专柜',
]
NON_OFFICIAL_SIGNALS = [
    'pre-owned', 'second hand', 'used', 'consignment', 'buy sell trade',
    'grey market', 'gray market', 'pawn', 'pawnshop', 'lombard',
    '平行进口', '灰市', '水货', '二手', '渠道商', '渠道', '典当', '寄售', '现货', '支持验货',
    'thu mua', 'đồng hồ cũ', 'комиссионный', 'бу часы',
]


def looks_official(title, content, url):
    txt = f"{title} {content} {url}".lower()
    return any(k in txt for k in OFFICIAL_PATTERNS)


def has_non_official_signal(title, content, query):
    txt = f"{title} {content} {query}".lower()
    return any(k in txt for k in NON_OFFICIAL_SIGNALS)


def score_lead(title, content, include_keywords, exclude_keywords):
    text = f"{title} {content}".lower()
    score = 0
    for kw in include_keywords:
        if kw.lower() in text:
            score += 8
    for kw in exclude_keywords:
        if kw.lower() in text:
            score -= 12
    for kw in ['contact', 'whatsapp', 'wechat', 'telegram', '地址', '电话', '联系方式', '门店']:
        if kw in text:
            score += 4
    return score


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--queries-file', required=True)
    p.add_argument('--include-file', required=True)
    p.add_argument('--exclude-file', required=True)
    p.add_argument('--blocked-domains-file', required=True)
    p.add_argument('--max-results', type=int, default=5)
    p.add_argument('--max-queries', type=int, default=20)
    p.add_argument('--out-dir', required=True)
    args = p.parse_args()

    api_key = load_tavily_key()
    if not api_key:
        raise SystemExit('ERROR: TAVILY_API_KEY not found')

    queries = read_lines(args.queries_file)[: args.max_queries]
    include_kw = read_lines(args.include_file)
    exclude_kw = read_lines(args.exclude_file)
    blocked = set(read_lines(args.blocked_domains_file))

    ts = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs(args.out_dir, exist_ok=True)
    jsonl_path = os.path.join(args.out_dir, f'leads_{ts}.jsonl')
    csv_path = os.path.join(args.out_dir, f'leads_{ts}.csv')
    md_path = os.path.join(args.out_dir, f'summary_{ts}.md')
    latest_md = os.path.join(args.out_dir, 'latest_summary.md')

    seen = set()
    rows = []

    for q in queries:
        try:
            results = call_tavily(api_key, q, max_results=args.max_results).get('results', [])
        except Exception:
            continue
        for r in results:
            url = (r.get('url') or '').strip()
            title = (r.get('title') or '').strip()
            content = (r.get('content') or '').replace('\n', ' ').strip()
            domain = domain_of(url)
            if not url or not domain:
                continue
            if any(domain == b or domain.endswith('.' + b) for b in blocked):
                continue
            if looks_official(title, content, url):
                continue
            if not has_non_official_signal(title, content, q):
                continue
            key = (domain, url)
            if key in seen:
                continue
            seen.add(key)
            score = score_lead(title, content, include_kw, exclude_kw)
            if score < 0:
                continue
            rows.append({
                'score': score,
                'query': q,
                'domain': domain,
                'title': title,
                'url': url,
                'snippet': content[:360],
                'timestamp': ts,
            })

    rows.sort(key=lambda x: x['score'], reverse=True)

    with open(jsonl_path, 'w', encoding='utf-8') as jf:
        for row in rows:
            jf.write(json.dumps(row, ensure_ascii=False) + '\n')

    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as cf:
        w = csv.DictWriter(cf, fieldnames=['score', 'domain', 'title', 'url', 'query', 'snippet', 'timestamp'])
        w.writeheader()
        for row in rows:
            w.writerow(row)

    top = rows[:30]
    lines = [
        f'# Leadgen Summary ({ts})',
        '',
        f'- Total leads: {len(rows)}',
        f'- Top exported: {len(top)}',
        '- Filter policy: NON-OFFICIAL ONLY (official/authorized/store-locator excluded)',
        '',
        '## Top Leads',
        ''
    ]
    for i, r in enumerate(top, 1):
        lines.append(f"{i}. [{r['title']}]({r['url']})")
        lines.append(f"   - Score: {r['score']} | Domain: {r['domain']}")
        lines.append(f"   - Query: {r['query']}")
        lines.append(f"   - Note: {r['snippet']}")
        lines.append('')

    with open(md_path, 'w', encoding='utf-8') as mf:
        mf.write('\n'.join(lines))
    with open(latest_md, 'w', encoding='utf-8') as lf:
        lf.write('\n'.join(lines))

    print(f'OK leads={len(rows)}')
    print(f'CSV {csv_path}')
    print(f'JSONL {jsonl_path}')
    print(f'MD {md_path}')


if __name__ == '__main__':
    main()
