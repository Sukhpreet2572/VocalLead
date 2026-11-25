import { AudioLines, PanelLeftClose, X } from "lucide-react";
import { navigation } from "./navigation";

export function Sidebar({
  page,
  open,
  close,
}: {
  page: string;
  open: boolean;
  close: () => void;
}) {
  return (
    <>
      {open && (
        <button
          className="sidebar-overlay"
          aria-label="Close navigation"
          onClick={close}
        />
      )}
      <aside
        id="workspace-navigation"
        className={`sidebar ${open ? "is-open" : ""}`}
        aria-label="Main navigation"
      >
        <a className="brand" href="#overview" onClick={close}>
          <span className="brand-mark">
            <AudioLines size={23} />
          </span>
          <span>
            VocaLead<span className="brand-ai">AI</span>
            <small>SALES INTELLIGENCE</small>
          </span>
        </a>
        <button
          className="mobile-close icon-button"
          onClick={close}
          aria-label="Close navigation"
        >
          <X size={20} />
        </button>
        <div className="workspace">
          <span className="workspace-icon">V</span>
          <div>
            Real estate workspace<small>Development environment</small>
          </div>
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav>
          {navigation.map(({ id, label, icon: Icon }) => (
            <a
              key={id}
              className={`nav-item ${page === id ? "active" : ""}`}
              href={`#${id}`}
              onClick={close}
              aria-current={page === id ? "page" : undefined}
            >
              <Icon size={19} />
              <span>{label}</span>
              {id === "voice" && <span className="nav-future">Soon</span>}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="phase-note">
            <span className="phase-square">
              <PanelLeftClose size={17} />
            </span>
            <div>
              Building the foundation
              <small>Phase 1 of the development roadmap</small>
            </div>
          </div>
          <div className="profile">
            <span className="avatar">DV</span>
            <div>
              Developer workspace<small>Local development</small>
            </div>
            <span className="profile-dot" />
          </div>
        </div>
      </aside>
    </>
  );
}
