# Configuration

Reference for environment variables, `companies.json`, and filtering rules.

---

## Environment variables (`.env`)

Copy [`.env.example`](../.env.example) to `.env` in the project root. The file is **gitignored** — never commit it.

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `SMTP_HOST` | No | `smtp.mail.yahoo.com` | SMTP server hostname |
| `SMTP_PORT` | No | `587` | SMTP port (STARTTLS) |
| `SMTP_USER` | For email | — | Yahoo account used to authenticate |
| `SMTP_PASS` | For email | — | Yahoo **app password** (not login password) |
| `EMAIL_FROM` | No | `SMTP_USER` | From header |
| `EMAIL_TO` | No | `balaji.chandran@yahoo.com` | Recipient for digests |
| `GITHUB_TOKEN` | No | — | Personal access token for `scripts/push-to-github.sh` (optional; device login works without it) |
| `SEND_EMAIL` | No | unset | Set to `1` for `run.mjs` / `scrape.sh` to send mail after scrape |

### Loading behavior

| Context | How `.env` is loaded |
|---------|----------------------|
| `scheduled-run.sh` | `source .env` with `set -a` |
| `send-results-email.py` | Parses file line-by-line into `os.environ` |
| `send-results-email.mjs` / `send-results-email-smtp.mjs` | Parses file into `process.env` |
| `send-results-email.sh` | `source .env` |
| `push-to-github.sh` | `source .env` for `GITHUB_TOKEN` → `GH_TOKEN` |
| `run.mjs` | Does not load `.env` unless you `source .env` in the shell |

### Example `.env` (placeholders only)

```bash
SMTP_HOST=smtp.mail.yahoo.com
SMTP_PORT=587
SMTP_USER=your_yahoo@yahoo.com
SMTP_PASS=xxxx-xxxx-xxxx-xxxx
EMAIL_FROM=your_yahoo@yahoo.com
EMAIL_TO=recipient@yahoo.com

# Optional — GitHub push without interactive gh login
# GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```

---

## `companies.json` schema

Single JSON **array** at the project root. Shared by Python (`companies.py`) and Node (`run.mjs`). Currently **100** companies (~40 AI, ~60 tech).

**Priority AI (top of file):** OpenAI (Ashby), Anthropic (Greenhouse), Perplexity (Ashby), plus xAI, Cursor, Cognition, CoreWeave, Suno. **NVIDIA** and **Groq** are listed but `enabled: false` — their careers sites do not expose a public Greenhouse/Lever/Ashby API slug (NVIDIA uses Workday).

### Object fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Display name in results and email |
| `ats` | string | Yes | One of: `greenhouse`, `lever`, `ashby` |
| `board_id` | string | Yes | API slug from the careers URL |
| `category` | string | Yes | `ai` or `tech` — used by `--category` |
| `enabled` | boolean | No | If `false`, entry is skipped |

### Example

```json
[
  {
    "name": "OpenAI",
    "ats": "ashby",
    "board_id": "openai",
    "category": "ai"
  },
  {
    "name": "Netflix",
    "ats": "lever",
    "board_id": "netflix",
    "category": "tech",
    "enabled": false
  }
]
```

### Resolving `board_id`

| ATS | Careers URL pattern | `board_id` |
|-----|---------------------|------------|
| Greenhouse | `https://boards.greenhouse.io/{board_id}` | slug after last `/` |
| Lever | `https://jobs.lever.co/{board_id}` | company slug |
| Ashby | `https://jobs.ashbyhq.com/{board_id}` | board slug |

If a board returns 404 or empty jobs, verify the slug on the live careers site and update the entry.

---

## `config/agent.json` (Job Agent)

Used by `server.py`, the browser UI, and `search_criteria.py` when running with `--match` or `POST /api/run`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `candidateName` | string | — | Name in match summaries |
| `jobTitles` | string[] | VP/Head/CPO phrases | Substrings matched against job **title** |
| `regions` | string[] | `india`, `texas`, `california` | Allowed regions |
| `requireSeniorPmRules` | boolean | `true` | Also apply `filters.py` senior PM regex |
| `fetchDescriptions` | boolean | `false` | Greenhouse full HTML (slower) |
| `useLlmMatch` | boolean \| null | `null` | Claude refine if `ANTHROPIC_API_KEY` set |
| `apiBaseUrl` | string | `http://127.0.0.1:8765` | UI hint |

Editable in the browser UI or via `PUT /api/config`. See [AGENT.md](AGENT.md).

### Optional `.env` keys (agent)

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Optional LLM scoring after RAG |
| `CANDIDATE_NAME` | Override candidate name |
| `AGENT_PORT` | API port (default `8765`) |
| `AGENT_HOST` | Bind address (default `127.0.0.1`) |

---

### Category filter

| CLI | Effect |
|-----|--------|
| `--category ai` | Only `category: "ai"` |
| `--category tech` | Only `category: "tech"` |
| `--category all` or omitted | All enabled companies |

---

## Filter rules

Filtering happens **after** jobs are fetched from the ATS. Rules live in:

- **Python:** [`src/pm_jobs_scraper/filters.py`](../src/pm_jobs_scraper/filters.py)
- **Node:** regex constants at top of [`run.mjs`](../run.mjs)

### Title: must look like Product Management

`PM_TITLE_RE` / `PM_TITLE` matches phrases such as:

- product manag(er), product lead
- head of product, chief product, CPO
- VP/SVP/EVP + product
- product director, director + product
- GM + product

### Title: must be above Director

`ABOVE_DIRECTOR_RE` / `ABOVE_DIR` matches:

- CPO, chief product, head of product
- VP, SVP, EVP, vice president (with product context via PM title rule)
- senior director, sr. director, executive director
- president + product, GM + product, general manager

**Python only — plain Director handling:**

- If title contains `director` but **not** `senior|sr.|executive` director, it is rejected **unless** the title also contains VP, vice president, chief, CPO, or head of product.

### Title: exclusions

Rejected if matched (examples):

| Pattern | Examples excluded |
|---------|-------------------|
| `principal product` | Principal Product Manager |
| `group product manag` | Group PM |
| `senior product manag` | Senior PM |
| `staff product` | Staff PM |
| `associate product` | Associate PM |
| `intern`, `coordinator`, `analyst` | Non-PM support roles |
| `associate director` | Below target seniority |
| `product manag(er)? i{1,3}` (Python) | PM I / II / III level |

Node does not include the PM level (`I`/`II`/`III`) exclusion.

### Location: regions

A job must match **at least one** region regex on the location string.

| Region | `region` value | Example keywords |
|--------|----------------|------------------|
| India | `india` | india, bangalore, bengaluru, hyderabad, mumbai, delhi, ncr, gurgaon, gurugram, noida, pune, chennai, kolkata, ahmedabad, remote-india |
| Texas | `texas` | texas, tx, austin, dallas, fort worth, houston, san antonio, plano, irving, remote-texas |
| California | `california` | california, ca, san francisco, sf, bay area, silicon valley, los angeles, la, san diego, san jose, mountain view, palo alto, sunnyvale, cupertino, menlo park, redwood city, irvine, sacramento, oakland, berkeley, remote-california |

**Python:** `detect_region()` searches `location` **and** `title` combined.

**Node:** `region()` searches **location only**.

Remote jobs only appear if the ATS location string includes a recognized city, state, or “remote-{region}” style text.

### Match object

When all rules pass, a job becomes:

| Field | Description |
|-------|-------------|
| `company` | From `companies.json` `name` |
| `category` | `ai` or `tech` |
| `title` | Posting title |
| `location` | Best-effort location string from ATS |
| `region` | `india`, `texas`, or `california` |
| `url` | Apply or hosted URL |
| `ats` | `greenhouse`, `lever`, or `ashby` |

---

## Python-only CLI flags

| Flag | Default | Description |
|------|---------|-------------|
| `--category` | `all` | `ai`, `tech`, or `all` |
| `-o` / `--output` | `./output` | Output directory |
| `--no-save` | off | Skip JSON/CSV write |
| `--workers` | `12` | Thread pool size for company fetches |

Internal: `request_delay_s=0.05` between completed futures in `run_scrape()` (not exposed on CLI).

---

## Node-only flags

| Flag | Default | Description |
|------|---------|-------------|
| `--category` | `all` | `ai`, `tech`, or `all` |
| `-o` | `output` | Output directory |

Environment:

| Variable | Effect |
|----------|--------|
| `SEND_EMAIL=1` | Run `scripts/send-results-email.mjs` after successful scrape |

---

## Dependencies

| Runtime | Install |
|---------|---------|
| Node | `npm install` → `nodemailer` (email path only) |
| Python | `pip install -r requirements.txt` → `httpx`, `rich` |

`scrape.sh` falls back to Cursor-bundled Node if `node` is not on `PATH`.
