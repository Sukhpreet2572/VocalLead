import { useEffect, useState } from "react";
import { Menu, Construction } from "lucide-react";
import { Sidebar } from "./components/layout/Sidebar";
import { navigation } from "./components/layout/navigation";
import { Badge } from "./components/common/Badge";
import { useSystemStatus } from "./hooks/useSystemStatus";
import { Overview } from "./pages/Overview";
import { Voice } from "./pages/Voice";

function currentPage() {
  return window.location.hash.slice(1) || "overview";
}

export default function App() {
  const [page, setPage] = useState(currentPage);
  const [menuOpen, setMenuOpen] = useState(false);
  const status = useSystemStatus();
  useEffect(() => {
    const update = () => setPage(currentPage());
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, []);
  const selected = navigation.find((item) => item.id === page);
  return (
    <div className="app-shell">
      <a
        className="skip-link"
        href="#main"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("main")?.focus();
        }}
      >
        Skip to content
      </a>
      <Sidebar page={page} open={menuOpen} close={() => setMenuOpen(false)} />
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              onClick={() => setMenuOpen(true)}
              aria-label="Open navigation"
              aria-expanded={menuOpen}
              aria-controls="workspace-navigation"
            >
              <Menu size={21} />
            </button>
            <span>VocaLead AI</span>
            <span className="breadcrumb-slash">/</span>
            <strong>{selected?.label || "Page not found"}</strong>
          </div>
          <div className="topbar-status" aria-live="polite">
            <span
              className={`status-dot ${status.snapshot?.health.data ? "green" : ""}`}
            />
            <span>
              {status.loading
                ? "Checking backend"
                : status.snapshot?.health.data
                  ? "Backend connected"
                  : "Backend unavailable"}
            </span>
            <Badge>{import.meta.env.DEV ? "DEV" : "BUILD"}</Badge>
          </div>
        </header>
        <main id="main" tabIndex={-1}>
          {page === "overview" ? (
            <Overview {...status} />
          ) : page === "voice" ? (
            <Voice />
          ) : (
            <div className="placeholder panel">
              <Construction size={38} />
              <Badge>PLANNED FEATURE</Badge>
              <h1>{selected?.label || "Page not found"}</h1>
              <p>
                {selected
                  ? "This feature will be implemented in a later phase. Phase 1 establishes the application, configuration and database foundation."
                  : "Choose a page from the navigation."}
              </p>
              <a className="button" href="#overview">
                Return to overview
              </a>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
