#!/usr/bin/env node
/**
 * Email latest scrape results. Requires .env with Yahoo SMTP credentials.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import nodemailer from "nodemailer";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_DIR = join(__dirname, "..");
const OUTPUT_DIR = join(PROJECT_DIR, "output");
const DEFAULT_TO = "balaji.chandran@yahoo.com";

function loadEnv() {
  const path = join(PROJECT_DIR, ".env");
  try {
    const text = readFileSync(path, "utf8");
    for (const line of text.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const eq = trimmed.indexOf("=");
      if (eq === -1) continue;
      const key = trimmed.slice(0, eq).trim();
      let val = trimmed.slice(eq + 1).trim();
      if (
        (val.startsWith('"') && val.endsWith('"')) ||
        (val.startsWith("'") && val.endsWith("'"))
      ) {
        val = val.slice(1, -1);
      }
      if (!(key in process.env)) process.env[key] = val;
    }
  } catch {
    /* optional .env */
  }
}

function latestResultsFile() {
  let files;
  try {
    files = readdirSync(OUTPUT_DIR)
      .filter((f) => f.startsWith("pm_jobs_") && f.endsWith(".json"))
      .map((f) => ({ name: f, mtime: statSync(join(OUTPUT_DIR, f)).mtimeMs }))
      .sort((a, b) => b.mtime - a.mtime);
  } catch {
    return null;
  }
  return files[0] ? join(OUTPUT_DIR, files[0].name) : null;
}

function buildBodies(payload, scrapedAt) {
  const jobs = payload?.jobs ?? [];
  const count = payload?.count ?? jobs.length;

  const textLines = [
    `PM Jobs Scraper — ${scrapedAt}`,
    `Director+ Product roles | India, Texas, California`,
    ``,
    count === 0
      ? "No matching roles in this run."
      : `${count} matching role(s):`,
    ``,
  ];

  const htmlParts = [
    `<h2>PM Jobs Scraper</h2>`,
    `<p><strong>${scrapedAt}</strong><br>`,
    `Director+ Product Management · India / TX / CA</p>`,
  ];

  if (count === 0) {
    textLines.push("Check companies.json and filters if this is unexpected.");
    htmlParts.push("<p><em>No matching roles in this run.</em></p>");
  } else {
    htmlParts.push("<table border='1' cellpadding='8' cellspacing='0' style='border-collapse:collapse'>");
    htmlParts.push(
      "<tr><th>Company</th><th>Title</th><th>Location</th><th>Region</th><th>Link</th></tr>",
    );
    for (const j of jobs) {
      textLines.push(
        `${j.company} | ${j.region?.toUpperCase()}`,
        `  ${j.title}`,
        `  ${j.location}`,
        `  ${j.url}`,
        ``,
      );
      htmlParts.push(
        `<tr><td>${esc(j.company)}</td><td>${esc(j.title)}</td>`,
        `<td>${esc(j.location)}</td><td>${esc(j.region)}</td>`,
        `<td><a href="${esc(j.url)}">Apply</a></td></tr>`,
      );
    }
    htmlParts.push("</table>");
  }

  textLines.push("", "Full JSON attached.");
  htmlParts.push("<p><small>Full JSON results attached.</small></p>");

  return { text: textLines.join("\n"), html: htmlParts.join("\n") };
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function main() {
  loadEnv();

  const user = process.env.SMTP_USER;
  const pass = process.env.SMTP_PASS;
  const host = process.env.SMTP_HOST || "smtp.mail.yahoo.com";
  const port = Number(process.env.SMTP_PORT || 587);
  const from = process.env.EMAIL_FROM || user;
  const to = process.env.EMAIL_TO || DEFAULT_TO;

  if (!user || !pass) {
    console.error(
      "Email skipped: set SMTP_USER and SMTP_PASS in .env (copy from .env.example).",
    );
    process.exit(1);
  }

  const resultsPath = latestResultsFile();
  let payload = { count: 0, jobs: [] };
  let scrapedAt = new Date().toISOString();

  if (resultsPath) {
    const raw = readFileSync(resultsPath, "utf8");
    payload = JSON.parse(raw);
    scrapedAt = payload.scraped_at || scrapedAt;
  }

  const { text, html } = buildBodies(payload, scrapedAt);
  const subject = `[PM Jobs] ${payload.count ?? 0} director+ role(s) — ${scrapedAt.slice(0, 10)}`;

  const transporter = nodemailer.createTransport({
    host,
    port,
    secure: port === 465,
    auth: { user, pass },
  });

  const attachments = resultsPath
    ? [{ filename: resultsPath.split("/").pop(), path: resultsPath }]
    : [];

  await transporter.sendMail({
    from,
    to,
    subject,
    text,
    html,
    attachments,
  });

  console.log(`Email sent to ${to}`);
}

main().catch((err) => {
  console.error("Email failed:", err.message);
  process.exit(1);
});
