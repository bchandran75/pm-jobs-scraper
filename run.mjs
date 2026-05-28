#!/usr/bin/env node
/**
 * PM Jobs Scraper — Node entrypoint (no pip/venv required).
 * Usage: node run.mjs [--category ai|tech|all] [-o output]
 */

import { readFileSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

const GREENHOUSE = "https://boards-api.greenhouse.io/v1/boards/{id}/jobs";
const LEVER = "https://api.lever.co/v0/postings/{id}?mode=json";
const ASHBY = "https://api.ashbyhq.com/posting-api/job-board/{id}";

function loadCompanies() {
  const raw = readFileSync(join(__dirname, "companies.json"), "utf8");
  return JSON.parse(raw).filter((c) => c.enabled !== false);
}

const COMPANIES = loadCompanies();

const PM_TITLE =
  /\b(product\s+manag|product\s+lead|head\s+of\s+product|chief\s+product|\bcpo\b|vp[,\/\s]+product|svp[,\/\s]+product|evp[,\/\s]+product|product\s+director|director[,\/\s]+product|gm[,\/\s]+product)\b/i;
const ABOVE_DIR =
  /\b(chief\s+product|\bcpo\b|head\s+of\s+product|\b(?:evp|svp|vp)\b|vice\s+president|senior\s+director|sr\.?\s+director|executive\s+director|president[,\/\s]+product|gm[,\/\s]+product|general\s+manager)\b/i;
const EXCLUDE =
  /\b(principal\s+product|group\s+product\s+manag|senior\s+product\s+manag|staff\s+product|associate\s+product|intern|coordinator|analyst|associate\s+director)\b/i;

const INDIA =
  /\b(india|bangalore|bengaluru|hyderabad|mumbai|delhi|ncr|gurgaon|gurugram|noida|pune|chennai)\b/i;
const TEXAS = /\b(texas|\btx\b|austin|dallas|houston|san\s+antonio|plano)\b/i;
const CA =
  /\b(california|\bca\b|san\s+francisco|\bsf\b|bay\s+area|silicon\s+valley|los\s+angeles|san\s+diego|san\s+jose|mountain\s+view|palo\s+alto|sunnyvale|cupertino|menlo\s+park)\b/i;

function region(loc) {
  if (INDIA.test(loc)) return "india";
  if (TEXAS.test(loc)) return "texas";
  if (CA.test(loc)) return "california";
  return null;
}

function isMatch(title, loc) {
  if (EXCLUDE.test(title)) return false;
  if (!PM_TITLE.test(title) || !ABOVE_DIR.test(title)) return false;
  return region(loc);
}

async function fetchJson(url) {
  const res = await fetch(url, {
    headers: { Accept: "application/json", "User-Agent": "pm-jobs-scraper/0.1" },
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

async function scrapeCompany({ name, ats, board_id: boardId, category }) {
  const out = [];
  try {
    if (ats === "greenhouse") {
      const data = await fetchJson(GREENHOUSE.replace("{id}", boardId));
      if (!data?.jobs) return out;
      for (const j of data.jobs) {
        const loc = j.location?.name || (j.offices || []).map((o) => o.name).join(", ");
        const r = isMatch(j.title || "", loc || "");
        if (r)
          out.push({
            company: name,
            category,
            title: j.title,
            location: loc,
            region: r,
            url: j.absolute_url,
            ats,
          });
      }
    } else if (ats === "lever") {
      const data = await fetchJson(LEVER.replace("{id}", boardId));
      if (!Array.isArray(data)) return out;
      for (const j of data) {
        const loc = j.categories?.location || (j.allLocations || []).join(", ");
        const r = isMatch(j.text || "", loc || "");
        if (r)
          out.push({
            company: name,
            category,
            title: j.text,
            location: loc,
            region: r,
            url: j.hostedUrl || j.applyUrl,
            ats,
          });
      }
    } else if (ats === "ashby") {
      const data = await fetchJson(ASHBY.replace("{id}", boardId));
      if (!data?.jobs) return out;
      for (const j of data.jobs) {
        const loc = j.location || (j.isRemote ? "Remote" : "");
        const r = isMatch(j.title || "", loc);
        if (r)
          out.push({
            company: name,
            category,
            title: j.title,
            location: loc,
            region: r,
            url: j.jobUrl || j.applyUrl,
            ats,
          });
      }
    }
  } catch {
    /* skip failed board */
  }
  return out;
}

const args = process.argv.slice(2);
let catFilter = "all";
let outDir = "output";
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--category" && args[i + 1]) catFilter = args[++i];
  if (args[i] === "-o" && args[i + 1]) outDir = args[++i];
}

const targets = COMPANIES.filter((c) => catFilter === "all" || c.category === catFilter);
console.log(`PM Jobs Scraper — ${targets.length} companies (from companies.json)\n`);

const results = (await Promise.all(targets.map(scrapeCompany))).flat();
const seen = new Set();
const unique = results.filter((j) => {
  if (seen.has(j.url)) return false;
  seen.add(j.url);
  return true;
});

if (!unique.length) {
  console.log("No matching roles this run.");
  console.log("Edit companies.json to add/remove companies, then re-run.");
  process.exit(1);
}

for (const j of unique) {
  console.log(`\n${j.company} | ${j.region.toUpperCase()}`);
  console.log(`  ${j.title}`);
  console.log(`  ${j.location}`);
  console.log(`  ${j.url}`);
}

await mkdir(outDir, { recursive: true });
const ts = new Date().toISOString().replace(/[:.]/g, "-");
const path = join(outDir, `pm_jobs_${ts}.json`);
const payload = {
  scraped_at: new Date().toISOString(),
  count: unique.length,
  jobs: unique,
};
await writeFile(path, JSON.stringify(payload, null, 2));
console.log(`\n${unique.length} role(s). Saved ${path}`);

if (process.env.SEND_EMAIL === "1") {
  const { spawnSync } = await import("node:child_process");
  const r = spawnSync("node", [join(__dirname, "scripts/send-results-email.mjs")], {
    stdio: "inherit",
    cwd: __dirname,
  });
  if (r.status !== 0) process.exit(r.status ?? 1);
}
