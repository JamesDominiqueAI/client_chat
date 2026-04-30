import Head from "next/head";
import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";

import { ChatBox } from "../components/ChatBox";
import { authHeaders, Complaint, exportUrl, fetchJson, IntegrationStatus, ObservabilityMetrics, reportUrl } from "../lib/api";

export default function Home() {
  const [complaints, setComplaints] = useState<Complaint[]>([]);
  const [priority, setPriority] = useState("all");
  const [category, setCategory] = useState("all");
  const [error, setError] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<ObservabilityMetrics | null>(null);
  const [metricsError, setMetricsError] = useState<string | null>(null);
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([]);
  const [authToken, setAuthToken] = useState("");
  const [password, setPassword] = useState("");
  const [adminMessage, setAdminMessage] = useState<string | null>(null);
  const [adminError, setAdminError] = useState<string | null>(null);

  useEffect(() => {
    setAuthToken(window.localStorage.getItem("managerToken") || "");
  }, []);

  useEffect(() => {
    if (!authToken) {
      setComplaints([]);
      setMetrics(null);
      setIntegrations([]);
      return;
    }
    fetchJson<Complaint[]>("/api/complaints", { headers: authHeaders(authToken) })
      .then(setComplaints)
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load complaints."));
  }, [authToken]);

  async function refreshMetrics() {
    try {
      setMetricsError(null);
      if (!authToken) {
        setMetrics(null);
        return;
      }
      const result = await fetchJson<ObservabilityMetrics>("/api/observability/metrics", { headers: authHeaders(authToken) });
      setMetrics(result);
    } catch (err) {
      setMetricsError(err instanceof Error ? err.message : "Unable to load metrics.");
    }
  }

  useEffect(() => {
    void refreshMetrics();
    if (!authToken) {
      setIntegrations([]);
      return;
    }
    fetchJson<{ integrations: IntegrationStatus[] }>("/api/integrations", { headers: authHeaders(authToken) })
      .then((result) => setIntegrations(result.integrations))
      .catch(() => setIntegrations([]));
  }, [authToken]);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAdminError(null);
    setAdminMessage(null);
    try {
      const result = await fetchJson<{ token: string; role: string }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      window.localStorage.setItem("managerToken", result.token);
      setAuthToken(result.token);
      setPassword("");
      setAdminMessage("Manager login active.");
    } catch (err) {
      setAdminError(err instanceof Error ? err.message : "Login failed.");
    }
  }

  async function importCsv(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    setAdminError(null);
    setAdminMessage(null);
    try {
      const csvText = await file.text();
      const result = await fetchJson<{ imported: number; message: string }>("/api/complaints/import", {
        method: "POST",
        headers: authHeaders(authToken),
        body: JSON.stringify({ csvText }),
      });
      setAdminMessage(result.message);
      setComplaints(await fetchJson<Complaint[]>("/api/complaints", { headers: authHeaders(authToken) }));
      await refreshMetrics();
    } catch (err) {
      setAdminError(err instanceof Error ? err.message : "CSV import failed.");
    } finally {
      event.target.value = "";
    }
  }

  const categories = useMemo(() => Array.from(new Set(complaints.map((item) => item.category))).sort(), [complaints]);
  const filtered = complaints.filter((item) => {
    const priorityMatch = priority === "all" || item.priority === priority;
    const categoryMatch = category === "all" || item.category === category;
    return priorityMatch && categoryMatch;
  });
  const urgent = complaints.filter((item) => item.priority === "urgent" && item.status === "open").length;
  const negative = complaints.filter((item) => item.sentiment === "negative").length;

  return (
    <>
      <Head>
        <title>Customer Report Agent</title>
        <meta name="description" content="MCP customer support reporting chatbot for managers." />
      </Head>
      <main>
        <section className="hero">
          <div>
            <p className="eyebrow">MCP Customer Report Agent</p>
            <h1>Customer Report Agent</h1>
            <p className="lede">
              A support-manager workspace that turns raw complaints into urgent-case lists, recurring issue summaries,
              sentiment snapshots, action plans, CSV exports, and manager-ready reports.
            </p>
            <div className="hero-actions">
              <a className="button primary" href="#chat">
                Open chat
              </a>
              <a className={`button ${authToken ? "" : "disabled"}`} href={authToken ? exportUrl(authToken) : "#admin"}>
                Export CSV
              </a>
              <a className={`button ${authToken ? "" : "disabled"}`} href={authToken ? reportUrl(authToken) : "#admin"}>
                Download report
              </a>
            </div>
          </div>
          <div className="hero-metrics">
            <article>
              <strong>{complaints.length || "..."}</strong>
              <span>Total complaints</span>
            </article>
            <article>
              <strong>{urgent || "..."}</strong>
              <span>Urgent open</span>
            </article>
            <article>
              <strong>{negative || "..."}</strong>
              <span>Negative sentiment</span>
            </article>
          </div>
        </section>

        <section id="chat" className="page-section">
          <ChatBox authToken={authToken} />
        </section>

        <section className="page-section">
          <div className="evidence-header">
            <div className="section-heading">
              <p className="eyebrow">Production Evidence</p>
              <h2>Live tool metrics, guardrail counts, and export readiness.</h2>
            </div>
            <button className="button" type="button" onClick={refreshMetrics}>
              Refresh metrics
            </button>
          </div>

          <div className="evidence-grid">
            <article>
              <span>Total chat runs</span>
              <strong>{metrics?.requests.total ?? "..."}</strong>
            </article>
            <article>
              <span>Guardrail blocks</span>
              <strong>{metrics?.requests.guarded ?? "..."}</strong>
            </article>
            <article>
              <span>P95 latency</span>
              <strong>{metrics ? `${metrics.requests.p95LatencyMs} ms` : "..."}</strong>
            </article>
            <article>
              <span>MCP servers</span>
              <strong>{metrics?.mcpServers.counts.total ?? 10}</strong>
            </article>
            <article>
              <span>Internal MCP</span>
              <strong>{metrics?.mcpServers.counts.internal ?? 5}</strong>
            </article>
            <article>
              <span>External MCP</span>
              <strong>{metrics?.mcpServers.counts.external ?? 5}</strong>
            </article>
          </div>

          {metricsError ? <p className="error">{metricsError}</p> : null}

          <div className="production-grid">
            <article className="production-panel">
              <h3>Recent tool events</h3>
              {!authToken ? (
                <p className="muted">Manager login is required to view traces and MCP activity.</p>
              ) : metrics?.recentEvents.length ? (
                <div className="event-list">
                  {metrics.recentEvents
                    .slice()
                    .reverse()
                    .map((event) => (
                      <div key={event.traceId}>
                        <span>{event.tool}</span>
                        <strong>{event.connection}</strong>
                        <small>{event.mcpServer} / {event.traceId.slice(0, 8)} / {event.latencyMs} ms</small>
                      </div>
                    ))}
                </div>
              ) : (
                <p className="muted">Run a chat prompt to populate recent tool activity.</p>
              )}
            </article>

            <article className="production-panel">
              <h3>Trace spans</h3>
              {!authToken ? (
                <p className="muted">Manager login is required to inspect traces.</p>
              ) : metrics?.traces.recentSpans.length ? (
                <div className="event-list">
                  {metrics.traces.recentSpans
                    .slice()
                    .reverse()
                    .map((span) => (
                      <div key={`${span.traceId}-${span.name}`}>
                        <span>{span.name}</span>
                        <strong>{span.durationMs} ms</strong>
                        <small>{span.traceId.slice(0, 8)}</small>
                      </div>
                    ))}
                </div>
              ) : (
                <p className="muted">Run a chat prompt to generate OpenTelemetry-style spans.</p>
              )}
            </article>

            <article className="production-panel">
              <h3>Demo readiness</h3>
              <ul className="readiness-list">
                <li>10 MCP servers are registered: 5 internal analysis servers and 5 external integration servers.</li>
                <li>MCP tool route returns tool, source, trace, session, and latency metadata.</li>
                <li>Security prompt routes to `security_guardrail` without exposing private data.</li>
                <li>CRM, ticketing, status, Slack, and email adapters fail safely when unconfigured.</li>
                <li>CSV and markdown report downloads use the same complaint dataset as chat.</li>
                <li>OpenTelemetry-style recent spans are exposed in observability metrics.</li>
                <li>The manager workspace is authenticated by default instead of being fully public.</li>
              </ul>
              <div className="hero-actions">
                <a className={`button ${authToken ? "" : "disabled"}`} href={authToken ? exportUrl(authToken) : "#admin"}>
                  CSV
                </a>
                <a className={`button ${authToken ? "" : "disabled"}`} href={authToken ? reportUrl(authToken) : "#admin"}>
                  Report
                </a>
              </div>
            </article>
          </div>
        </section>

        <section className="page-section">
          <div className="section-heading">
            <p className="eyebrow">Admin</p>
            <h2>Manager login, CSV import, and external MCP connection status.</h2>
          </div>

          <div id="admin" className="admin-grid">
            <article className="production-panel">
              <h3>Manager access</h3>
              {authToken ? (
                <div className="auth-state">
                  <p className="muted">Authenticated as manager.</p>
                  <button
                    className="button"
                    type="button"
                    onClick={() => {
                      window.localStorage.removeItem("managerToken");
                      setAuthToken("");
                      setAdminMessage("Manager session cleared.");
                    }}
                  >
                    Sign out
                  </button>
                </div>
              ) : (
                <form className="admin-form" onSubmit={login}>
                  <label>
                    Manager password
                    <input
                      type="password"
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      placeholder="manager-demo"
                    />
                  </label>
                  <button className="button primary" type="submit">
                    Sign in
                  </button>
                </form>
              )}
              {adminMessage ? <p className="success">{adminMessage}</p> : null}
              {adminError ? <p className="error">{adminError}</p> : null}
            </article>

            <article className="production-panel">
              <h3>Complaint import</h3>
              <p className="muted">Upload a CSV with the export headers to replace the complaint dataset used by chat, exports, and reports.</p>
              <label className={authToken ? "file-control" : "file-control disabled"}>
                CSV file
                <input type="file" accept=".csv,text/csv" disabled={!authToken} onChange={importCsv} />
              </label>
            </article>
          </div>

          <div className="integration-grid">
            {integrations.map((integration) => (
              <article className="integration-card" key={integration.mcpServer}>
                <div>
                  <h3>{integration.name}</h3>
                  <p>{integration.mcpServer}</p>
                </div>
                <span className={`status-pill ${integration.status}`}>
                  {integration.status === "connected" ? "Connected" : "Not configured"}
                </span>
                <small>{integration.envVar}</small>
              </article>
            ))}
          </div>
        </section>

        <section className="page-section">
          <div className="section-heading">
            <p className="eyebrow">Complaint Browser</p>
            <h2>Filter the same dataset used by the MCP tools.</h2>
          </div>

          <div className="filters">
            <label>
              Priority
              <select value={priority} onChange={(event) => setPriority(event.target.value)}>
                <option value="all">All priorities</option>
                <option value="urgent">Urgent</option>
                <option value="high">High</option>
                <option value="normal">Normal</option>
              </select>
            </label>
            <label>
              Category
              <select value={category} onChange={(event) => setCategory(event.target.value)}>
                <option value="all">All categories</option>
                {categories.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <a className={`button ${authToken ? "" : "disabled"}`} href={authToken ? exportUrl(authToken) : "#admin"}>
              Download CSV
            </a>
            <a className={`button ${authToken ? "" : "disabled"}`} href={authToken ? reportUrl(authToken) : "#admin"}>
              Download report
            </a>
          </div>

          {error ? <p className="error">{error}</p> : null}

          <div className="complaint-list">
            {filtered.map((item) => (
              <article className="complaint-card" key={item.id}>
                <div>
                  <p className="card-meta">
                    {item.id} / {item.category} / {item.channel}
                  </p>
                  <h3>{item.issue}</h3>
                  <p>{item.summary}</p>
                </div>
                <div className="card-footer">
                  <span className={`pill ${item.priority}`}>{item.priority}</span>
                  <span className={`pill ${item.sentiment}`}>{item.sentiment}</span>
                  <span>{item.customer}</span>
                </div>
              </article>
            ))}
          </div>
        </section>
      </main>
    </>
  );
}
