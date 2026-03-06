#!/usr/bin/env python3
import csv
import glob
import os
import datetime as dt
from urllib.parse import urlparse

CONTACT_SIGNALS = [
    'contact', 'whatsapp', 'wechat', 'telegram', 'zalo', 'phone', 'tel', 'address',
    '联系方式', '微信', '电话', '地址', '到店', 'liên hệ', 'контакты'
]
SECOND_LEVEL_SUFFIXES = {
    'com.cn','net.cn','org.cn','com.vn','com.ru','com.tw','com.hk','com.sg','co.uk','com.au'
}


def root_domain(host: str) -> str:
    h = (host or '').lower().strip('.')
    if not h:
        return ''
    parts = h.split('.')
    if len(parts) <= 2:
        return h
    tail2 = '.'.join(parts[-2:])
    tail3 = '.'.join(parts[-3:])
    if tail2 in SECOND_LEVEL_SUFFIXES and len(parts) >= 3:
        return '.'.join(parts[-3:])
    if tail3 in SECOND_LEVEL_SUFFIXES and len(parts) >= 4:
        return '.'.join(parts[-4:])
    return '.'.join(parts[-2:])


def has_contact_signal(row):
    txt = ' '.join([row.get('title',''), row.get('snippet',''), row.get('url',''), row.get('query','')]).lower()
    return any(k in txt for k in CONTACT_SIGNALS)


def main():
    out_dir = '/root/.openclaw/workspace/leadgen/out'
    csvs = sorted(glob.glob(os.path.join(out_dir, 'leads_*.csv')))
    if not csvs:
        raise SystemExit('no leads csv found')
    src = csvs[-1]

    rows = list(csv.DictReader(open(src, 'r', encoding='utf-8-sig')))
    rows = [r for r in rows if has_contact_signal(r)]
    rows.sort(key=lambda r: float(r.get('score', 0) or 0), reverse=True)

    picked = []
    seen = set()
    for r in rows:
        host = urlparse(r.get('url','')).netloc
        rd = root_domain(host)
        if not rd or rd in seen:
            continue
        seen.add(rd)
        r['root_domain'] = rd
        picked.append(r)
        if len(picked) >= 20:
            break

    ts = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    out_csv = os.path.join(out_dir, f'contact_ready_top20_{ts}.csv')
    out_md = os.path.join(out_dir, f'contact_ready_top20_{ts}.md')
    latest_csv = os.path.join(out_dir, 'contact_ready_top20_latest.csv')
    latest_md = os.path.join(out_dir, 'contact_ready_top20_latest.md')

    fields = ['score','root_domain','domain','title','url','query','snippet','timestamp']
    with open(out_csv, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in picked:
            w.writerow({k:r.get(k,'') for k in fields})

    lines = [
        f'# Contact Ready Top20 ({ts})',
        '',
        f'- Source file: {os.path.basename(src)}',
        f'- After contact filter: {len(rows)}',
        f'- After website dedup: {len(picked)}',
        ''
    ]
    for i, r in enumerate(picked, 1):
        lines.append(f"{i}. [{r.get('title','')}]({r.get('url','')})")
        lines.append(f"   - Score: {r.get('score','')} | Root domain: {r.get('root_domain','')}")
        lines.append(f"   - Query: {r.get('query','')}")
        lines.append('')

    open(out_md, 'w', encoding='utf-8').write('\n'.join(lines))
    open(latest_csv, 'wb').write(open(out_csv, 'rb').read())
    open(latest_md, 'wb').write(open(out_md, 'rb').read())

    print(f'OK source={src}')
    print(f'OK contact_filtered={len(rows)} dedup_top={len(picked)}')
    print(f'CSV {out_csv}')
    print(f'MD {out_md}')


if __name__ == '__main__':
    main()
