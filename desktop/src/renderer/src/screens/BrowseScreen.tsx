import { useState, useEffect, useRef } from "react";import { bridge } from "../api";
import { sourceLabel, rarityFor, type Addon, type SearchResult } from "./browseData";
import { DetailPanel } from "./DetailPanel";

type View = "list" | "grid";

function MonoBadge({ glyph, rarity, size = 46 }: { glyph: string; rarity: string; size?: number }): JSX.Element {
  return (
    <div
      className={`mono-badge mb-${rarity}`}
      style={{ width: size, height: size, fontSize: size * 0.42 }}
    >
      {glyph}
    </div>
  );
}

function SourcePill({ source }: { source: Addon["source"] }): JSX.Element {
  return (
    <span className={`pill src-${source}`}>
      <span className="dot" />
      {sourceLabel(source)}
    </span>
  );
}

function InstallButton({ installed }: { installed?: boolean }): JSX.Element {
  if (installed) {
    return (
      <span className="installed-tag">
        <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
          <path d="M2.5 7l3 3 5-6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        Installed
      </span>
    );
  }
  return <button className="btn btn-primary btn-sm">Install</button>;
}

export function BrowseScreen(): JSX.Element {
  const [view, setView] = useState<View>(() => {
    return (localStorage.getItem("wowusky:browseView") as View | null) ?? "list";
  });
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Addon | null>(null);
  const [catMenuOpen, setCatMenuOpen] = useState(false);
  const catMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (catMenuRef.current && !catMenuRef.current.contains(e.target as Node)) {
        setCatMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  function setViewPersist(v: View) {
    setView(v);
    localStorage.setItem("wowusky:browseView", v);
  }

  // Debounced catalog search via the Python bridge.
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => {
    setLoading(true);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      bridge
        .call<SearchResult>("catalog.search", { query, category })
        .then((r) => { setResult(r); setError(null); })
        .catch((e) => setError(String(e)))
        .finally(() => setLoading(false));
    }, 160);
    return () => clearTimeout(debounceRef.current);
  }, [query, category]);

  const items = result?.items ?? [];
  const categories = result?.categories ?? ["All"];

  return (
    <div className="page">
      <div className="page-head">
        <div className="page-title">
          Browse
          <span className="badge-count">{result ? result.count : "…"}</span>
        </div>
        <div className="page-sub">
          Discover and install addons from all sources
          {result && ` · ${result.total} in catalog`}
        </div>
      </div>

      <div className="toolbar">
        <div className="searchrow">
          <label className="search">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.4"/>
              <path d="M10.5 10.5 13 13" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
            </svg>
            <input
              placeholder="Search addons…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <span className="kbd">⌘K</span>
          </label>
          <div className="viewtoggle">
            <button className={view === "list" ? "on" : ""} title="List view" onClick={() => setViewPersist("list")}>
              <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
                <path d="M3 4h9M3 7.5h9M3 11h9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </button>
            <button className={view === "grid" ? "on" : ""} title="Grid view" onClick={() => setViewPersist("grid")}>
              <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
                <rect x="3" y="3" width="3.5" height="3.5" rx="1" stroke="currentColor" strokeWidth="1.4"/>
                <rect x="8.5" y="3" width="3.5" height="3.5" rx="1" stroke="currentColor" strokeWidth="1.4"/>
                <rect x="3" y="8.5" width="3.5" height="3.5" rx="1" stroke="currentColor" strokeWidth="1.4"/>
                <rect x="8.5" y="8.5" width="3.5" height="3.5" rx="1" stroke="currentColor" strokeWidth="1.4"/>
              </svg>
            </button>
          </div>
        </div>
        <div className="filters">
          <div className="filtergroup">
            <span className="glabel">Category</span>
            <div className="dropdown" ref={catMenuRef}>
              <button
                className={`sortsel${catMenuOpen ? " on" : ""}`}
                onClick={() => setCatMenuOpen((o) => !o)}
              >
                {category}
                <svg className="chev" width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M3 5l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
              {catMenuOpen && (
                <div className="menu" style={{ maxHeight: 320, overflowY: "auto" }}>
                  {categories.map((c) => (
                    <button
                      key={c}
                      className={`menu-item${category === c ? " on" : ""}`}
                      onClick={() => { setCategory(c); setCatMenuOpen(false); }}
                    >
                      {c}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="page-body scroll">
        <div className="page-pad">
          {error ? (
            <div className="empty">
              <div className="eicon">!</div>
              <h3>Catalog unavailable</h3>
              <p>{error}</p>
            </div>
          ) : loading && !result ? (
            <div className="empty">
              <div className="spin" />
              <p>Loading catalog…</p>
            </div>
          ) : items.length === 0 ? (
            <div className="empty">
              <div className="eicon">
                <svg width="26" height="26" viewBox="0 0 26 26" fill="none">
                  <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="1.6"/>
                  <path d="M16 16l5 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
                </svg>
              </div>
              <h3>No addons found</h3>
              <p>Try a different search term or category filter.</p>
            </div>
          ) : view === "list" ? (
            <div className="alist">
              {items.map((a) => (
                <div
                  key={a.id}
                  className={`acard${selected?.id === a.id ? " sel" : ""}`}
                  style={{ "--rar": `var(--badge-${rarityFor(a)})` } as React.CSSProperties}
                  onClick={() => setSelected(a)}
                >
                  <div className="thumb">
                    <MonoBadge glyph={a.glyph} rarity={rarityFor(a)} />
                  </div>
                  <div className="main">
                    <div className="titlerow">
                      <span className="nm">{a.name}</span>
                      <span className="cat">{a.category}</span>
                    </div>
                    <div className="ds">{a.description}</div>
                    <div className="meta">
                      <SourcePill source={a.source} />
                      <span className="m">{a.author}</span>
                    </div>
                  </div>
                  <div className="right" onClick={(e) => e.stopPropagation()}>
                    <InstallButton installed={a.installed} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="agrid">
              {items.map((a) => (
                <div
                  key={a.id}
                  className={`gcard${selected?.id === a.id ? " sel" : ""}`}
                  onClick={() => setSelected(a)}
                >
                  <div className={`gcover cov-${rarityFor(a)}`}>
                    <span className="glyph">{a.glyph}</span>
                    <div className="src">
                      <SourcePill source={a.source} />
                    </div>
                  </div>
                  <div className="gbody">
                    <div>
                      <div className="gname">{a.name}</div>
                      <div className="gauthor">by {a.author}</div>
                    </div>
                    <div className="gdesc">{a.description}</div>
                    <div className="gfoot">
                      <span className="gstats">
                        <span className="s">{a.category}</span>
                      </span>
                      <span onClick={(e) => e.stopPropagation()}>
                        <InstallButton installed={a.installed} />
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <DetailPanel addon={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
