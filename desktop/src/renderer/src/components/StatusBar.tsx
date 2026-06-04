import { useState, useEffect } from "react";
import { bridge } from "../api";

interface ProfileInfo {
  flavor: string;
  addons_path: string;
}

interface Props {
  version: string;
  bridgeOk: boolean;
  refreshKey?: number;
}

export function StatusBar({ version, bridgeOk, refreshKey = 0 }: Props): JSX.Element {
  const [profile, setProfile] = useState<ProfileInfo | null>(null);

  useEffect(() => {
    if (!bridgeOk) return;
    bridge.call<{ active_profile: string; profiles: ProfileInfo[] }>("settings.get", {})
      .then((s) => {
        const profiles = s.profiles as Array<{ id: string; flavor: string; addons_path: string }>;
        const active = profiles.find((p) => p.id === s.active_profile) ?? null;
        setProfile(active ? { flavor: active.flavor, addons_path: active.addons_path } : null);
      })
      .catch(() => {});
  }, [bridgeOk, refreshKey]);

  return (
    <div className="statusbar">
      {bridgeOk ? (
        profile ? (
          <span className="ok">
            <span className="sb-flavor">{profile.flavor}</span>
            <span className="sb-sep">·</span>
            <span className={profile.addons_path ? "sb-path" : "sb-path-missing"}>
              {profile.addons_path || "path not set"}
            </span>
          </span>
        ) : (
          <span className="ok">bridge connected</span>
        )
      ) : (
        <span style={{ color: "var(--red)" }}>bridge error</span>
      )}
      <span className="right">
        <span>v{version}</span>
      </span>
    </div>
  );
}
