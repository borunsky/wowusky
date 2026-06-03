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

export function HealthScreen(): JSX.Element {
  const [result, setResult] = useState<HealthResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [onlyErrors, setOnlyErrors] = useState(false);

  function run() {
    setLoading(true);
    bridge
      .call<HealthResult>("health.check", {})
      .then((r) => { setResult(r); setError(null); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }
  useEffect(run, []);

  const rows = (result?.results ?? []).filter((r) => !onlyErrors || r.status === "error");

  return (
    <div className="page">
      <div className="page-head">
        <div className="page-title">Health</div>
        <div className="page-sub">Verify every catalog entry resolves to a valid provider reference</div>
      </div>

      <div className="inst-toolbar">
        <div className="left" style={{ alignItems: "center", gap: 12, display: "flex" }}>
          <button className="btn btn-sm" onClick={run} disabled={loading}>
            {loading ? <span className="spin" /> : "Re-run check"}
          </button>
          {result && (
            <button
              className={`chip${onlyErrors ? " on" : ""}`}
              onClick={() => setOnlyErrors((v) => !v)}
            >
              Errors only
            </button>
          )}
        </div>
        {result && (
          <div className="right">
            <span className="installed-tag">{result.ok} ok</span>
            {result.failed > 0
              ? <span style={{ color: "var(--red)", display: "inline-flex", alignItems: "center", gap: 6 }}>{result.failed} failed</span>
              : <span className="checking">no issues</span>}
          </div>
        )}
      </div>

      {result && (
        <div style={{ padding: "8px 24px 0" }}>
          <div className="usage" style={{ height: 8 }}>
            <i style={{ width: `${(result.ok / Math.max(result.total, 1)) * 100}%` }} />
          </div>
        </div>
      )}

      <div className="page-body scroll">
        {error ? (
          <div className="empty">
            <div className="eicon">!</div>
            <h3>Health check failed</h3>
            <p>{error}</p>
          </div>
        ) : loading && !result ? (
          <div className="empty">
            <div className="spin" />
            <p>Running health check…</p>
          </div>
        ) : rows.length === 0 ? (
          <div className="empty">
            <div className="eicon">
              <svg width="26" height="26" viewBox="0 0 26 26" fill="none">
                <path d="M6 13l4 4 10-10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <h3>{onlyErrors ? "No errors" : "All healthy"}</h3>
            <p>Every catalog entry resolved successfully.</p>
          </div>
        ) : (
          <div style={{ padding: "0 10px 16px" }}>
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
                <span
                  className="idesc"
                  style={{ margin: 0, color: r.status === "error" ? "var(--red)" : "var(--text-faint)" }}
                >
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
