import { useState, useEffect } from "react";
import { bridge } from "../api";
import { useActionProgress, progressLabel } from "../useActionProgress";

interface FullBackup {
  path: string;
  name: string;
  mtime: number;
  size: number;
}

interface AddonBackup extends FullBackup {
  addon_id: string;
  addon_name: string;
  version: string;
}

interface BackupsResult {
  full: FullBackup[];
  addons: AddonBackup[];
  full_count: number;
  addon_count: number;
}

interface DiffResult {
  added: string[];
  removed: string[];
  changed: { path: string; size_a: number; size_b: number }[];
}

interface StorageSummary {
  backups_bytes: number;
  backups_count: number;
  addons_bytes: number;
  by_addon: { addon_id: string; name: string; bytes: number; count: number }[];
}

// Dev-only placeholder data, shown when the profile has no backups yet so the
// layout can be eyeballed. Flip to false to disable.
const SHOW_DEMO = false;
const _now = Date.now() / 1000;
const DEMO_BACKUPS: BackupsResult = {
  full_count: 1,
  addon_count: 2,
  full: [
    { path: "demo-full", name: "wowusky-full-20260603-2230.zip", mtime: _now - 3600, size: 48_300_000 },
  ],
  addons: [
    { path: "demo-elvui", addon_id: "elvui", addon_name: "ElvUI", name: "elvui-13.78.zip", mtime: _now - 7200, size: 4_200_000, version: "13.78" },
    { path: "demo-details", addon_id: "details", addon_name: "Details! Damage Meter", name: "details-11.1.5.zip", mtime: _now - 86_400, size: 2_700_000, version: "11.1.5" },
  ],
};

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fmtDate(mtime: number): string {
  const d = new Date(mtime * 1000);
  return d.toLocaleString();
}

function BackupCard({
  icon,
  title,
  meta,
  busy,
  disabled,
  onRestore,
}: {
  icon: JSX.Element;
  title: string;
  meta: string[];
  busy?: boolean;
  disabled?: boolean;
  onRestore?: () => void;
}): JSX.Element {
  return (
    <div className="bcard">
      <div className="bicon">{icon}</div>
      <div className="bmain">
        <div className="bt">{title}</div>
        <div className="bm">
          {meta.map((m, i) => <span className="m" key={i}>{m}</span>)}
        </div>
      </div>
      <div className="br">
        <button className="btn btn-sm" disabled={disabled} onClick={onRestore}>
          {busy ? "…" : "Restore"}
        </button>
      </div>
    </div>
  );
}

export function BackupsScreen(): JSX.Element {
  const [result, setResult] = useState<BackupsResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // Diff state (#45): pick two backups, show the file-level diff.
  const [diffAddon, setDiffAddon] = useState<string>("");
  const [diffA, setDiffA] = useState<string>("");
  const [diffB, setDiffB] = useState<string>("");
  const [diff, setDiff] = useState<DiffResult | null>(null);
  const [diffErr, setDiffErr] = useState<string | null>(null);
  // Storage overview + cleanup (#52)
  const [storage, setStorage] = useState<StorageSummary | null>(null);
  const [keep, setKeep] = useState(5);
  const [cleaning, setCleaning] = useState(false);
  const progress = useActionProgress();
  const liveLabel = busy ? progressLabel(progress[busy]) : null;

  function runDiff(a: string, b: string) {
    setDiff(null);
    setDiffErr(null);
    if (!a || !b || a === b) return;
    bridge
      .call<DiffResult>("backups.diff", { a, b })
      .then(setDiff)
      .catch((e) => setDiffErr(String(e)));
  }

  function reload() {
    setLoading(true);
    bridge
      .call<BackupsResult>("backups.list", {})
      .then((r) => { setResult(r); setError(null); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
    bridge.call<StorageSummary>("storage.summary", {}).then(setStorage).catch(() => {});
  }
  useEffect(reload, []);

  function cleanup() {
    if (cleaning) return;
    if (!window.confirm(`Keep only the ${keep} newest backups per addon and full set? Older backups are deleted.`)) return;
    setCleaning(true);
    setNotice(null);
    bridge
      .call<{ ok: boolean; removed: number; freed_bytes: number }>("storage.cleanup", { keep })
      .then((r) => {
        setNotice(`Cleanup: removed ${r.removed} backup${r.removed === 1 ? "" : "s"}, freed ${fmtSize(r.freed_bytes)}`);
        reload();
      })
      .catch((e) => setNotice(String(e)))
      .finally(() => setCleaning(false));
  }

  function restore(path: string, label: string, addonId?: string) {
    if (busy) return;
    if (!window.confirm(`Restore ${label}? This overwrites the current files.`)) return;
    setBusy(path);
    setNotice(null);
    bridge
      .call<{ ok: boolean; error?: string }>("backups.restore", {
        path,
        ...(addonId ? { addon_id: addonId } : {}),
      })
      .then((r) => {
        setNotice(r.ok ? `${label}: restored` : `${label}: ${r.error ?? "restore failed"}`);
      })
      .catch((e) => setNotice(`${label}: ${String(e)}`))
      .finally(() => setBusy(null));
  }

  const realEmpty = !!result && result.full_count === 0 && result.addon_count === 0;
  // Show demo data when the profile has none yet, or when the bridge call
  // failed (e.g. a stale bridge after a renderer-only HMR reload).
  const isDemo = SHOW_DEMO && (realEmpty || (!!error && !result));
  const view = isDemo ? DEMO_BACKUPS : result;
  const empty = realEmpty && !isDemo;

  return (
    <div className="page">
      <div className="page-head">
        <div className="page-title">
          Backups
          {view && <span className="badge-count">{view.full_count + view.addon_count}</span>}
          {isDemo && <span className="cat">demo data</span>}
        </div>
        <div className="page-sub">Snapshots of your addons and full installations</div>
      </div>

      {(liveLabel || notice) && <div className="inst-toolbar"><div className="inst-notice">{liveLabel ?? notice}</div></div>}

      <div className="page-body scroll">
        <div className="page-pad">
          {error && !isDemo ? (
            <div className="empty">
              <div className="eicon">!</div>
              <h3>Could not load backups</h3>
              <p>{error}</p>
            </div>
          ) : loading && !result ? (
            <div className="empty">
              <div className="spin" />
              <p>Loading backups…</p>
            </div>
          ) : empty ? (
            <div className="empty">
              <div className="eicon">
                <svg width="26" height="26" viewBox="0 0 26 26" fill="none">
                  <rect x="4" y="7" width="18" height="14" rx="3" stroke="currentColor" strokeWidth="1.6"/>
                  <path d="M9 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M13 11v5M10 13.5h6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
                </svg>
              </div>
              <h3>No backups yet</h3>
              <p>wowusky creates backups automatically before updating or removing addons.</p>
            </div>
          ) : (
            <>
              {!isDemo && storage && (
                <div className="storage-card">
                  <div className="storage-stats">
                    <div className="storage-stat">
                      <div className="ss-val">{fmtSize(storage.backups_bytes)}</div>
                      <div className="ss-lbl">{storage.backups_count} backup{storage.backups_count === 1 ? "" : "s"}</div>
                    </div>
                    <div className="storage-stat">
                      <div className="ss-val">{fmtSize(storage.addons_bytes)}</div>
                      <div className="ss-lbl">addons on disk</div>
                    </div>
                    {storage.by_addon[0] && (
                      <div className="storage-stat">
                        <div className="ss-val">{fmtSize(storage.by_addon[0].bytes)}</div>
                        <div className="ss-lbl">top: {storage.by_addon[0].name}</div>
                      </div>
                    )}
                  </div>
                  <div className="storage-clean">
                    <label className="ss-keep">
                      Keep
                      <input
                        type="number"
                        min={1}
                        value={keep}
                        onChange={(e) => setKeep(Math.max(1, Number(e.target.value) || 1))}
                      />
                      newest
                    </label>
                    <button className="btn btn-sm" onClick={cleanup} disabled={cleaning || storage.backups_count === 0}>
                      {cleaning ? "Cleaning…" : "Clean up old backups"}
                    </button>
                  </div>
                </div>
              )}

              {view!.full.length > 0 && (
                <>
                  <div className="section-h">
                    <span className="t">Full installations</span>
                    <span className="c">{view!.full_count}</span>
                  </div>
                  <div className="backup-list">
                    {view!.full.map((b) => (
                      <BackupCard
                        key={b.path}
                        title={b.name}
                        icon={
                          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                            <rect x="3" y="3" width="14" height="14" rx="3" stroke="currentColor" strokeWidth="1.5"/>
                            <path d="M7 7h6M7 10h6M7 13h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                          </svg>
                        }
                        meta={[fmtDate(b.mtime), fmtSize(b.size)]}
                        busy={busy === b.path}
                        disabled={isDemo || busy !== null}
                        onRestore={isDemo ? undefined : () => restore(b.path, b.name)}
                      />
                    ))}
                  </div>
                </>
              )}

              {(() => {
                // Addons that have ≥2 snapshots can be diffed.
                const byAddon = new Map<string, AddonBackup[]>();
                for (const b of view!.addons) {
                  const arr = byAddon.get(b.addon_id) ?? [];
                  arr.push(b);
                  byAddon.set(b.addon_id, arr);
                }
                const diffable = [...byAddon.entries()].filter(([, arr]) => arr.length >= 2);
                if (diffable.length === 0) return null;
                const selectable = diffAddon ? (byAddon.get(diffAddon) ?? []) : [];
                return (
                  <>
                    <div className="section-h" style={{ marginTop: 18 }}>
                      <span className="t">Compare backups</span>
                    </div>
                    <div className="diff-box">
                      <div className="diff-controls">
                        <select
                          value={diffAddon}
                          onChange={(e) => { setDiffAddon(e.target.value); setDiffA(""); setDiffB(""); setDiff(null); setDiffErr(null); }}
                        >
                          <option value="">Select an addon…</option>
                          {diffable.map(([id, arr]) => (
                            <option key={id} value={id}>{arr[0].addon_name} ({arr.length})</option>
                          ))}
                        </select>
                        {diffAddon && (
                          <>
                            <select value={diffA} onChange={(e) => { setDiffA(e.target.value); runDiff(e.target.value, diffB); }}>
                              <option value="">Version A…</option>
                              {selectable.map((b) => <option key={b.path} value={b.path}>{`v${b.version} · ${fmtDate(b.mtime)}`}</option>)}
                            </select>
                            <span className="diff-arrow">→</span>
                            <select value={diffB} onChange={(e) => { setDiffB(e.target.value); runDiff(diffA, e.target.value); }}>
                              <option value="">Version B…</option>
                              {selectable.map((b) => <option key={b.path} value={b.path}>{`v${b.version} · ${fmtDate(b.mtime)}`}</option>)}
                            </select>
                          </>
                        )}
                      </div>
                      {diffErr && <div className="diff-err">{diffErr}</div>}
                      {diff && (diffA && diffB && diffA !== diffB) && (
                        <div className="diff-result">
                          {diff.added.length === 0 && diff.removed.length === 0 && diff.changed.length === 0 ? (
                            <div className="diff-empty">No differences.</div>
                          ) : (
                            <>
                              {diff.added.map((p) => <div key={`a${p}`} className="diff-line dl-add"><span>+</span>{p}</div>)}
                              {diff.removed.map((p) => <div key={`r${p}`} className="diff-line dl-rem"><span>−</span>{p}</div>)}
                              {diff.changed.map((c) => (
                                <div key={`c${c.path}`} className="diff-line dl-chg">
                                  <span>~</span>{c.path}
                                  <em>{fmtSize(c.size_a)} → {fmtSize(c.size_b)}</em>
                                </div>
                              ))}
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  </>
                );
              })()}

              {view!.addons.length > 0 && (
                <>
                  <div className="section-h" style={{ marginTop: 18 }}>
                    <span className="t">Per-addon snapshots</span>
                    <span className="c">{view!.addon_count}</span>
                  </div>
                  <div className="backup-list">
                    {view!.addons.map((b) => (
                      <BackupCard
                        key={b.path}
                        title={b.addon_name}
                        icon={
                          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                            <path d="M4 7l6-3 6 3v6l-6 3-6-3V7z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
                          </svg>
                        }
                        meta={[`v${b.version}`, fmtDate(b.mtime), fmtSize(b.size)]}
                        busy={busy === b.path}
                        disabled={isDemo || busy !== null}
                        onRestore={isDemo ? undefined : () => restore(b.path, b.addon_name, b.addon_id)}
                      />
                    ))}
                  </div>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
