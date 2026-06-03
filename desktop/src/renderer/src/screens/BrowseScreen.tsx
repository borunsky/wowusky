import { useState, useMemo } from "react";
import { MOCK_ADDONS, CATEGORIES, sourceLabel, type Addon } from "./browseData";

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

  function setViewPersist(v: View) {
    setView(v);
    localStorage.setItem("wowusky:browseView", v);
  }

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    return MOCK_ADDONS.filter((a) => {
      if (category !== "All" && a.category !== category) return false;
      if (q && !a.name.toLowerCase().includes(q) && !a.description.toLowerCase().includes(q)) {
        return false;
      }
      return true;
    });
  }, [query, category]);

  return (
    <div className="page">
      <div className="page-head">
        <div className="page-title">
          Browse
          <span className="badge-count">{results.length}</span>
        </div>
        <div className="page-sub">Discover and install addons from all sources</div>
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
            {CATEGORIES.map((c) => (
              <button
                key={c}
                className={`chip${category === c ? " on" : ""}`}
                onClick={() => setCategory(c)}
              >
                {c}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="page-body scroll">
        <div className="page-pad">
          {results.length === 0 ? (
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
              {results.map((a) => (
                <div
                  key={a.id}
                  className="acard"
                  style={{ "--rar": `var(--badge-${a.rarity})` } as React.CSSProperties}
                >
                  <div className="thumb">
                    <MonoBadge glyph={a.glyph} rarity={a.rarity} />
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
                      <span className="m">↓ {a.downloads}</span>
                      <span className="m">{a.updated}</span>
                    </div>
                  </div>
                  <div className="right">
                    <span className="ver-mono">{a.version}</span>
                    <InstallButton installed={a.installed} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="agrid">
              {results.map((a) => (
                <div key={a.id} className="gcard">
                  <div className={`gcover cov-${a.rarity}`}>
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
                      <div className="gstats">
                        <span className="s">↓ {a.downloads}</span>
                        <span className="s">{a.updated}</span>
                      </div>
                      <InstallButton installed={a.installed} />
                    </div>
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
