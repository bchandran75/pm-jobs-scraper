# Operations

Install, run, monitor, and troubleshoot the PM Jobs Scraper on macOS.

**Repository:** https://github.com/bchandran75/pm-jobs-scraper

---

## Initial setup

```bash
git clone https://github.com/bchandran75/pm-jobs-scraper.git
cd pm-jobs-scraper

# Scraper (pick one or both)
chmod +x scrape.sh
./scrape.sh

# Optional Python + CSV
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run.py

# Email
cp .env.example .env
# Edit .env with Yahoo app password (see CONFIGURATION.md)

# Optional: nodemailer for Node email path
npm install

# 24h schedule
chmod +x scripts/*.sh scrape.sh
./scripts/install-schedule.sh
```

`install-schedule.sh` will:

- Create `logs/` and `output/`
- Run `npm install` if `npm` is available
- Copy `.env.example` → `.env` if `.env` is missing
- Install `~/Library/LaunchAgents/com.pm-jobs-scraper.plist`
- Bootstrap the LaunchAgent (runs once immediately, then every 24h)

---

## Manual runs

### Node (quick)

```bash
./scrape.sh
./scrape.sh --category ai
node run.mjs -o /tmp/pm-out
```

### Python

```bash
source .venv/bin/activate   # if using venv
python run.py
python run.py --category tech --no-save
python run.py -o ./output --workers 8
```

### Scrape + email

```bash
source .env
./scrape.sh && python3 scripts/send-results-email.py
# or
source .env && SEND_EMAIL=1 ./scrape.sh
```

### Email only (uses latest `output/pm_jobs_*.json`)

```bash
source .env
./scripts/send-results-email.sh
python3 scripts/send-results-email.py
node scripts/send-results-email-smtp.mjs
node scripts/send-results-email.mjs   # requires npm install
```

---

## Scheduled runs

| Component | Path |
|-----------|------|
| LaunchAgent label | `com.pm-jobs-scraper` |
| Installed plist | `~/Library/LaunchAgents/com.pm-jobs-scraper.plist` |
| Template (source) | `launchd/com.pm-jobs-scraper.plist.template` |
| Wrapper script | `scripts/scheduled-run.sh` |

### Runtime selection

`scheduled-run.sh` chooses:

1. **Python** — if `.venv/bin/python` exists and is executable
2. **Node** — else if `scrape.sh` is executable
3. **Error** — if neither is available

Email runs after every scrape attempt (skipped if `SMTP_USER` / `SMTP_PASS` missing).

### Check status

```bash
launchctl print gui/$(id -u)/com.pm-jobs-scraper
```

Look for `state = running` or last exit status in the output.

### Uninstall schedule

```bash
./scripts/uninstall-schedule.sh
```

### Change interval or time

Edit the **installed** plist (not only the template):

```bash
open ~/Library/LaunchAgents/com.pm-jobs-scraper.plist
```

- **Every N seconds:** `StartInterval` (current: `86400`)
- **Daily at fixed time:** remove `StartInterval`, add:

```xml
<key>StartCalendarInterval</key>
<dict>
  <key>Hour</key>
  <integer>8</integer>
  <key>Minute</key>
  <integer>0</integer>
</dict>
```

Then reload:

```bash
./scripts/uninstall-schedule.sh
./scripts/install-schedule.sh
```

---

## Logs

| File | Contents |
|------|----------|
| `logs/scraper.log` | Timestamped lines from `scheduled-run.sh` (start/finish, Python vs Node, email result) |
| `logs/launchd.out.log` | launchd stdout from the wrapper |
| `logs/launchd.err.log` | launchd stderr |

### Tail logs live

```bash
tail -f logs/scraper.log
tail -f logs/launchd.err.log
```

### Example log lines

```
[2026-05-17T12:00:00Z] === PM jobs scraper started ===
[2026-05-17T12:01:30Z] Finished (Node).
[2026-05-17T12:01:35Z] Results emailed to user@yahoo.com (SMTP).
[2026-05-17T12:01:35Z] === PM jobs scraper done ===
```

---

## Output artifacts

| Pattern | Description |
|---------|-------------|
| `output/pm_jobs_*.json` | Latest scrape payload |
| `output/pm_jobs_*.csv` | Python runs only |

Old files are **not** auto-deleted; prune manually if disk space matters.

Email scripts always attach the **most recently modified** `pm_jobs_*.json`.

---

## Push to GitHub

```bash
./scripts/push-to-github.sh
```

- Target: `bchandran75/pm-jobs-scraper`
- Downloads `gh` to `.tools/` if needed
- Skips secrets and generated dirs (see README)
- Optional: set `GITHUB_TOKEN` in `.env` for API auth

---

## Troubleshooting

### No matches / exit code 1

| Cause | What to do |
|-------|------------|
| Filters are strict | Inspect raw boards in browser; confirm titles/locations |
| Wrong `board_id` | Fix slug in `companies.json` |
| No roles in target geo | Expected — not every company posts IN/TX/CA director+ PM roles |
| Python vs Node difference | Try both; Python may match region from title text |

### Board fetch errors

- Check network; APIs must be reachable without VPN blocks
- 404 on Greenhouse/Lever usually means bad `board_id`
- Ashby may return 403 for some boards — treated as empty in Python

### Email not sent

| Symptom | Fix |
|---------|-----|
| `Email skipped — add SMTP_USER and SMTP_PASS` | Fill `.env`; use Yahoo **app password** |
| `Email failed` in log | Verify 2FA + app password; check `SMTP_HOST`/`SMTP_PORT` |
| nodemailer path fails | Run `npm install` or use `send-results-email.py` / `send-results-email-smtp.mjs` |
| No attachment | Run scrape first so `output/pm_jobs_*.json` exists |

### launchd not running

- Confirm you are **logged in** (LaunchAgent is per GUI user)
- Re-run `./scripts/install-schedule.sh`
- Read `logs/launchd.err.log` for permission or path errors
- Ensure `scripts/scheduled-run.sh` is executable

### Node not found

- Install Node.js, or rely on `scrape.sh` Cursor helper path
- For schedule, prefer creating `.venv` so Python path is used

### Python / venv issues

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Scheduled runs auto-detect `.venv/bin/python`.

### Xcode / python3 missing (macOS)

Use Node path: `./scrape.sh` — does not require Xcode CLI tools.

---

## Security operations

- Rotate Yahoo app password if `.env` was ever shared or committed
- Never commit `.env`; confirm `git status` does not list it before push
- `output/` and `logs/` are gitignored but may contain personal job-search data — back up or delete as needed

---

## Related docs

- [README.md](../README.md) — overview and quick start
- [ARCHITECTURE.md](ARCHITECTURE.md) — modules and ATS APIs
- [CONFIGURATION.md](CONFIGURATION.md) — env vars and filter reference
