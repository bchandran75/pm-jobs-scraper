#!/usr/bin/env node
/** SMTP email without external dependencies (Yahoo-compatible). */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { connect } from "node:net";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import tls from "node:tls";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_DIR = join(__dirname, "..");
const OUTPUT_DIR = join(PROJECT_DIR, "output");
const DEFAULT_TO = "balaji.chandran@yahoo.com";

function loadEnv() {
  try {
    for (const line of readFileSync(join(PROJECT_DIR, ".env"), "utf8").split("\n")) {
      const t = line.trim();
      if (!t || t.startsWith("#") || !t.includes("=")) continue;
      const i = t.indexOf("=");
      const k = t.slice(0, i).trim();
      let v = t.slice(i + 1).trim().replace(/^['"]|['"]$/g, "");
      if (!(k in process.env)) process.env[k] = v;
    }
  } catch {
    /* */
  }
}

function latestJson() {
  const files = readdirSync(OUTPUT_DIR)
    .filter((f) => f.startsWith("pm_jobs_") && f.endsWith(".json"))
    .map((f) => ({ f, m: statSync(join(OUTPUT_DIR, f)).mtimeMs }))
    .sort((a, b) => b.m - a.m);
  return files[0] ? join(OUTPUT_DIR, files[0].f) : null;
}

function buildBodies(payload, scrapedAt) {
  const jobs = payload?.jobs ?? [];
  const count = payload?.count ?? jobs.length;
  let text = `PM Jobs Scraper — ${scrapedAt}\nDirector+ PM · India / TX / CA\n\n`;
  let html = `<h2>PM Jobs Scraper</h2><p><strong>${scrapedAt}</strong></p>`;
  if (!count) {
    text += "No matching roles in this run.\n";
    html += "<p><em>No matching roles.</em></p>";
  } else {
    text += `${count} role(s):\n\n`;
    html += "<ul>";
    for (const j of jobs) {
      text += `${j.company} | ${(j.region || "").toUpperCase()}\n  ${j.title}\n  ${j.location}\n  ${j.url}\n\n`;
      html += `<li><b>${j.company}</b> — <a href="${j.url}">${j.title}</a> (${j.location})</li>`;
    }
    html += "</ul>";
  }
  return { text, html };
}

function cmd(socket, line) {
  return new Promise((resolve, reject) => {
    const onData = (buf) => {
      const s = buf.toString();
      const code = parseInt(s.slice(0, 3), 10);
      if (code >= 400) {
        socket.off("data", onData);
        reject(new Error(s.trim()));
      } else if (/^\d{3} /.test(s) && !/^\d{3}-/.test(s.split("\n").pop())) {
        socket.off("data", onData);
        resolve(s);
      }
    };
    socket.on("data", onData);
    socket.write(line + "\r\n");
  });
}

async function sendMail({ host, port, user, pass, from, to, subject, text, html, attachmentPath }) {
  const boundary = `----pmjobs_${Date.now()}`;
  let body = "";

  if (attachmentPath) {
    const raw = readFileSync(attachmentPath);
    const b64 = raw.toString("base64");
    const fname = attachmentPath.split("/").pop();
    body =
      `Content-Type: multipart/mixed; boundary="${boundary}"\r\n\r\n` +
      `--${boundary}\r\nContent-Type: multipart/alternative; boundary="${boundary}_alt"\r\n\r\n` +
      `--${boundary}_alt\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n${text}\r\n\r\n` +
      `--${boundary}_alt\r\nContent-Type: text/html; charset=utf-8\r\n\r\n${html}\r\n\r\n` +
      `--${boundary}_alt--\r\n\r\n` +
      `--${boundary}\r\nContent-Type: application/json; name="${fname}"\r\n` +
      `Content-Transfer-Encoding: base64\r\nContent-Disposition: attachment; filename="${fname}"\r\n\r\n` +
      b64.match(/.{1,76}/g).join("\r\n") +
      `\r\n--${boundary}--`;
  } else {
    body =
      `Content-Type: multipart/alternative; boundary="${boundary}"\r\n\r\n` +
      `--${boundary}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n${text}\r\n\r\n` +
      `--${boundary}\r\nContent-Type: text/html; charset=utf-8\r\n\r\n${html}\r\n\r\n` +
      `--${boundary}--`;
  }

  const message =
    `From: ${from}\r\nTo: ${to}\r\nSubject: ${subject}\r\nMIME-Version: 1.0\r\n${body}`;

  await new Promise((resolve, reject) => {
    const socket = connect(port, host, async () => {
      try {
        await waitGreet(socket);
        await cmd(socket, `EHLO localhost`);
        await cmd(socket, "STARTTLS");
        const secure = tls.connect({ socket, servername: host }, async () => {
          try {
            await cmd(secure, `EHLO localhost`);
            await cmd(secure, "AUTH LOGIN");
            await cmd(secure, Buffer.from(user).toString("base64"));
            await cmd(secure, Buffer.from(pass).toString("base64"));
            await cmd(secure, `MAIL FROM:<${from}>`);
            await cmd(secure, `RCPT TO:<${to}>`);
            await cmd(secure, "DATA");
            secure.write(message.replace(/\n/g, "\r\n") + "\r\n.\r\n");
            await cmd(secure, "QUIT");
            secure.end();
            resolve();
          } catch (e) {
            reject(e);
          }
        });
      } catch (e) {
        reject(e);
      }
    });
    socket.on("error", reject);
  });
}

function waitGreet(socket) {
  return new Promise((resolve, reject) => {
    socket.once("data", (d) => {
      if (String(d).startsWith("220")) resolve();
      else reject(new Error(String(d)));
    });
    socket.on("error", reject);
  });
}

loadEnv();
const user = process.env.SMTP_USER;
const pass = process.env.SMTP_PASS;
const host = process.env.SMTP_HOST || "smtp.mail.yahoo.com";
const port = Number(process.env.SMTP_PORT || 587);
const from = process.env.EMAIL_FROM || user;
const to = process.env.EMAIL_TO || DEFAULT_TO;

if (!user || !pass) {
  console.error("Missing SMTP_USER or SMTP_PASS in .env");
  process.exit(1);
}

const path = latestJson();
let payload = { count: 0, jobs: [] };
let scrapedAt = new Date().toISOString();
if (path) {
  payload = JSON.parse(readFileSync(path, "utf8"));
  scrapedAt = payload.scraped_at || scrapedAt;
}

const { text, html } = buildBodies(payload, scrapedAt);
const subject = `[PM Jobs] ${payload.count ?? 0} director+ role(s) — ${scrapedAt.slice(0, 10)}`;

await sendMail({ host, port, user, pass, from, to, subject, text, html, attachmentPath: path });
console.log(`Email sent to ${to}`);
