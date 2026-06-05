import { useState, useEffect } from "react";
import { bridge } from "../api";

interface HealthRow {
  id: string;
  name: string;
  provider: string;
  status: "ok" | "error";
  detail: string;
}

interface HealthResult {
  total: number;
  ok: number;
  failed: number;
  results: HealthRow[];
}

interface Orphan { folder: string; match_id: string | null; match_name: string | null; }
interface InstallHealth {
  addons_path: string;
  missing: { id: string; name: string; folders: string[] }[];
  duplicates: { folder: string; ids: string[] }[];
  orphans: Orphan[];
  problem_count: number;
}

export function HealthScreen(): JSX.Element {
  // Catalog health (provider resolve).
  const [result, setResult] = useState<HealthResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [onlyErrors, setOnlyErrors] = useState(false);
  // Installation health (#59/#60).
  const [inst, setInst] = useState<InstallHealth | null>(null);
  const [instLoading, setInstLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  function run() {
    setLoading(true);
    bridge
      .call<HealthResult>("health.check", {})
      .then((r) => { setResult(r); setError(null); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }
  function loadInstall() {
    setInstLoading(true);
    bridge
      .call<InstallHealth>("health.installed", {})
      .then(setInst)
      .catch(() => {})
      .finally(() => setInstLoading(false));
  }
  useEffect(() => { run(); loadInstall(); }, []);

  function resync() {
    setBusy("resync");
    setNotice(null);
    bridge.call<{ ok: boolean } & InstallHealth>("health.fixResync", {})
      .then((r) => { setInst(r); setNotice("Re-synced with the filesystem."); })
      .catch((e) => setNotice(String(e)))
      .finally(() => setBusy(null));
  }
  function removeEntry(id: string) {
    setBusy(id);
    bridge.call<{ ok: boolean } & InstallHealth>("health.removeEntry", { id })
      .then((r) => setInst(r))
      .catch((e) => setNotice(String(e)))
      .finally(() => setBusy(null));
  }
  function adopt(folder: string) {
    setBusy("orphan:" + folder);
    bridge.call<{ ok: boolean; error?: string }>("orphans.adopt", { folder })
      .then((r) => { if (!r.ok) setNotice(r.error ?? "adopt failed"); loadInstall(); })
      .catch((e) => setNotice(String(e)))
      .finally(() => setBusy(null));
  }
  function removeOrphan(folder: string) {
    if (!window.confirm(`Delete folder "${folder}" from disk? A backup is taken first.`)) return;
    setBusy("orphan:" + folder);
    bridge.call<{ ok: boolean; error?: string; orphans?: Orphan[] }>("orphans.remove", { folder })
      .then((r) => { if (!r.ok) setNotice(r.error ?? "remove failed"); loadInstall(); })
      .catch((e) => setNotice(String(e)))
      .finally(() => setBusy(null));
  }

  const rows = (result?.results ?? []).filter((r) => !onlyErrors || r.status === "error");
  const hasInstallProblems = (inst?.problem_count ?? 0) > 0;

  return (
    <div className="page">
      <div className="page-head">
        <div className="page-title">Health</div>
        <div className="page-sub">Diagnose installation problems and verify the catalog</div>
      </div>

      <div className="page-body scroll">
        {/* Installation health (#59 / #60) */}
        <div style={{ padding: "12px 24px 0" }}>
          <div className="health-section-head">
            <h3>Installation</h3>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              {notice && <span className="checking">{notice}</span>}
              <button className="btn btn-sm" disabled={busy !== null || instLoading} onClick={resync}>
                {busy === "resync" ? "Re-syncing…" : "Re-sync with disk"}
              </button>
              <button className="btn btn-sm" disabled={instLoading} onClick={loadInstall}>
                {instLoading ? <span className="spin" /> : "Refresh"}
              </button>
            </div>
          </div>

          {!inst ? (
            <div className="health-empty">Scanning installation…</div>
          ) : !hasInstallProblems ? (
            <div className="health-ok">✓ No installation problems detected.</div>
          ) : (
            <div className="health-problems">
              {inst.missing.length > 0 && (
                <div className="health-group">
                  <div className="health-group-title">Missing folders ({inst.missing.length})</div>
                  <div className="health-group-sub">Tracked addons whose folders are gone from disk.</div>
                  {inst.missing.map((m) => (
                    <div className="health-row" key={m.id}>
                      <span className="hr-name">{m.name}</span>
                      <span className="hr-detail">{m.folders.join(", ")}</span>
                      <button className="btn btn-sm btn-danger" disabled={busy !== null} onClick={() => removeEntry(m.id)}>
                        {busy === m.id ? "…" : "Remove entry"}
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {inst.duplicates.length > 0 && (
                <div className="health-group">
                  <div className="health-group-title">Duplicate folder claims ({inst.duplicates.length})</div>
                  <div className="health-group-sub">A folder claimed by more than one addon — re-sync to reconcile.</div>
                  {inst.duplicates.map((d) => (
                    <div className="health-row" key={d.folder}>
                      <span className="hr-name">{d.folder}</span>
                      <span className="hr-detail">claimed by: {d.ids.join(", ")}</span>
                    </div>
                  ))}
                </div>
              )}
              {inst.orphans.length > 0 && (
                <div className="health-group">
                  <div className="health-group-title">Orphan folders ({inst.orphans.length})</div>
                  <div className="health-group-sub">On disk but not tracked. Adopt to manage, or delete.</div>
                  {inst.orphans.map((o) => (
                    <div className="health-row" key={o.folder}>
                      <span className="hr-name">{o.folder}</span>
                      <span className="hr-detail">
                        {o.match_name ? `catalog match: ${o.match_name}` : "no catalog match"}
                      </span>
                      <div style={{ display: "flex", gap: 6 }}>
                        <button className="btn btn-sm btn-primary" disabled={busy !== null} onClick={() => adopt(o.folder)}>
                          {busy === "orphan:" + o.folder ? "…" : "Adopt"}
                        </button>
                        <button className="btn btn-sm btn-danger" disabled={busy !== null} onClick={() => removeOrphan(o.folder)}>
                          Delete
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Catalog health */}
        <div style={{ padding: "20px 24px 0" }}>
          <div className="health-section-head">
            <h3>Catalog</h3>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              {result && (
                <>
                  <span className="installed-tag">{result.ok} ok</span>
                  {result.failed > 0
                    ? <span style={{ color: "var(--red)" }}>{result.failed} failed</span>
                    : <span className="checking">no issues</span>}
                  <button className={`chip${onlyErrors ? " on" : ""}`} onClick={() => setOnlyErrors((v) => !v)}>
                    Errors only
                  </button>
                </>
              )}
              <button className="btn btn-sm" onClick={run} disabled={loading}>
                {loading ? <span className="spin" /> : "Re-run"}
              </button>
            </div>
          </div>
        </div>

        {error ? (
          <div className="empty">
            <div className="eicon">!</div>
            <h3>Health check failed</h3>
            <p>{error}</p>
          </div>
        ) : loading && !result ? (
          <div className="empty">
            <div className="spin" />
            <p>Running catalog check…</p>
          </div>
        ) : rows.length === 0 ? (
          <div className="health-ok" style={{ margin: "8px 24px" }}>
            {onlyErrors ? "No catalog errors." : "Every catalog entry resolved successfully."}
          </div>
        ) : (
          <div style={{ padding: "8px 10px 16px" }}>
            <div className="ihead" style={{ gridTemplateColumns: "28px minmax(0,1fr) 160px minmax(0,1.4fr)" }}>
              <span />
              <span>Addon</span>
              <span>Provider</span>
              <span>Detail</span>
            </div>
            {rows.map((r) => (
              <div
                key={r.id}
                className="irow"
                style={{ gridTemplateColumns: "28px minmax(0,1fr) 160px minmax(0,1.4fr)", cursor: "default" }}
              >
                <span
                  style={{
                    width: 10, height: 10, borderRadius: "50%",
                    background: r.status === "ok" ? "var(--green)" : "var(--red)",
                  }}
                />
                <div className="iname" style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {r.name}
                </div>
                <span className="ver-mono">{r.provider || "—"}</span>
                <span className="idesc" style={{ margin: 0, color: r.status === "error" ? "var(--red)" : "var(--text-faint)" }}>
                  {r.detail || "—"}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
