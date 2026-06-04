import { sourceLabel, rarityFor, type Addon } from "./browseData";

interface Props {
  addon: Addon | null;
  busy?: boolean;
  disabled?: boolean;
  onClose: () => void;
  onInstall: () => void;
  onRemove: () => void;
}

export function DetailPanel({ addon, busy, disabled, onClose, onInstall, onRemove }: Props): JSX.Element {
  const open = addon !== null;
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
                  <button className="btn" style={{ flex: 1 }} disabled={disabled} onClick={onInstall}>
                    {busy ? "…" : "Update"}
                  </button>
                  <button className="btn btn-danger" disabled={disabled} onClick={onRemove}>
                    Remove
                  </button>
                </>
              ) : (
                <button className="btn btn-primary" style={{ flex: 1 }} disabled={disabled} onClick={onInstall}>
                  {busy ? "…" : "Install"}
                </button>
              )}
            </div>
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
