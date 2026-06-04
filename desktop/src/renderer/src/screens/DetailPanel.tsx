import { useState, useEffect } from "react";
import { bridge } from "../api";
import { sourceLabel, rarityFor, type Addon } from "./browseData";

interface VersionChoice {
  label: string;
  url: string;
  version: string;
  type: string;
}

interface DepPreview {
  id: string;
  name: string;
  installed: boolean;
}

interface Props {
  addon: Addon | null;
  busy?: boolean;
  busyLabel?: string | null;
  disabled?: boolean;
  /** Latest version when an update is available for this installed addon. */
  updateVersion?: string | null;
  onClose: () => void;
  onInstall: () => void;
  onRemove: () => void;
  /** Install a specific version by direct ZIP url. */
  onInstallVersion?: (url: string, label: string) => void;
}

export function DetailPanel({ addon, busy, busyLabel, disabled, updateVersion, onClose, onInstall, onRemove, onInstallVersion }: Props): JSX.Element {
  const open = addon !== null;
  const [versions, setVersions] = useState<VersionChoice[] | null>(null);
  const [loadingVersions, setLoadingVersions] = useState(false);
  const [showVersions, setShowVersions] = useState(false);
  // Transitive catalog dependencies a fresh install would pull in.
  const [deps, setDeps] = useState<DepPreview[] | null>(null);
  const [depsMissing, setDepsMissing] = useState<string[]>([]);
  // Installed addons that conflict with this one.
  const [conflicts, setConflicts] = useState<{ id: string; name: string }[]>([]);

  // Sources that expose multiple selectable downloads.
  const versionable = addon?.source === "github" || addon?.source === "curse";

  useEffect(() => {
    setVersions(null);
    setShowVersions(false);
    if (!addon || !onInstallVersion) return;
    if (addon.source !== "github" && addon.source !== "curse") return;
    setLoadingVersions(true);
    bridge
      .call<{ versions: VersionChoice[] }>("addon.versions", { id: addon.id })
      .then((r) => setVersions(r.versions ?? []))
      .catch(() => setVersions([]))
      .finally(() => setLoadingVersions(false));
  }, [addon, onInstallVersion]);

  // Fetch the dependency preview for not-yet-installed addons that declare any.
  useEffect(() => {
    setDeps(null);
    setDepsMissing([]);
    if (!addon || addon.installed || (addon.depends?.length ?? 0) === 0) return;
    bridge
      .call<{ deps: DepPreview[]; missing: string[] }>("addon.deps", { id: addon.id })
      .then((r) => { setDeps(r.deps ?? []); setDepsMissing(r.missing ?? []); })
      .catch(() => {});
  }, [addon]);

  // Fetch conflict warnings for not-yet-installed addons.
  useEffect(() => {
    setConflicts([]);
    if (!addon || addon.installed) return;
    bridge
      .call<{ conflicts: { id: string; name: string }[] }>("addon.conflicts", { id: addon.id })
      .then((r) => setConflicts(r.conflicts ?? []))
      .catch(() => {});
  }, [addon]);

  // Release notes (#53): lazy-load on expand for addons with a pending update.
  const [notesOpen, setNotesOpen] = useState(false);
  const [notes, setNotes] = useState<{ version: string; notes: string } | null>(null);
  const [notesLoading, setNotesLoading] = useState(false);
  useEffect(() => { setNotesOpen(false); setNotes(null); }, [addon]);
  useEffect(() => {
    if (!notesOpen || notes || !addon) return;
    setNotesLoading(true);
    bridge
      .call<{ version: string; notes: string }>("addon.releaseNotes", { id: addon.id })
      .then((r) => setNotes(r))
      .catch(() => setNotes({ version: "", notes: "" }))
      .finally(() => setNotesLoading(false));
  }, [notesOpen, addon, notes]);

  const pendingDeps = (deps ?? []).filter((d) => !d.installed);
  return (
    <div className={`detail${open ? " open" : ""}`}>
      {addon && (
        <div className="detail-inner">
          <div className="detail-hero">
            <div className={`detail-cover cov-${rarityFor(addon)}`} />
            <div className="detail-top">
              <div
                className={`mono-badge mb-${rarityFor(addon)}`}
                style={{ width: 52, height: 52, fontSize: 22 }}
              >
                {addon.glyph}
              </div>
              <div style={{ minWidth: 0 }}>
                <div className="detail-name">{addon.name}</div>
                <div className="detail-author">by {addon.author}</div>
              </div>
              <button className="detail-x" onClick={onClose} aria-label="Close">
                <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                  <path d="M2 2l9 9M11 2l-9 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
              </button>
            </div>
            <div className="detail-cta">
              {addon.installed ? (
                <>
                  {(updateVersion || busy) && (
                    <button className="btn btn-primary" style={{ flex: 1 }} disabled={disabled} onClick={onInstall}>
                      {busy ? (busyLabel ?? "…") : `Update → ${updateVersion}`}
                    </button>
                  )}
                  <button
                    className="btn btn-danger"
                    style={updateVersion || busy ? undefined : { flex: 1 }}
                    disabled={disabled}
                    onClick={onRemove}
                  >
                    Remove
                  </button>
                </>
              ) : (
                <button className="btn btn-primary" style={{ flex: 1 }} disabled={disabled} onClick={onInstall}>
                  {busy ? (busyLabel ?? "…") : "Install"}
                </button>
              )}
            </div>

            {!addon.installed && pendingDeps.length > 0 && (
              <div className="dep-note" title={pendingDeps.map((d) => d.name).join(", ")}>
                <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
                  <path d="M7 1.5 12.5 4.5v5L7 12.5 1.5 9.5v-5L7 1.5z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
                </svg>
                Also installs {pendingDeps.length} {pendingDeps.length === 1 ? "dependency" : "dependencies"}:
                {" "}{pendingDeps.map((d) => d.name).join(", ")}
              </div>
            )}

            {!addon.installed && conflicts.length > 0 && (
              <div className="conflict-note" title={conflicts.map((c) => c.name).join(", ")}>
                <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
                  <path d="M7 1.5 13 12.5H1L7 1.5z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
                  <path d="M7 6v2.5M7 10.2v.3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                </svg>
                Conflicts with {conflicts.length === 1 ? "an installed addon" : `${conflicts.length} installed addons`}:
                {" "}{conflicts.map((c) => c.name).join(", ")}
              </div>
            )}

            {addon.installed && updateVersion && (
              <div className="notes-box">
                <button className="notes-toggle" onClick={() => setNotesOpen((v) => !v)}>
                  <svg
                    className="chev"
                    width="13" height="13" viewBox="0 0 14 14" fill="none"
                    style={{ transform: notesOpen ? "rotate(180deg)" : undefined }}
                  >
                    <path d="M3 5l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  What's new in v{updateVersion}
                </button>
                {notesOpen && (
                  <div className="notes-body">
                    {notesLoading ? (
                      <div className="notes-muted">Loading release notes…</div>
                    ) : notes && notes.notes ? (
                      <pre className="notes-pre">{notes.notes}</pre>
                    ) : (
                      <div className="notes-muted">No release notes available from this source.</div>
                    )}
                  </div>
                )}
              </div>
            )}

            {versionable && onInstallVersion && (
              <div className="detail-versions">
                <button
                  className="versions-toggle"
                  onClick={() => setShowVersions((v) => !v)}
                  disabled={loadingVersions}
                >
                  <svg
                    className="chev"
                    width="13" height="13" viewBox="0 0 14 14" fill="none"
                    style={{ transform: showVersions ? "rotate(180deg)" : undefined }}
                  >
                    <path d="M3 5l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  {loadingVersions
                    ? "Loading versions…"
                    : `Choose a specific version${versions ? ` (${versions.length})` : ""}`}
                </button>
                {showVersions && versions && (
                  versions.length === 0 ? (
                    <div className="idesc" style={{ padding: "4px 2px" }}>
                      No selectable versions{addon.source === "curse" ? " (a CurseForge API key is required)" : ""}.
                    </div>
                  ) : (
                    <div className="version-list">
                      {versions.map((v) => (
                        <div key={v.url} className="version-row">
                          <span className="vlabel" title={v.label}>{v.label}</span>
                          <span className={`vtype vt-${v.type}`}>{v.type}</span>
                          <button
                            className="btn btn-sm"
                            disabled={disabled}
                            onClick={() => onInstallVersion(v.url, v.label)}
                          >
                            Install
                          </button>
                        </div>
                      ))}
                    </div>
                  )
                )}
              </div>
            )}
          </div>

          <div className="detail-scroll scroll">
            <div className="detail-stats">
              <div className="ds">
                <div className="k">Source</div>
                <div className="v">
                  <span className={`pill src-${addon.source}`}>
                    <span className="dot" />
                    {sourceLabel(addon.source)}
                  </span>
                </div>
              </div>
              <div className="ds">
                <div className="k">Category</div>
                <div className="v">{addon.category}</div>
              </div>
              <div className="ds">
                <div className="k">Flavors</div>
                <div className="v">{addon.flavors.join(", ") || "—"}</div>
              </div>
              <div className="ds">
                <div className="k">Folders</div>
                <div className="v">{addon.folders.length}</div>
              </div>
            </div>

            <div className="dsec-title">Description</div>
            <div className="dprose">{addon.description || "No description available."}</div>

            <div className="dsec-title">Folders</div>
            <div className="taglist">
              {addon.folders.map((f) => (
                <span key={f} className="tag">{f}</span>
              ))}
            </div>

            {addon.depends.length > 0 && (
              <>
                <div className="dsec-title">Dependencies</div>
                <div className="deps">
                  {(deps && deps.length > 0 ? deps : addon.depends.map((d) => ({ id: d, name: d, installed: false }))).map((d) => (
                    <div key={d.id} className="dep">
                      <span className="dn">{d.name}</span>
                      <span className={`dm ver-mono${d.installed ? " dep-have" : ""}`}>
                        {d.installed ? "installed" : "required"}
                      </span>
                    </div>
                  ))}
                  {depsMissing.map((d) => (
                    <div key={d} className="dep">
                      <span className="dn">{d}</span>
                      <span className="dm ver-mono dep-missing">not in catalog</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
