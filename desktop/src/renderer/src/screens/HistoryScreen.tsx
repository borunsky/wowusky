import { useState, useEffect } from "react";
import { bridge } from "../api";

interface HistoryItem {
  ts: number;
  action: string;
  id: string;
  name: string;
  from: string;
  to: string;
}

interface Props {
  refreshKey?: number;
}

const ACTION_LABEL: Record<string, string> = {
  install: "Installed",
  update: "Updated",
  remove: "Removed",
};

export function HistoryScreen({ refreshKey = 0 }: Props): JSX.Element {
  const [items, setItems] = useState<HistoryItem[] | null>(null);
  const [query, setQuery] = useState("");
  const [actionFilter, setActionFilter] = useState<string>("all");

  function reload() {
    bridge
      .call<{ items: HistoryItem[] }>("history.list", {})
      .then((r) => setItems(r.items ?? []))
      .catch(() => setItems([]));
  }
  useEffect(reload, [refreshKey]);

  function clearHistory() {
    if (!window.confirm("Clear the entire change history for this profile?")) return;
    bridge.call("history.clear", {}).then(() => reload()).catch(() => {});
  }

  const q = query.trim().toLowerCase();
  const rows = (items ?? []).filter((it) => {
    if (actionFilter !== "all" && it.action !== actionFilter) return false;
    if (q && !(it.name.toLowerCase().includes(q) || it.id.toLowerCase().includes(q))) return false;
    return true;
  });

  return (
    <div className="page">
      <div className="page-head">
        <div className="page-title">
          History
          {items && <span className="badge-count">{items.length}</span>}
        </div>
        <div className="page-sub">Persistent log of installs, updates and removals for this profile</div>
      </div>

      <div className="inst-toolbar">
        <div className="left">
          <label className="search" style={{ width: 260 }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.4"/>
              <path d="M10.5 10.5 13 13" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
            </svg>
            <input placeholder="Filter history…" value={query} onChange={(e) => setQuery(e.target.value)} />
          </label>
          <select className="field inst-filter" value={actionFilter} onChange={(e) => setActionFilter(e.target.value)}>
            <option value="all">All actions</option>
            <option value="install">Installed</option>
            <option value="update">Updated</option>
            <option value="remove">Removed</option>
          </select>
        </div>
        {items && items.length > 0 && (
          <div className="right">
            <button className="btn btn-sm btn-danger" onClick={clearHistory}>Clear history</button>
          </div>
        )}
      </div>

      <div className="page-body scroll">
        {items === null ? (
          <div className="empty"><div className="spin" /><p>Loading history…</p></div>
        ) : rows.length === 0 ? (
          <div className="empty">
            <div className="eicon">
              <svg width="26" height="26" viewBox="0 0 26 26" fill="none">
                <circle cx="13" cy="13" r="10" stroke="currentColor" strokeWidth="1.6"/>
                <path d="M13 7v6l4 2.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <h3>{items.length === 0 ? "No history yet" : "No matches"}</h3>
            <p>{items.length === 0 ? "Installs, updates and removals will appear here." : "Try a different filter."}</p>
          </div>
        ) : (
          <div style={{ padding: "0 10px 16px" }}>
            <div className="ihead" style={{ gridTemplateColumns: "110px 100px minmax(0,1fr) minmax(0,1fr)" }}>
              <span>When</span>
              <span>Action</span>
              <span>Addon</span>
              <span>Version</span>
            </div>
            {rows.map((it, i) => (
              <div
                key={`${it.ts}-${it.id}-${i}`}
                className="irow"
                style={{ gridTemplateColumns: "110px 100px minmax(0,1fr) minmax(0,1fr)", cursor: "default" }}
              >
                <span className="idesc" style={{ margin: 0 }}>{new Date(it.ts * 1000).toLocaleDateString()}</span>
                <span className={`hist-action ha-${it.action}`}>{ACTION_LABEL[it.action] ?? it.action}</span>
                <div className="iname" style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {it.name}
                </div>
                <span className="ver-mono">
                  {it.action === "update" && it.from ? `${it.from} → ${it.to}` : it.to || it.from || "—"}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
