import { useState, useEffect } from "react";
import { bridge } from "../api";

interface Aura {
  slug: string;
  name: string;
  version: number | string;
  latest_version: number | string;
  has_update: boolean;
  type: string;
  note: string;
  author: string;
  modified: string;
  url: string;
}

interface WaResult {
  count: number;
  items: Aura[];
}

interface SearchHit {
  slug: string;
  name: string;
  author: string;
  type: string;
}

export function WeakAurasScreen(): JSX.Element {
  const [result, setResult] = useState<WaResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [updating, setUpdating] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // Search & track (#48)
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [tracking, setTracking] = useState<string | null>(null);
  // Import / companion (#49 / #50)
  const [importing, setImporting] = useState(false);
  const [generating, setGenerating] = useState(false);

  function reload() {
    setLoading(true);
    bridge
      .call<WaResult>("weakauras.list", {})
      .then((r) => { setResult(r); setError(null); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }
  useEffect(reload, []);

  function runSearch() {
    const q = query.trim();
    if (!q) { setHits(null); return; }
    setSearching(true);
    setNotice(null);
    bridge.call<{ items: SearchHit[] }>("wago.search", { query: q })
      .then((r) => setHits(r.items ?? []))
      .catch((e) => setNotice(String(e)))
      .finally(() => setSearching(false));
  }

  function track(hit: SearchHit) {
    setTracking(hit.slug);
    bridge.call<{ ok: boolean; error?: string }>("wago.add", { slug: hit.slug, name: hit.name })
      .then((r) => {
        if (!r.ok) { setNotice(r.error ?? "could not track aura"); return; }
        setNotice(`Now tracking ${hit.name}`);
        setHits((hs) => (hs ?? []).filter((h) => h.slug !== hit.slug));
        reload();
      })
      .catch((e) => setNotice(String(e)))
      .finally(() => setTracking(null));
  }

  function importFromWow() {
    setImporting(true);
    setNotice(null);
    bridge.call<{ ok: boolean; added: number; existing: number; failed: number; error?: string }>(
      "wago.importFromSavedVariables", {})
      .then((r) => {
        if (!r.ok) { setNotice(r.error ?? "import failed"); return; }
        setNotice(`Imported ${r.added} new (${r.existing} already tracked${r.failed ? `, ${r.failed} failed` : ""})`);
        reload();
      })
      .catch((e) => setNotice(String(e)))
      .finally(() => setImporting(false));
  }

  function generateCompanion() {
    setGenerating(true);
    setNotice(null);
    bridge.call<{ ok: boolean; count: number; error?: string }>("wago.generateCompanion", {})
      .then((r) => {
        if (!r.ok) { setNotice(r.error ?? "generation failed"); return; }
        setNotice(`Companion generated with ${r.count} aura${r.count === 1 ? "" : "s"} — run /reload in-game`);
      })
      .catch((e) => setNotice(String(e)))
      .finally(() => setGenerating(false));
  }

  function checkUpdates() {
    setChecking(true);
    setNotice(null);
    bridge.call<{ updates: string[]; count: number }>("wago.checkUpdates", {})
      .then((r) => {
        setNotice(r.count > 0 ? `${r.count} update${r.count === 1 ? "" : "s"} available` : "All auras up to date");
        reload();
      })
      .catch((e) => setNotice(String(e)))
      .finally(() => setChecking(false));
  }

  function updateAura(slug: string) {
    setUpdating(slug);
    setNotice(null);
    bridge.call<{ ok: boolean; error?: string }>("wago.update", { slug })
      .then((r) => {
        if (r.ok) reload();
        else setNotice(r.error ?? "update failed");
      })
      .catch((e) => setNotice(String(e)))
      .finally(() => setUpdating(null));
  }

  function updateAll() {
    setUpdating("__all__");
    setNotice(null);
    bridge.call<{ ok: boolean; updated: string[]; failed: string[] }>("wago.updateAll", {})
      .then((r) => {
        const n = r.updated?.length ?? 0;
        setNotice(`Updated ${n} aura${n === 1 ? "" : "s"}${r.failed?.length ? `, ${r.failed.length} failed` : ""}`);
        reload();
      })
      .catch((e) => setNotice(String(e)))
      .finally(() => setUpdating(null));
  }

  const items = result?.items ?? [];
  const updateCount = items.filter((a) => a.has_update).length;

  return (
    <div className="page">
      <div className="page-head">
        <div className="page-title">
          WeakAuras
          <span className="badge-count">{result ? items.length : "…"}</span>
          {updateCount > 0 && <span className="badge-upd">{updateCount} update{updateCount === 1 ? "" : "s"}</span>}
        </div>
        <div className="page-sub">Tracked Wago auras synced via the WeakAuras Companion</div>
      </div>

      <div className="page-body scroll">
        <div className="page-pad">
          {notice && <div className="wa-notice">{notice}</div>}

          {/* Toolbar — search + actions */}
          <div className="wa-toolbar">
            <div className="wa-search">
              <input
                type="text"
                placeholder="Search wago.io…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") runSearch(); }}
              />
              <button className="btn btn-sm" onClick={runSearch} disabled={searching || !query.trim()}>
                {searching ? "…" : "Search"}
              </button>
              {hits !== null && (
                <button className="btn btn-sm btn-ghost" onClick={() => { setHits(null); setQuery(""); }}>
                  Clear
                </button>
              )}
            </div>
            <div className="wa-actions">
              <button className="btn btn-sm" onClick={importFromWow} disabled={importing}>
                {importing ? "Importing…" : "Import from WoW"}
              </button>
              <button className="btn btn-sm" onClick={generateCompanion} disabled={generating || items.length === 0}>
                {generating ? "Generating…" : "Generate Companion"}
              </button>
              <button className="btn btn-sm" onClick={checkUpdates} disabled={checking || updating !== null}>
                {checking ? "Checking…" : "Check for Updates"}
              </button>
              {updateCount > 0 && (
                <button className="btn btn-sm btn-accent" onClick={updateAll} disabled={updating !== null}>
                  {updating === "__all__" ? "Updating…" : `Update All (${updateCount})`}
                </button>
              )}
            </div>
          </div>

          {/* Search results (#48) */}
          {hits !== null && (
            <div className="wa-hits">
              {hits.length === 0 ? (
                <div className="wa-hits-empty">No auras found for “{query}”.</div>
              ) : (
                hits.map((h) => (
                  <div className="wa-hit" key={h.slug}>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div className="wa-nm">{h.name}</div>
                      <div className="wa-au">{h.type}{h.author ? ` · by ${h.author}` : ""}</div>
                    </div>
                    <button
                      className="btn btn-sm btn-accent"
                      onClick={() => track(h)}
                      disabled={tracking !== null}
                    >
                      {tracking === h.slug ? "…" : "Track"}
                    </button>
                  </div>
                ))
              )}
            </div>
          )}

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
              <p>Search wago.io above to track auras, or import the ones you already use in WoW.</p>
              <button className="btn" onClick={importFromWow} disabled={importing} style={{ marginTop: 12 }}>
                {importing ? "Importing…" : "Import from WoW"}
              </button>
            </div>
          ) : (
            <div className="wa-grid">
              {items.map((a) => (
                <div className={`wa-card${a.has_update ? " wa-card-upd" : ""}`} key={a.slug}>
                  <div className="wa-top">
                    <div className="wa-ic">
                      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                        <path d="M10 2 4 10h4l-1 6 6-8h-4l1-6z" fill="currentColor"/>
                      </svg>
                    </div>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div className="wa-nm">{a.name}</div>
                      <div className="wa-au">{a.type} · v{a.version}</div>
                    </div>
                    {a.has_update ? (
                      <button
                        className="btn btn-sm btn-accent wa-upd-btn"
                        onClick={() => updateAura(a.slug)}
                        disabled={updating !== null}
                      >
                        {updating === a.slug ? "…" : `v${a.latest_version}`}
                      </button>
                    ) : (
                      <span className="wa-sync">current</span>
                    )}
                  </div>
                  {a.note && <div className="gdesc">{a.note}</div>}
                  <div className="wa-foot">
                    {a.author && <span className="wa-meta">by {a.author}</span>}
                    {a.modified && <span className="wa-meta">{new Date(a.modified).toLocaleDateString()}</span>}
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
