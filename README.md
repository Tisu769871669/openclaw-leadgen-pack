# OpenClaw Leadgen Migration Pack

This pack migrates the non-official dealer leadgen pipeline to another OpenClaw server.

## What it includes
- `leadgen_tavily.py`: Tavily collector with NON-OFFICIAL hard filter
- `postprocess_contact_top20.py`: contact-signal filter + website dedup Top20
- `run_leadgen.sh`: one-shot runner
- `queries.txt`: seed queries (watch/luxury reseller scenarios)
- `include_keywords.txt` / `exclude_keywords.txt` / `blocked_domains.txt`

## Target paths (server)
- Base: `/root/.openclaw/workspace/leadgen`
- Output: `/root/.openclaw/workspace/leadgen/out`

## Quick install (on target server)
1. Upload this folder to server (for example to `/root/openclaw-leadgen-pack`).
2. Run:
   ```bash
   bash /root/openclaw-leadgen-pack/install_on_server.sh
   ```
3. Set Tavily key (example uses systemd override):
   ```bash
   mkdir -p /root/.config/systemd/user/openclaw-gateway.service.d
   cat >/root/.config/systemd/user/openclaw-gateway.service.d/override.conf <<'EOF'
   [Service]
   Environment=TAVILY_API_KEY=YOUR_TAVILY_KEY
   EOF
   systemctl --user daemon-reload
   systemctl --user restart openclaw-gateway.service
   ```
4. Run once:
   ```bash
   bash /root/.openclaw/workspace/leadgen/run_leadgen.sh
   python3 /root/.openclaw/workspace/leadgen/postprocess_contact_top20.py
   ```
5. Optional cron (every 4h at minute 20):
   ```bash
   (crontab -l 2>/dev/null | grep -v 'leadgen/run_leadgen.sh'; \
    echo '20 */4 * * * bash /root/.openclaw/workspace/leadgen/run_leadgen.sh >> /root/.openclaw/workspace/leadgen/out/leadgen_cron.log 2>&1') | crontab -
   ```

## Output files
- `leads_*.csv` / `leads_*.jsonl`
- `summary_*.md` / `latest_summary.md`
- `contact_ready_top20_*.csv` / `contact_ready_top20_latest.csv`

## Notes
- No secrets are stored in this pack.
- You can tune keywords in `queries.txt` and filters in `include/exclude/blocked` files.
