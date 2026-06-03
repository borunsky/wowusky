import { useState, useEffect, useRef } from "react";
import type { Theme, Density } from "../App";

interface Flavor {
  tag: string;
  name: string;
}

const FLAVORS: Flavor[] = [
  { tag: "retail", name: "World of Warcraft" },
  { tag: "classic", name: "WoW Classic" },
  { tag: "cata", name: "Cataclysm Classic" },
];

interface Props {
  version: string;
  theme: Theme;
  density: Density;
  onThemeChange: (t: Theme) => void;
  onDensityChange: (d: Density) => void;
  onRescan: () => void;
  rescanning?: boolean;
}

export function AppBar({ version, theme, density: _density, onThemeChange, onDensityChange: _onDensityChange, onRescan, rescanning }: Props): JSX.Element {
  const [flavorIdx, setFlavorIdx] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const flavor = FLAVORS[flavorIdx];

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  return (
    <div className="appbar">
      <div className="brand">
        <div className="logo">W</div>
        <span className="name">wowusky</span>
        {version !== "…" && <span className="ver">v{version}</span>}
      </div>

      <div className="dropdown" ref={menuRef}>
        <button
          className={`flavor-pick${menuOpen ? " on" : ""}`}
          onClick={() => setMenuOpen((o) => !o)}
        >
          <span className="fp-tag">{flavor.tag}</span>
          <span style={{ flex: 1 }}>{flavor.name}</span>
          <svg className="chev" width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M3 5l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
        {menuOpen && (
          <div className="menu">
            <div className="menu-label">Game version</div>
            {FLAVORS.map((f, i) => (
              <button
                key={f.tag}
                className={`menu-item${i === flavorIdx ? " on" : ""}`}
                onClick={() => { setFlavorIdx(i); setMenuOpen(false); }}
              >
                {f.name}
                <span className="fp-tag">{f.tag}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="spacer" />

      <button
        className="iconbtn"
        title="Rescan addons"
        onClick={onRescan}
        disabled={rescanning}
      >
        {rescanning ? (
          <span className="spin" />
        ) : (
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M13.5 8A5.5 5.5 0 1 1 8 2.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            <path d="M8 2.5 10.5 5 8 7.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        )}
      </button>

      <div className="theme-toggle">
        {(["dark", "system", "light"] as Theme[]).map((t) => (
          <button
            key={t}
            className={theme === t ? "on" : ""}
            title={t.charAt(0).toUpperCase() + t.slice(1)}
            onClick={() => onThemeChange(t)}
          >
            {t === "dark" && (
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M12 7.6A5 5 0 1 1 6.4 2a4 4 0 0 0 5.6 5.6z" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
              </svg>
            )}
            {t === "system" && (
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <rect x="2" y="2" width="10" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
                <path d="M5.5 12h3M7 9v3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
              </svg>
            )}
            {t === "light" && (
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <circle cx="7" cy="7" r="2.5" stroke="currentColor" strokeWidth="1.4"/>
                <path d="M7 1.5V3M7 11v1.5M1.5 7H3M11 7h1.5M3.1 3.1l1.1 1.1M9.8 9.8l1.1 1.1M10.9 3.1 9.8 4.2M4.2 9.8 3.1 10.9" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
              </svg>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
