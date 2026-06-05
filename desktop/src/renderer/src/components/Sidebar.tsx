import { useState, useEffect } from "react";
import { bridge } from "../api";
import type { Screen } from "../App";

interface Props {
  screen: Screen;
  onNav: (s: Screen) => void;
  addonCount: number;
  updateCount?: number;
  refreshKey?: number;
}

const NAV: { id: Screen; label: string; icon: JSX.Element }[] = [
  {
    id: "browse",
    label: "Browse",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.4"/>
        <path d="M10.5 10.5 13 13" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    id: "installed",
    label: "Installed",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M3 9l3.5 3.5L13 5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  {
    id: "weakauras",
    label: "WeakAuras",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M8 2.5 5.5 7h5L8 2.5z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
        <rect x="4.5" y="8.5" width="7" height="5" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      </svg>
    ),
  },
  {
    id: "backups",
    label: "Backups",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <rect x="3" y="4.5" width="10" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
        <path d="M6 4.5V3a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v1.5M8 7v4M6 9h4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    id: "health",
    label: "Health",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M8 13.5C8 13.5 2 9.8 2 5.5a3.5 3.5 0 0 1 6-2.45A3.5 3.5 0 0 1 14 5.5c0 4.3-6 8-6 8z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
      </svg>
    ),
  },
  {
    id: "history",
    label: "History",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.4"/>
        <path d="M8 4.5V8l2.5 1.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  {
    id: "settings",
    label: "Settings",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.4"/>
        <path d="M8 2v1.5M8 12.5V14M2 8h1.5M12.5 8H14M3.6 3.6l1.1 1.1M11.3 11.3l1.1 1.1M12.4 3.6l-1.1 1.1M4.7 11.3l-1.1 1.1" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
      </svg>
    ),
  },
];

export function Sidebar({ screen, onNav, addonCount, updateCount = 0, refreshKey = 0 }: Props): JSX.Element {
  const [flavor, setFlavor] = useState<string>("—");
  const [addonsPath, setAddonsPath] = useState<string>("");

  useEffect(() => {
    bridge.call<{ active_profile: string; profiles: Array<{ id: string; flavor: string; addons_path: string }> }>(
      "settings.get", {}
    ).then((s) => {
      const active = s.profiles.find((p) => p.id === s.active_profile);
      if (active) {
        setFlavor(active.flavor);
        setAddonsPath(active.addons_path);
      }
    }).catch(() => {});
  }, [refreshKey]);

  return (
    <nav className="sidebar">
      <div className="side-label">Library</div>
      {NAV.map((item) => (
        <button
          key={item.id}
          className={`nav-item${screen === item.id ? " active" : ""}`}
          onClick={() => onNav(item.id)}
        >
          {item.icon}
          {item.label}
          {item.id === "installed" && updateCount > 0 && (
            <span className="count count-update" title={`${updateCount} update${updateCount === 1 ? "" : "s"} available`}>
              {updateCount} ↑
            </span>
          )}
          {item.id === "installed" && updateCount === 0 && addonCount > 0 && (
            <span className="count">{addonCount}</span>
          )}
        </button>
      ))}
      <div className="grow" />
      <div className="side-foot">
        <div className="frow">
          <span>{flavor}</span>
          <span className={`v${addonsPath ? "" : " missing"}`}>{addonsPath ? "active" : "path not set"}</span>
        </div>
        <div className="usage"><i style={{ width: "0%" }} /></div>
      </div>
    </nav>
  );
}
