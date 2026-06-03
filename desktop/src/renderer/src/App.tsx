import { useEffect, useState } from "react";
import { bridge } from "./api";

/**
 * Phase 0 shell. Proves the Electron <-> Python bridge round-trip and the
 * custom titlebar window controls. The full redesigned UI (chrome, sidebar,
 * Browse/Detail/Installed/…) lands in later phases on top of this foundation.
 */
export default function App(): JSX.Element {
  const [version, setVersion] = useState<string>("…");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    bridge
      .call<{ version: string }>("app.version")
      .then((r) => setVersion(r.version))
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="boot">
      <header className="boot-titlebar">
        <span className="boot-drag">wowusky</span>
        <div className="boot-wincontrols">
          <button onClick={() => bridge.minimize()} aria-label="Minimize">
            ─
          </button>
          <button onClick={() => bridge.maximize()} aria-label="Maximize">
            ▢
          </button>
          <button
            className="boot-close"
            onClick={() => bridge.close()}
            aria-label="Close"
          >
            ✕
          </button>
        </div>
      </header>

      <main className="boot-body">
        <div className="boot-logo">W</div>
        <h1>wowusky</h1>
        <p className="boot-sub">Electron shell — Phase 0</p>
        {error ? (
          <p className="boot-err">bridge error: {error}</p>
        ) : (
          <p className="boot-ok">
            Python bridge connected · core v{version}
          </p>
        )}
      </main>
    </div>
  );
}
