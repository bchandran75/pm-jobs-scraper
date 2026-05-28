# Troubleshooting

## Browser UI

### `ERR_CONNECTION_REFUSED` on http://127.0.0.1:8765

Nothing is listening on port 8765.

```bash
cd ~/projects/pm-jobs-scraper
python3 server.py
```

Verify:

```bash
curl http://127.0.0.1:8765/api/health
# {"ok": true, "version": 2}
```

### Page loads but shows “Cannot reach API”

- You may have opened `ui/index.html` as a **file** (`file://`). Use **http://127.0.0.1:8765/** instead.
- Server not running (see above).
- Wrong port — check `AGENT_PORT` in `.env`.

### Scrape fails with `not found`

An **old** server process is running without newer API routes. Restart:

```bash
kill $(lsof -t -i:8765) 2>/dev/null
python3 server.py
```

Hard refresh the browser (`Cmd+Shift+R`).

### Scrape runs forever / feels stuck

Normal for **All** categories (~100 HTTP calls). Expect **30–90 seconds**.

Speed tips:

- Category: **AI only**
- Uncheck **LLM refine**
- `fetchDescriptions: false` in `config/agent.json`
- Disable unused companies with `"enabled": false`

### No jobs in results

1. **Regions** — role must match `india`, `texas`, or `california` in location/title.
2. **Job titles** — must match at least one phrase in `jobTitles` (and senior PM rules if enabled).
3. **Board slug** — wrong `board_id` or `ats` in `companies.json` returns empty (404).
4. **NVIDIA / Groq** — listed but may be `enabled: false` (no public API).

---

## Scheduled scraper (launchd)

```bash
launchctl print gui/$(id -u)/com.pm-jobs-scraper
tail -50 logs/scraper.log
```

Re-install:

```bash
./scripts/install-schedule.sh
```

---

## Email

- Use Yahoo **app password**, not login password.
- Confirm `.env` has `SMTP_USER`, `SMTP_PASS`, `EMAIL_TO`.
- Test: `python3 scripts/send-results-email.py` after a scrape.

---

## GitHub push

```bash
# Token in .env (repo scope)
GITHUB_TOKEN=ghp_...

./scripts/push-to-github.sh
```

Or standard git:

```bash
git remote add origin https://github.com/bchandran75/pm-jobs-scraper.git
git push -u origin main
```
