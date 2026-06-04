import { bridge } from "../api";

export function Titlebar(): JSX.Element {
  return (
    <div className="titlebar" style={{ WebkitAppRegion: "drag" } as React.CSSProperties}>
      <div className="tb-dots" />
      <span className="tb-title">wowusky</span>
      <div className="tb-ctrls" style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}>
        <button onClick={() => bridge.minimize()} aria-label="Minimize" title="Minimize">
          <svg width="11" height="2" viewBox="0 0 11 2" fill="none">
            <path d="M1 1h9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </button>
        <button onClick={() => bridge.maximize()} aria-label="Maximize" title="Maximize">
          <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
            <rect x="1" y="1" width="9" height="9" rx="2" stroke="currentColor" strokeWidth="1.5"/>
          </svg>
        </button>
        <button className="close" onClick={() => bridge.close()} aria-label="Close" title="Close">
          <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
            <path d="M1.5 1.5 9.5 9.5M9.5 1.5 1.5 9.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </button>
      </div>
    </div>
  );
}
