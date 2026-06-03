import { useState, useEffect } from "react";
import { bridge } from "../api";

interface Aura {
  slug: string;
  name: string;
  version: number | string;
  type: string;
  note: string;
  url: string;
}

interface WaResult {
  count: number;
  items: Aura[];
}

export function WeakAurasScreen(): JSX.Element {
  const [result, setResult] = useState<WaResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    setLoading(true);
    bridge
      .call<WaResult>("weakauras.list", {})
      .then((r) => { setResult(r); setError(null); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }
  useEffect(reload, []);

  const items = result?.items ?? [];

  return (
    <div className="page">
      <div className="page-head">
        <div className="page-title">
          WeakAuras
          <span className="badge-count">{result ? result.count : "…"}</span>
        </div>
        <div className="page-sub">Tracked Wago auras synced via the WeakAuras Companion</div>
      </div>

      <div className="page-body scroll">
        <div className="page-pad">
          {error ? (
            <div className="empty">
              <div className="eicon">!</div>
              <h3>Could not load auras</h3>
              <p>{error}</p>
            </div>
          ) : loading && !result ? (
            <div className="empty">
              <div className="spin" />
              <p>Loading auras…</p>
            </div>
          ) : items.length === 0 ? (
            <div className="empty">
              <div className="eicon">
                <svg width="26" height="26" viewBox="0 0 26 26" fill="none">
                  <path d="M14 3 7 14h6l-2 9 8-12h-6l1-8z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/>
                </svg>
              </div>
              <h3>No auras tracked</h3>
              <p>Add Wago auras from the Import tab or via the WeakAuras Companion to see them here.</p>
            </div>
          ) : (
            <div className="wa-grid">
              {items.map((a) => (
                <div className="wa-card" key={a.slug}>
                  <div className="wa-top">
                    <div className="wa-ic">
                      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                        <path d="M10 2 4 10h4l-1 6 6-8h-4l1-6z" fill="currentColor"/>
                      </svg>
                    </div>
                    <div style={{ minWidth: 0 }}>
                      <div className="wa-nm">{a.name}</div>
                      <div className="wa-au">{a.type} · v{a.version}</div>
                    </div>
                  </div>
                  {a.note && <div className="gdesc">{a.note}</div>}
                  <div className="wa-foot">
                    <span className="wa-sync">tracked</span>
                    <a
                      className="btn btn-sm btn-ghost"
                      href={a.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      wago.io
                    </a>
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
