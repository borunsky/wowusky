import { useState, useEffect } from "react";
import { bridge } from "../api";
import { sourceLabel, rarityFor, type Addon } from "./browseData";

interface VersionChoice {
  label: string;
  url: string;
  version: string;
  type: string;
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
                  {addon.depends.map((d) => (
                    <div key={d} className="dep">
                      <span className="dn">{d}</span>
                      <span className="dm ver-mono">required</span>
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
