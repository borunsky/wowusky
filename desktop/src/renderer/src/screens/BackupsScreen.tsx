import { useState, useEffect } from "react";
import { bridge } from "../api";

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

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fmtDate(mtime: number): string {
  const d = new Date(mtime * 1000);
  return d.toLocaleString();
}

function BackupCard({ icon, title, meta }: { icon: JSX.Element; title: string; meta: string[] }): JSX.Element {
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
        <button className="btn btn-sm">Restore</button>
      </div>
    </div>
  );
}

export function BackupsScreen(): JSX.Element {
  const [result, setResult] = useState<BackupsResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    setLoading(true);
    bridge
      .call<BackupsResult>("backups.list", {})
      .then((r) => { setResult(r); setError(null); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }
  useEffect(reload, []);

  const empty = result && result.full_count === 0 && result.addon_count === 0;

  return (
    <div className="page">
      <div className="page-head">
        <div className="page-title">
          Backups
          {result && <span className="badge-count">{result.full_count + result.addon_count}</span>}
        </div>
        <div className="page-sub">Snapshots of your addons and full installations</div>
      </div>

      <div className="page-body scroll">
        <div className="page-pad">
          {error ? (
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
              {result!.full.length > 0 && (
                <>
                  <div className="section-h">
                    <span className="t">Full installations</span>
                    <span className="c">{result!.full_count}</span>
                  </div>
                  <div className="backup-list">
                    {result!.full.map((b) => (
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
                      />
                    ))}
                  </div>
                </>
              )}

              {result!.addons.length > 0 && (
                <>
                  <div className="section-h" style={{ marginTop: 18 }}>
                    <span className="t">Per-addon snapshots</span>
                    <span className="c">{result!.addon_count}</span>
                  </div>
                  <div className="backup-list">
                    {result!.addons.map((b) => (
                      <BackupCard
                        key={b.path}
                        title={b.addon_name}
                        icon={
                          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                            <path d="M4 7l6-3 6 3v6l-6 3-6-3V7z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
                          </svg>
                        }
                        meta={[`v${b.version}`, fmtDate(b.mtime), fmtSize(b.size)]}
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
