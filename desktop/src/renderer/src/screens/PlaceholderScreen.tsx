interface Props {
  name: string;
  icon: string;
  description: string;
}

export function PlaceholderScreen({ name, icon, description }: Props): JSX.Element {
  return (
    <div className="page">
      <div className="page-head">
        <div className="page-title">{name}</div>
        <div className="page-sub">{description}</div>
      </div>
      <div className="page-body">
        <div className="empty" style={{ marginTop: 40 }}>
          <div className="eicon" style={{ fontSize: 28 }}>{icon}</div>
          <h3>{name}</h3>
          <p>This screen is coming in a later phase. Stay tuned!</p>
        </div>
      </div>
    </div>
  );
}
