import { useState, useCallback, useEffect } from "react";

const DEFAULT_API = "http://127.0.0.1:8765";

async function api(base, path, options = {}) {
  const res = await fetch(`${base}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `API ${res.status}`);
  return data;
}

const TIER_STYLES = {
  strong: { border: "#16a34a", badge: "#dcfce7", badgeText: "#166534", label: "🟢 Strong" },
  good: { border: "#1a6ef7", badge: "#dbeafe", badgeText: "#1e40af", label: "🔵 Good" },
  low: { border: "#d1d5db", badge: "#f3f4f6", badgeText: "#6b7280", label: "⚪ Low" },
};

function getTier(score) {
  return score >= 80 ? "strong" : score >= 60 ? "good" : "low";
}

function JobCard({ job, candidateName }) {
  const [open, setOpen] = useState(false);
  const score = job.matchScore || 0;
  const tier = job.matchTier || getTier(score);
  const s = TIER_STYLES[tier] || TIER_STYLES.low;

  return (
    <div style={{
      background: "#fff", border: "1px solid #e5e7eb", borderLeft: `4px solid ${s.border}`,
      borderRadius: 12, padding: "16px 20px", marginBottom: 12, boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 8 }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 15 }}>{job.title}</div>
          <div style={{ fontSize: 13, color: "#6b7280", marginTop: 2 }}>{job.company}</div>
        </div>
        <span style={{ background: s.badge, color: s.badgeText, padding: "4px 10px", borderRadius: 20, fontSize: 12, fontWeight: 600 }}>
          {s.label} · {score}%
        </span>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 10, fontSize: 12, color: "#6b7280" }}>
        {job.location && <span>📍 {job.location}</span>}
        {job.region && <span>🌐 {job.region}</span>}
        {job.ats && <span>📋 {job.ats}</span>}
      </div>

      <div style={{ borderTop: "1px solid #f3f4f6", paddingTop: 10 }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: "#9ca3af", textTransform: "uppercase", marginBottom: 6 }}>RAG match</div>
        <div style={{ fontSize: 13, color: "#374151", lineHeight: 1.65, marginBottom: 8 }}>{job.summary}</div>

        <button onClick={() => setOpen(!open)} style={{ fontSize: 12, color: "#6b7280", background: "none", border: "none", cursor: "pointer", padding: 0 }}>
          {open ? "▾" : "▸"} Strengths, gaps & resume evidence
        </button>

        {open && (
          <div style={{ marginTop: 10 }}>
            {(job.strengths || []).map((x, i) => (
              <div key={i} style={{ fontSize: 12, marginBottom: 4 }}><span style={{ color: "#16a34a" }}>✓</span> {x}</div>
            ))}
            {(job.gaps || []).map((x, i) => (
              <div key={i} style={{ fontSize: 12, marginBottom: 4 }}><span style={{ color: "#dc2626" }}>△</span> {x}</div>
            ))}
            {(job.resumeEvidence || []).map((x, i) => (
              <div key={i} style={{ fontSize: 11, color: "#6b7280", fontStyle: "italic", marginBottom: 4, paddingLeft: 8, borderLeft: "2px solid #e5e7eb" }}>{x}</div>
            ))}
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
        {job.url && (
          <a href={job.url} target="_blank" rel="noreferrer" style={{
            fontSize: 12, padding: "6px 12px", border: "1px solid #e5e7eb", borderRadius: 8, color: "#374151", textDecoration: "none",
          }}>🔗 Apply / view posting</a>
        )}
        <button onClick={() => window.sendPrompt?.(
          `Write a tailored cover letter for ${candidateName} applying to ${job.title} at ${job.company}. Use only facts from their resume.`
        )} style={{ fontSize: 12, padding: "6px 12px", border: "1px solid #e5e7eb", borderRadius: 8, background: "none", cursor: "pointer" }}>
          ✏️ Cover letter ↗
        </button>
      </div>
    </div>
  );
}

function StepRow({ n, label, status }) {
  const col = status === "done" ? "#16a34a" : status === "active" ? "#1a6ef7" : "#d1d5db";
  const textCol = status === "active" ? "#1e40af" : status === "done" ? "#166534" : "#9ca3af";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 14px", borderRadius: 8,
      background: status === "active" ? "#eff6ff" : status === "done" ? "#f0fdf4" : "#f9fafb", marginBottom: 6 }}>
      <div style={{ width: 24, height: 24, borderRadius: "50%", background: col, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700 }}>
        {status === "done" ? "✓" : status === "active" ? "⟳" : n}
      </div>
      <span style={{ fontSize: 13, color: textCol }}>{label}</span>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState("setup");
  const [apiBase, setApiBase] = useState(DEFAULT_API);
  const [candidateName, setCandidateName] = useState("Balaji Chandran");
  const [resume, setResume] = useState("");
  const [companiesJson, setCompaniesJson] = useState("[]");
  const [category, setCategory] = useState("all");
  const [useLlm, setUseLlm] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [step, setStep] = useState(0);
  const [error, setError] = useState(null);
  const [filterMatch, setFilterMatch] = useState("all");
  const [filterRegion, setFilterRegion] = useState("all");
  const [apiOk, setApiOk] = useState(null);
  const [usedLlm, setUsedLlm] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        await api(apiBase, "/api/health");
        setApiOk(true);
        const cfg = await api(apiBase, "/api/config");
        if (cfg.candidateName) setCandidateName(cfg.candidateName);
        if (cfg.apiBaseUrl) setApiBase(cfg.apiBaseUrl);
        const r = await api(apiBase, "/api/resume");
        setResume(r.resume || "");
        const c = await api(apiBase, "/api/companies");
        setCompaniesJson(JSON.stringify(c.companies, null, 2));
      } catch {
        setApiOk(false);
      }
    })();
  }, [apiBase]);

  const saveCompanies = useCallback(async () => {
    const rows = JSON.parse(companiesJson);
    await api(apiBase, "/api/companies", { method: "PUT", body: JSON.stringify({ companies: rows }) });
  }, [apiBase, companiesJson]);

  const saveResume = useCallback(async () => {
    await api(apiBase, "/api/resume", { method: "PUT", body: JSON.stringify({ resume }) });
  }, [apiBase, resume]);

  const run = useCallback(async () => {
    setError(null);
    setJobs([]);
    setTab("results");
    setStep(1);
    try {
      await saveResume();
      setStep(2);
      try { await saveCompanies(); } catch (e) { /* allow run with last saved companies */ console.warn(e); }
      setStep(3);
      const data = await api(apiBase, "/api/run", {
        method: "POST",
        body: JSON.stringify({ category, resume, candidateName, useLlm }),
      });
      setJobs(data.jobs || []);
      setUsedLlm(!!data.usedLlm);
      setStep(4);
    } catch (e) {
      setError(e.message);
      setStep(0);
    }
  }, [apiBase, category, resume, candidateName, useLlm, saveResume, saveCompanies]);

  const filtered = jobs
    .filter((j) => {
      const s = j.matchScore || 0;
      if (filterMatch === "strong") return s >= 80;
      if (filterMatch === "good") return s >= 60 && s < 80;
      if (filterMatch === "low") return s < 60;
      return true;
    })
    .filter((j) => filterRegion === "all" || j.region === filterRegion)
    .sort((a, b) => (b.matchScore || 0) - (a.matchScore || 0));

  const strong = jobs.filter((j) => (j.matchScore || 0) >= 80).length;
  const avg = jobs.length ? Math.round(jobs.reduce((s, j) => s + (j.matchScore || 0), 0) / jobs.length) : 0;

  const inputStyle = { width: "100%", fontSize: 13, padding: "8px 10px", border: "1px solid #e5e7eb", borderRadius: 8 };

  return (
    <div style={{ fontFamily: "'DM Sans', system-ui, sans-serif", maxWidth: 800, margin: "0 auto", padding: "20px 16px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
        <div style={{ width: 40, height: 40, background: "#1a6ef7", borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20 }}>🤖</div>
        <div>
          <div style={{ fontWeight: 700, fontSize: 18 }}>PM Leadership Job Agent</div>
          <div style={{ fontSize: 12, color: "#6b7280" }}>Live ATS scrape · RAG resume match · {candidateName}</div>
        </div>
      </div>

      {apiOk === false && (
        <div style={{ background: "#fef3c7", border: "1px solid #fcd34d", borderRadius: 10, padding: 12, marginBottom: 16, fontSize: 13 }}>
          Start the API: <code>python3 server.py</code> in pm-jobs-scraper (port 8765).
        </div>
      )}

      <div style={{ display: "flex", gap: 4, background: "#f3f4f6", borderRadius: 10, padding: 4, marginBottom: 20 }}>
        {["setup", "results"].map((t) => (
          <button key={t} onClick={() => setTab(t)} style={{
            flex: 1, padding: "8px 12px", fontSize: 13, fontWeight: tab === t ? 600 : 400,
            border: tab === t ? "1px solid #e5e7eb" : "none", borderRadius: 8, cursor: "pointer",
            background: tab === t ? "#fff" : "transparent", color: tab === t ? "#111827" : "#6b7280",
          }}>
            {t === "setup" ? "⚙️ Setup" : `📋 Results${jobs.length ? ` (${jobs.length})` : ""}`}
          </button>
        ))}
      </div>

      {tab === "setup" && (
        <div>
          <div style={{ background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: 10, padding: 12, marginBottom: 16, fontSize: 13, color: "#1e40af" }}>
            Scrapes real jobs from Greenhouse/Lever/Ashby boards in <strong>companies.json</strong>, then matches using RAG over your resume (TF-IDF chunks; optional Claude refine).
          </div>

          <label style={{ fontSize: 12, fontWeight: 600, color: "#6b7280", display: "block", marginBottom: 5 }}>API base URL</label>
          <input value={apiBase} onChange={(e) => setApiBase(e.target.value)} style={{ ...inputStyle, marginBottom: 14 }} />

          <label style={{ fontSize: 12, fontWeight: 600, color: "#6b7280", display: "block", marginBottom: 5 }}>Candidate name</label>
          <input value={candidateName} onChange={(e) => setCandidateName(e.target.value)} style={{ ...inputStyle, marginBottom: 14 }} />

          <label style={{ fontSize: 12, fontWeight: 600, color: "#6b7280", display: "block", marginBottom: 5 }}>
            Resume (RAG index) <span style={{ fontWeight: 400, color: "#16a34a" }}>chunked on save</span>
          </label>
          <textarea value={resume} onChange={(e) => setResume(e.target.value)} rows={8} style={{ ...inputStyle, fontFamily: "monospace", fontSize: 11, resize: "vertical", marginBottom: 8, lineHeight: 1.6 }} />
          <button onClick={saveResume} style={{ fontSize: 12, marginBottom: 16, padding: "6px 12px", borderRadius: 8, border: "1px solid #e5e7eb", background: "#fff", cursor: "pointer" }}>
            Save resume to RAG store
          </button>

          <label style={{ fontSize: 12, fontWeight: 600, color: "#6b7280", display: "block", marginBottom: 5 }}>
            Companies (companies.json)
          </label>
          <textarea value={companiesJson} onChange={(e) => setCompaniesJson(e.target.value)} rows={6} style={{ ...inputStyle, fontFamily: "monospace", fontSize: 10, marginBottom: 8 }} />
          <button onClick={saveCompanies} style={{ fontSize: 12, marginBottom: 16, padding: "6px 12px", borderRadius: 8, border: "1px solid #e5e7eb", background: "#fff", cursor: "pointer" }}>
            Save companies list
          </button>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: "#6b7280", display: "block", marginBottom: 5 }}>Company category</label>
              <select value={category} onChange={(e) => setCategory(e.target.value)} style={inputStyle}>
                <option value="all">All (AI + tech)</option>
                <option value="ai">AI only</option>
                <option value="tech">Tech only</option>
              </select>
            </div>
            <div style={{ display: "flex", alignItems: "end" }}>
              <label style={{ fontSize: 12, display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                <input type="checkbox" checked={useLlm} onChange={(e) => setUseLlm(e.target.checked)} />
                LLM refine (needs ANTHROPIC_API_KEY on server)
              </label>
            </div>
          </div>

          <button onClick={run} disabled={apiOk === false} style={{
            width: "100%", padding: 12, fontSize: 14, fontWeight: 600, background: apiOk === false ? "#9ca3af" : "#1a6ef7",
            color: "#fff", border: "none", borderRadius: 10, cursor: apiOk === false ? "not-allowed" : "pointer",
          }}>
            🤖 Scrape boards & RAG-match resume
          </button>
        </div>
      )}

      {tab === "results" && (
        <div>
          {step > 0 && step < 4 && (
            <div style={{ marginBottom: 20 }}>
              <StepRow n={1} label="Saving resume to RAG index…" status={step === 1 ? "active" : step > 1 ? "done" : "pending"} />
              <StepRow n={2} label="Saving companies.json…" status={step === 2 ? "active" : step > 2 ? "done" : "pending"} />
              <StepRow n={3} label="Scraping ATS boards & matching…" status={step === 3 ? "active" : step > 3 ? "done" : "pending"} />
              <StepRow n={4} label="Done" status={step === 4 ? "done" : "pending"} />
            </div>
          )}

          {error && (
            <div style={{ background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 10, padding: 14, marginBottom: 16 }}>
              <div style={{ fontWeight: 600, color: "#991b1b" }}>Error</div>
              <pre style={{ fontSize: 11, whiteSpace: "pre-wrap" }}>{error}</pre>
            </div>
          )}

          {jobs.length > 0 && (
            <>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 10, marginBottom: 16 }}>
                {[
                  { val: jobs.length, lbl: "Live roles scraped" },
                  { val: strong, lbl: "Strong matches" },
                  { val: avg + "%", lbl: "Avg RAG score" },
                ].map((m) => (
                  <div key={m.lbl} style={{ background: "#f9fafb", border: "1px solid #e5e7eb", borderRadius: 10, padding: 14 }}>
                    <div style={{ fontSize: 24, fontWeight: 700 }}>{m.val}</div>
                    <div style={{ fontSize: 12, color: "#6b7280" }}>{m.lbl}</div>
                  </div>
                ))}
              </div>
              {usedLlm && <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 12 }}>Scoring used Claude + RAG context.</div>}

              <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
                <select value={filterMatch} onChange={(e) => setFilterMatch(e.target.value)} style={{ fontSize: 12, padding: 6, borderRadius: 8, border: "1px solid #e5e7eb" }}>
                  <option value="all">All matches</option>
                  <option value="strong">Strong 80%+</option>
                  <option value="good">Good 60–79%</option>
                  <option value="low">Low &lt;60%</option>
                </select>
                <select value={filterRegion} onChange={(e) => setFilterRegion(e.target.value)} style={{ fontSize: 12, padding: 6, borderRadius: 8, border: "1px solid #e5e7eb" }}>
                  <option value="all">All regions</option>
                  <option value="india">India</option>
                  <option value="texas">Texas</option>
                  <option value="california">California</option>
                </select>
              </div>

              {filtered.map((job, i) => <JobCard key={job.url || i} job={job} candidateName={candidateName} />)}
            </>
          )}

          {step === 0 && !error && jobs.length === 0 && (
            <div style={{ textAlign: "center", padding: "3rem", color: "#9ca3af" }}>Run the agent from Setup.</div>
          )}
        </div>
      )}
    </div>
  );
}
