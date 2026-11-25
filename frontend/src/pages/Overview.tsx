import { useEffect, useState } from "react";
import { demoOwner } from "../services/demoOwner";
import {
  Activity,
  AudioLines,
  Check,
  Database,
  ExternalLink,
  Layers3,
  Plug,
  RefreshCw,
  Server,
  ShieldCheck,
} from "lucide-react";
import { Badge } from "../components/common/Badge";
import { API_BASE_URL } from "../services/api";
import type { ServiceSnapshot } from "../types/api";

const labels: Record<string, string> = {
  gemini: "Google Gemini",
  livekit: "LiveKit",
  deepgram: "Deepgram",
  tts: "Text-to-speech",
  google_calendar: "Google Calendar",
  hubspot: "HubSpot CRM",
};
const categories: Record<string, string> = {
  gemini: "Language & reasoning",
  livekit: "Real-time media",
  deepgram: "Speech recognition",
  tts: "Voice synthesis",
  google_calendar: "Appointment scheduling",
  hubspot: "Customer relationships",
};

type OverviewMetrics = { leads: { total: number; hot: number }; appointments: { upcoming: number }; interactions: { completed_voice_calls: number }; integrations: { failed_operations: number; pending_operations: number } };
type RecentInteraction = { id: string; interaction_type: string; ended_at: string; status: string };
type RecentEvent = { event_type: string; created_at: string };
type KnowledgeStatus = { ready: boolean; indexed_chunks: number };

function BusinessOverview({ backend, checkedAt }: { backend: boolean; checkedAt: Date | null }) {
  const [metrics, setMetrics] = useState<OverviewMetrics | null>(null);
  const [interactions, setInteractions] = useState<RecentInteraction[]>([]);
  const [events, setEvents] = useState<RecentEvent[]>([]);
  const [knowledge, setKnowledge] = useState<KnowledgeStatus | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!backend) return;
    const controller = new AbortController();
    const read = async <T,>(path: string): Promise<T> => {
      const response = await fetch(`${API_BASE_URL}${path}`, { headers: { "X-Voice-Owner": demoOwner() }, signal: controller.signal });
      if (!response.ok) throw new Error("Business metrics unavailable");
      return response.json() as Promise<T>;
    };
    void Promise.all([read<OverviewMetrics>("/analytics/overview"), read<{ items: RecentInteraction[] }>("/interactions?limit=4"),
      read<{ items: RecentEvent[] }>("/appointments/activity?limit=4"), read<KnowledgeStatus>("/knowledge/status")])
      .then(([m, i, e, k]) => { setMetrics(m); setInteractions(i.items); setEvents(e.items); setKnowledge(k); setError(""); })
      .catch(() => { if (!controller.signal.aborted) setError("Local business metrics are unavailable."); });
    return () => controller.abort();
  }, [backend, checkedAt]);
  return <><section className="status-grid" aria-label="Business metrics">
    <article className="status-card">Total leads<strong>{metrics?.leads.total ?? "—"}</strong></article>
    <article className="status-card">Hot leads<strong>{metrics?.leads.hot ?? "—"}</strong></article>
    <article className="status-card">Upcoming appointments<strong>{metrics?.appointments.upcoming ?? "—"}</strong></article>
    <article className="status-card">Completed voice calls<strong>{metrics?.interactions.completed_voice_calls ?? "—"}</strong></article>
  </section><div className="detail-grid"><section className="panel" style={{ padding: 24 }}><h2>Recent interactions</h2>{interactions.length === 0 ? <p>No recorded interactions.</p> : interactions.map(item => <p key={item.id}>{item.interaction_type === "LOCAL_DEMO" ? "Local demo" : "Voice"} · {new Date(item.ended_at).toLocaleString()} · {item.status}</p>)}</section><section className="panel" style={{ padding: 24 }}><h2>Recent business activity</h2>{events.length === 0 ? <p>No activity recorded.</p> : events.map((item, index) => <p key={`${item.created_at}-${index}`}>{item.event_type.replaceAll("_", " ")} · {new Date(item.created_at).toLocaleString()}</p>)}<p>Knowledge base: {knowledge ? knowledge.ready ? `Ready (${knowledge.indexed_chunks} chunks)` : "Not indexed" : "Unavailable"}</p><p>External sync operations: {metrics ? `${metrics.integrations.pending_operations} pending, ${metrics.integrations.failed_operations} need review` : "Unavailable"}</p></section></div>{error && <p className="error-banner" role="alert">{error}</p>}</>;
}

export function Overview({
  snapshot,
  loading,
  checkedAt,
  refresh,
}: {
  snapshot: ServiceSnapshot | null;
  loading: boolean;
  checkedAt: Date | null;
  refresh: () => void;
}) {
  const backend = !!snapshot?.health.data;
  const database = !!snapshot?.ready.data;
  const integrations = snapshot?.system.data?.integrations;
  const configured = integrations
    ? Object.values(integrations).filter((item) => item.configured).length
    : null;
  const docsUrl = API_BASE_URL.replace(/\/api\/v1$/, "") + "/docs";
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">YOUR SALES WORKSPACE</div>
          <h1>Workspace overview</h1>
          <p>A clear view of your platform, from connection to conversation.</p>
        </div>
        <button className="button" onClick={refresh} disabled={loading}>
          <RefreshCw size={16} className={loading ? "spinning" : ""} />
          {loading ? "Checking services…" : "Refresh status"}
        </button>
      </div>
      <section className="intro-panel">
        <div className="intro-copy">
          <Badge>PHASE 6 · LOCAL MVP</Badge>
          <h2>
            Your sales
            <br />
            workspace.
          </h2>
          <p>
            Review real local lead, appointment and interaction outcomes.
          </p>
          <div className="intro-tags">
            <span>
              <Check size={14} /> English, Hindi & Hinglish configured
            </span>
            <span>
              <ShieldCheck size={14} /> Backend-only credentials
            </span>
          </div>
        </div>
        <div className="signal-art" aria-hidden="true">
          <div className="signal-ring ring-outer" />
          <div className="signal-ring ring-inner" />
          <div className="signal-core">
            <AudioLines size={54} strokeWidth={1.5} />
          </div>
          <span className="signal-label">
            <span /> Voice agent · Live call unverified
          </span>
        </div>
      </section>
      <section
        className="status-grid"
        aria-label="Platform status"
        aria-live="polite"
      >
        <article className="status-card">
          <div className="card-label">
            <span>Backend API</span>
            <Server size={18} />
          </div>
          <strong>
            {loading ? "Checking…" : backend ? "Connected" : "Unavailable"}
          </strong>
          <div className="card-footer">
            <span className={`status-dot ${backend ? "green" : ""}`} />
            {snapshot?.health.data
              ? `FastAPI · v${snapshot.health.data.version}`
              : "Waiting for API response"}
          </div>
        </article>
        <article className="status-card">
          <div className="card-label">
            <span>Database</span>
            <Database size={18} />
          </div>
          <strong>
            {loading
              ? "Checking…"
              : database
                ? "Connected"
                : backend
                  ? "Unavailable"
                  : "Unknown"}
          </strong>
          <div className="card-footer">
            <span className={`status-dot ${database ? "green" : ""}`} />
            {database
              ? "Readiness query successful"
              : "Readiness not confirmed"}
          </div>
        </article>
        <article className="status-card">
          <div className="card-label">
            <span>Integration configuration</span>
            <Plug size={18} />
          </div>
          <strong>
            {configured === null ? (
              "Not checked"
            ) : (
              <>
                {configured}
                <small> / {Object.keys(integrations!).length} configured</small>
              </>
            )}
          </strong>
          <div className="card-footer">External connectivity not verified</div>
        </article>
        <article className="status-card">
          <div className="card-label">
            <span>Development phase</span>
            <Layers3 size={18} />
          </div>
          <strong>Local MVP</strong>
          <div className="card-footer">
            <span className="status-dot indigo" />
            Phase 6 · Local business workflow verified
          </div>
        </article>
      </section>
      <BusinessOverview backend={backend} checkedAt={checkedAt} />
      {!loading && snapshot?.health.error && (
        <div className="error-banner" role="alert">
          Backend: {snapshot.health.error} Start the backend and refresh.
        </div>
      )}
      {!loading && backend && snapshot?.ready.error && (
        <div className="error-banner" role="alert">
          Database readiness: {snapshot.ready.error} Check DATABASE_URL and the
          selected database.
        </div>
      )}
      <div className="detail-grid">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Connected services</h2>
              <p>Credential configuration from your backend.</p>
            </div>
            <Badge>DEVELOPMENT</Badge>
          </div>
          <div className="integration-list">
            {Object.entries(labels).map(([key, label]) => {
              const status = integrations?.[key];
              return (
                <div className="integration-row" key={key}>
                  <span className={`service-icon service-${key}`}>
                    {key === "gemini" ? (
                      "✦"
                    ) : key === "livekit" ? (
                      <AudioLines size={20} />
                    ) : (
                      label.slice(0, 1)
                    )}
                  </span>
                  <div className="integration-name">
                    <strong>{label}</strong>
                    <small>{categories[key]}</small>
                  </div>
                  <div className="integration-state">
                    <Badge tone={status?.configured ? "good" : "neutral"}>
                      {loading
                        ? "Checking"
                        : status
                          ? status.configured
                            ? "Configured"
                            : "Not configured"
                          : "Unknown"}
                    </Badge>
                    <small>
                      {status
                        ? "Connectivity not verified"
                        : "Diagnostics unavailable"}
                    </small>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="panel-note">
            <ShieldCheck size={15} />
            Local workflows do not require provider credentials.
          </div>
          {!loading && snapshot?.system.error && (
            <p className="diagnostic-error">{snapshot.system.error}</p>
          )}
        </section>
        <div className="right-panels">
          <section className="panel roadmap">
            <div className="panel-heading">
              <div>
                <h2>Capability status</h2>
                <p>Local implementation and provider verification.</p>
              </div>
              <Layers3 size={19} />
            </div>
            <ol>
              <li className="current">
                <span className="step">1</span>
                <div>
                  <strong>Platform foundation</strong>
                  <p>Application shell, API & database</p>
                  <Badge tone="good">VERIFIED LOCALLY</Badge>
                </div>
              </li>
              <li>
                <span className="step">2</span>
                <div>
                  <strong>Real-time voice agent</strong>
                  <p>Implemented; real call unverified</p>
                </div>
              </li>
              <li>
                <span className="step">3</span>
                <div>
                  <strong>Sales intelligence</strong>
                  <p>Knowledge retrieval & lead qualification locally verified</p>
                </div>
              </li>
              <li>
                <span className="step">4</span>
                <div>
                  <strong>Business automation</strong>
                  <p>Local bookings, CRM & analytics verified</p>
                </div>
              </li>
            </ol>
          </section>
          <section className="developer-panel">
            <span className="developer-icon">
              <Activity size={22} />
            </span>
            <div>
              <h3>Built to be inspectable</h3>
              <p>
                Explore the live API schema and test the foundation endpoints.
              </p>
              <a href={docsUrl} target="_blank" rel="noreferrer">
                Open API documentation <ExternalLink size={14} />
              </a>
            </div>
          </section>
        </div>
      </div>
      <footer className="page-footer">
        <span>
          VocaLead AI <span className="footer-separator">/</span> Phase 6
          development workspace
        </span>
        <span>
          {loading
            ? "Checking services…"
            : checkedAt
              ? `Last checked ${checkedAt.toLocaleTimeString()}`
              : "Not checked"}
        </span>
      </footer>
    </>
  );
}
