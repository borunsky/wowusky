import { useState, useEffect } from "react";
import { bridge } from "../api";

interface ScanResult {
  flavor: string;
  flavor_name: string;
  addons_path: string;
}

interface Props {
  /** Called once a profile has been configured (or the wizard is dismissed). */
  onDone: () => void;
}

/**
 * Guided first-run setup (#56). Shown when wowusky starts with no configured
 * profile: autoscan for WoW installations, pick one (or set a path manually),
 * then hand control back to the app on the Installed screen.
 */
export function FirstRunWizard({ onDone }: Props): JSX.Element {
  const [scanning, setScanning] = useState(false);
  const [results, setResults] = useState<ScanResult[] | null>(null);
  const [adding, setAdding] = useState(false);

  // Kick off an autoscan immediately so the common case is one click.
  useEffect(() => { runScan(); }, []);

  function runScan() {
    setScanning(true);
    setResults(null);
    bridge
      .call<{ found: ScanResult[] }>("profiles.scan", {})
      .then((r) => setResults(r.found ?? []))
      .catch(() => setResults([]))
      .finally(() => setScanning(false));
  }

  function add(path: string, name?: string) {
    if (adding) return;
    setAdding(true);
    bridge
      .call("profiles.addFromPath", name ? { path, name } : { path })
      .then(() => onDone())
      .catch(() => {})
      .finally(() => setAdding(false));
  }

  async function pickManual() {
    const chosen = await bridge.openDirectory().catch(() => null);
    if (chosen) add(chosen);
  }

  return (
    <div className="wizard-overlay">
      <div className="wizard">
        <div className="wizard-head">
          <div className="wizard-logo">W</div>
          <div>
            <h2>Welcome to wowusky</h2>
            <p>Let's connect your World of Warcraft installation to get started.</p>
          </div>
        </div>

        <div className="wizard-body">
          {scanning ? (
            <div className="wizard-state">
              <div className="spin" />
              <p>Scanning for WoW installations…</p>
            </div>
          ) : results && results.length > 0 ? (
            <>
              <div className="wizard-label">Found {results.length} installation{results.length === 1 ? "" : "s"}:</div>
              <div className="wizard-list">
                {results.map((r) => (
                  <div className="wizard-item" key={r.addons_path}>
                    <div style={{ minWidth: 0 }}>
                      <div className="wi-name">
                        <span className="ptag">{r.flavor}</span> {r.flavor_name}
                      </div>
                      <div className="wi-path">{r.addons_path}</div>
                    </div>
                    <button className="btn btn-sm btn-primary" disabled={adding} onClick={() => add(r.addons_path, r.flavor_name)}>
                      {adding ? "…" : "Use this"}
                    </button>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="wizard-state">
              <p>No WoW installations were found automatically.</p>
              <p className="wi-path">You can point wowusky at your AddOns folder manually.</p>
            </div>
          )}
        </div>

        <div className="wizard-foot">
          <button className="btn btn-sm" disabled={scanning} onClick={runScan}>Rescan</button>
          <button className="btn btn-sm" disabled={adding} onClick={pickManual}>Set path manually…</button>
          <button className="btn btn-sm wizard-skip" onClick={onDone}>Skip for now</button>
        </div>
      </div>
    </div>
  );
}
