import { useState, useEffect } from "react";
import { bridge } from "../api";
import { sourceLabel, rarityFor } from "./browseData";
import type { InstalledAddon, InstalledResult } from "./installedData";
import { useActionProgress, progressLabel } from "../useActionProgress";

interface Props {
  /** Bumped by the AppBar rescan button to force a reload. */
  refreshKey: number;
  /** Called after a successful update/remove so the sidebar count refreshes. */
  onChanged?: () => void;
}

interface ActionResult extends InstalledResult {
  ok: boolean;
  error?: string;
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

export function InstalledScreen({ refreshKey, onChanged }: Props): JSX.Element {
  const [result, setResult] = useState<InstalledResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  // id of the addon a mutation is currently running for ("" = none).
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // Map of addon id -> latest version, for addons that have an update available.
  const [updates, setUpdates] = useState<Record<string, string>>({});
  const [checkingUpdates, setCheckingUpdates] = useState(false);
  // Multi-select for bulk update / remove.
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const progress = useActionProgress();
  const liveLabel = busy ? progressLabel(progress[busy]) : null;

  function checkUpdates() {
    setCheckingUpdates(true);
    bridge
      .call<{ updates: Record<string, string> }>("installed.updates", {})
      .then((r) => setUpdates(r.updates ?? {}))
      .catch(() => {})
      .finally(() => setCheckingUpdates(false));
  }

  useEffect(() => {
    setLoading(true);
    setUpdates({});
    setSelected(new Set());
    bridge
      .call<InstalledResult>("installed.list", {})
      .then((r) => { setResult(r); setError(null); checkUpdates(); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [refreshKey]);

  function toggleSelect(id: string) {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function bulkUpdate() {
    // Only the selected addons that actually have an update pending.
    const ids = [...selected].filter((id) => updates[id]);
    if (busy || ids.length === 0) return;
    setBusy("__bulk__");
    setNotice(null);
    bridge
      .call<ActionResult>("installed.updateAll", { ids })
      .then((r) => {
        setResult({ profile: r.profile, count: r.count, addons_path: r.addons_path, items: r.items });
        setUpdates((u) => { const n = { ...u }; ids.forEach((id) => delete n[id]); return n; });
        setSelected(new Set());
        setNotice(`Updated ${ids.length} addon${ids.length === 1 ? "" : "s"}`);
        onChanged?.();
      })
      .catch((e) => setNotice(String(e)))
      .finally(() => { setBusy(null); checkUpdates(); });
  }

  function bulkRemove() {
    const ids = [...selected];
    if (busy || ids.length === 0) return;
    if (!window.confirm(`Remove ${ids.length} addon${ids.length === 1 ? "" : "s"}? A backup is taken first.`)) {
      return;
    }
    setBusy("__bulk__");
    setNotice(null);
    bridge
      .call<ActionResult>("installed.removeMany", { ids })
      .then((r) => {
        setResult({ profile: r.profile, count: r.count, addons_path: r.addons_path, items: r.items });
        setUpdates((u) => { const n = { ...u }; ids.forEach((id) => delete n[id]); return n; });
        setSelected(new Set());
        setNotice(`Removed ${ids.length} addon${ids.length === 1 ? "" : "s"}`);
        onChanged?.();
      })
      .catch((e) => setNotice(String(e)))
      .finally(() => setBusy(null));
  }

  function updateAll() {
    const ids = Object.keys(updates);
    if (busy || ids.length === 0) return;
    setBusy("__all__");
    setNotice(null);
    bridge
      .call<ActionResult>("installed.updateAll", { ids })
      .then((r) => {
        setResult({ profile: r.profile, count: r.count, addons_path: r.addons_path, items: r.items });
        setUpdates({});
        setNotice(`Updated ${ids.length} addon${ids.length === 1 ? "" : "s"}`);
        onChanged?.();
      })
      .catch((e) => setNotice(String(e)))
      .finally(() => { setBusy(null); checkUpdates(); });
  }

  function runAction(method: "addon.update" | "addon.remove", a: InstalledAddon) {
    if (busy) return;
    if (method === "addon.remove" && !window.confirm(`Remove ${a.name}? A backup is taken first.`)) {
      return;
    }
    setBusy(a.id);
    setNotice(null);
    bridge
      .call<ActionResult>(method, { id: a.id })
      .then((r) => {
        if (!r.ok) {
          setNotice(`${a.name}: ${r.error ?? "action failed"}`);
          return;
        }
        // The action returns the refreshed installed list — apply it directly.
        setResult({ profile: r.profile, count: r.count, addons_path: r.addons_path, items: r.items });
        // The addon is now current (or gone) — clear its pending-update marker.
        setUpdates((u) => {
          const next = { ...u };
          delete next[a.id];
          return next;
        });
        setNotice(`${a.name}: ${method === "addon.remove" ? "removed" : "updated"}`);
        onChanged?.();
      })
      .catch((e) => setNotice(`${a.name}: ${String(e)}`))
      .finally(() => setBusy(null));
  }

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
          {selected.size === 0 && Object.keys(updates).length > 0 && (
            <button
              className="btn btn-sm btn-primary"
              style={{ marginLeft: 10 }}
              disabled={busy !== null}
              onClick={updateAll}
            >
              {busy === "__all__" ? "Updating…" : `Update all (${Object.keys(updates).length})`}
            </button>
          )}
          {selected.size > 0 && (
            <div className="bulk-bar">
              <span className="bulk-count">{selected.size} selected</span>
              {[...selected].some((id) => updates[id]) && (
                <button className="btn btn-sm btn-primary" disabled={busy !== null} onClick={bulkUpdate}>
                  {busy === "__bulk__" ? "Working…" : `Update (${[...selected].filter((id) => updates[id]).length})`}
                </button>
              )}
              <button className="btn btn-sm btn-danger" disabled={busy !== null} onClick={bulkRemove}>
                {busy === "__bulk__" ? "Working…" : "Remove"}
              </button>
              <button className="btn btn-sm" disabled={busy !== null} onClick={() => setSelected(new Set())}>
                Clear
              </button>
            </div>
          )}
        </div>
        {(liveLabel || notice || checkingUpdates) && (
          <div className="inst-notice">{liveLabel ?? notice ?? "Checking for updates…"}</div>
        )}
      </div>

      <div className="page-body scroll">
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
          <div style={{ padding: "0 10px 16px" }}>
            <div className="ihead">
              <input
                type="checkbox"
                aria-label="Select all"
                checked={items.length > 0 && items.every((a) => selected.has(a.id))}
                ref={(el) => {
                  if (el) el.indeterminate = items.some((a) => selected.has(a.id)) && !items.every((a) => selected.has(a.id));
                }}
                onChange={(e) =>
                  setSelected(e.target.checked ? new Set(items.map((a) => a.id)) : new Set())
                }
              />
              <span />
              <span>Addon</span>
              <span>Source</span>
              <span>Version</span>
              <span style={{ justifySelf: "end" }}>Actions</span>
            </div>
            {items.map((a) => (
              <div key={a.id} className={`irow${selected.has(a.id) ? " sel" : ""}`}>
                <input
                  type="checkbox"
                  aria-label={`Select ${a.name}`}
                  checked={selected.has(a.id)}
                  onChange={() => toggleSelect(a.id)}
                />
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
                  <span className="ver-mono">
                    {a.version}
                    {updates[a.id] && (
                      <span className="installed-tag" style={{ marginLeft: 8 }} title={`Latest: ${updates[a.id]}`}>
                        → {updates[a.id]}
                      </span>
                    )}
                  </span>
                  <div className="iright">
                    {(updates[a.id] || busy === a.id) && (
                      <button
                        className="btn btn-sm btn-primary"
                        disabled={busy !== null}
                        onClick={() => runAction("addon.update", a)}
                      >
                        {busy === a.id ? (progressLabel(progress[a.id]) ?? "…") : "Update"}
                      </button>
                    )}
                    <button
                      className="btn btn-sm btn-danger"
                      disabled={busy !== null}
                      onClick={() => runAction("addon.remove", a)}
                    >
                      Remove
                    </button>
                  </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
