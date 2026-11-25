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
          <Badge>PHASE 01 · FOUNDATION</Badge>
          <h2>
            The foundation for
            <br />
            better conversations.
          </h2>
          <p>
            Your multilingual sales platform starts here. Connect your services
            today, and build towards intelligent property conversations.
          </p>
          <div className="intro-tags">
            <span>
              <Check size={14} /> English, Hindi & Hinglish planned
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
            <span /> Voice agent · Coming in Phase 2
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
          <strong>Foundation</strong>
          <div className="card-footer">
            <span className="status-dot indigo" />
            Phase 1 · Infrastructure & connectivity
          </div>
        </article>
      </section>
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
            Optional credentials are not required for Phase 1.
          </div>
          {!loading && snapshot?.system.error && (
            <p className="diagnostic-error">{snapshot.system.error}</p>
          )}
        </section>
        <div className="right-panels">
          <section className="panel roadmap">
            <div className="panel-heading">
              <div>
                <h2>Development roadmap</h2>
                <p>A deliberate path to your first AI call.</p>
              </div>
              <Layers3 size={19} />
            </div>
            <ol>
              <li className="current">
                <span className="step">1</span>
                <div>
                  <strong>Platform foundation</strong>
                  <p>Application shell, API & database</p>
                  <Badge tone="good">CURRENT PHASE</Badge>
                </div>
              </li>
              <li>
                <span className="step">2</span>
                <div>
                  <strong>Real-time voice agent</strong>
                  <p>Multilingual conversations & memory</p>
                </div>
              </li>
              <li>
                <span className="step">3</span>
                <div>
                  <strong>Sales intelligence</strong>
                  <p>Knowledge retrieval & lead qualification</p>
                </div>
              </li>
              <li>
                <span className="step">4</span>
                <div>
                  <strong>Business automation</strong>
                  <p>Bookings, CRM sync & analytics</p>
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
          VocaLead AI <span className="footer-separator">/</span> Phase 1
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
