import { useState, useEffect } from "react";
import { bridge } from "../api";
import { sourceLabel, rarityFor } from "./browseData";
import type { InstalledAddon, InstalledResult } from "./installedData";

interface Props {
  /** Bumped by the AppBar rescan button to force a reload. */
  refreshKey: number;
}

function MonoBadge({ a, size = 34 }: { a: InstalledAddon; size?: number }): JSX.Element {
  return (
    <div
      className={`mono-badge mb-${rarityFor(a as never)}`}
      style={{ width: size, height: size, fontSize: size * 0.42 }}
    >
      {a.glyph}
    </div>
  );
}

export function InstalledScreen({ refreshKey }: Props): JSX.Element {
  const [result, setResult] = useState<InstalledResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    setLoading(true);
    bridge
      .call<InstalledResult>("installed.list", {})
      .then((r) => { setResult(r); setError(null); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [refreshKey]);

  const all = result?.items ?? [];
  const q = query.trim().toLowerCase();
  const items = q ? all.filter((a) => a.name.toLowerCase().includes(q)) : all;

  return (
    <div className="page">
      <div className="page-head">
        <div className="page-title">
          Installed
          <span className="badge-count">{result ? result.count : "…"}</span>
        </div>
        <div className="page-sub">
          Manage your installed addons
          {result?.addons_path && ` · ${result.addons_path}`}
        </div>
      </div>

      <div className="inst-toolbar">
        <div className="left">
          <label className="search" style={{ width: 280 }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.4"/>
              <path d="M10.5 10.5 13 13" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
            </svg>
            <input
              placeholder="Filter installed…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
        </div>
      </div>

      <div className="page-body scroll">
        <div className="page-pad">
          {error ? (
            <div className="empty">
              <div className="eicon">!</div>
              <h3>Could not load installed addons</h3>
              <p>{error}</p>
            </div>
          ) : loading && !result ? (
            <div className="empty">
              <div className="spin" />
              <p>Scanning…</p>
            </div>
          ) : items.length === 0 ? (
            <div className="empty">
              <div className="eicon">
                <svg width="26" height="26" viewBox="0 0 26 26" fill="none">
                  <rect x="4" y="5" width="18" height="16" rx="3" stroke="currentColor" strokeWidth="1.6"/>
                  <path d="M9 11h8M9 15h5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
                </svg>
              </div>
              <h3>{q ? "No matches" : "No addons installed"}</h3>
              <p>
                {q
                  ? "Try a different filter term."
                  : "Install addons from the Browse tab, or hit Rescan to detect existing ones."}
              </p>
            </div>
          ) : (
            <div>
              <div className="ihead">
                <span />
                <span>Addon</span>
                <span>Source</span>
                <span>Version</span>
                <span style={{ justifySelf: "end" }}>Actions</span>
              </div>
              {items.map((a) => (
                <div key={a.id} className="irow">
                  <MonoBadge a={a} />
                  <div style={{ minWidth: 0 }}>
                    <div className="iname">{a.name}</div>
                    <div className="idesc">
                      {a.folders.length} folder{a.folders.length === 1 ? "" : "s"}
                      {a.interface ? ` · interface ${a.interface}` : ""}
                    </div>
                  </div>
                  <span className={`pill src-${a.source}`}>
                    <span className="dot" />
                    {sourceLabel(a.source)}
                  </span>
                  <span className="ver-mono">{a.version}</span>
                  <div className="iright">
                    <button className="btn btn-sm">Update</button>
                    <button className="btn btn-sm btn-danger">Remove</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
