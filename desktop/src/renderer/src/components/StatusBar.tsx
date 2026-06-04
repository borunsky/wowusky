interface Props {
  version: string;
  bridgeOk: boolean;
}

export function StatusBar({ version, bridgeOk }: Props): JSX.Element {
  return (
    <div className="statusbar">
      {bridgeOk ? (
        <span className="ok">bridge connected</span>
      ) : (
        <span style={{ color: "var(--red)" }}>bridge error</span>
      )}
      <span className="right">
        <span>v{version}</span>
      </span>
    </div>
  );
}
