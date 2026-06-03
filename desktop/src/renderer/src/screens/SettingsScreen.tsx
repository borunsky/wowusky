import { useState, useEffect } from "react";
import { bridge } from "../api";
import type { Theme, Density, Accent } from "../App";

interface ProfileSummary {
  id: string;
  name: string;
  flavor: string;
  addons_path: string;
  color_tag: string | null;
  count: number;
}

interface CoreSettings {
  addons_path: string;
  wtf_path: string;
  dry_run: boolean;
  curseforge_api_key_set: boolean;
  active_profile: string;
  profiles: ProfileSummary[];
}

interface Props {
  theme: Theme;
  density: Density;
  accent: Accent;
  onThemeChange: (t: Theme) => void;
  onDensityChange: (d: Density) => void;
  onAccentChange: (a: Accent) => void;
  onProfileChange: () => void;
}

const ACCENTS: { id: Accent; color: string }[] = [
  { id: "teal", color: "#2fe0c8" },
  { id: "blue", color: "#4d9fff" },
  { id: "purple", color: "#a78bff" },
  { id: "orange", color: "#ff9a5e" },
];

export function SettingsScreen({
  theme, density, accent,
  onThemeChange, onDensityChange, onAccentChange, onProfileChange,
}: Props): JSX.Element {
  const [core, setCore] = useState<CoreSettings | null>(null);
  const [addonsPath, setAddonsPath] = useState("");
  const [cfKey, setCfKey] = useState("");
  const [saved, setSaved] = useState(false);

  function reload() {
    bridge.call<CoreSettings>("settings.get", {}).then((s) => {
      setCore(s);
      setAddonsPath(s.addons_path);
    }).catch(() => {});
  }
  useEffect(reload, []);

  function flash() {
    setSaved(true);
    setTimeout(() => setSaved(false), 1400);
  }

  function savePath() {
    bridge.call<CoreSettings>("settings.update", { addons_path: addonsPath })
      .then((s) => { setCore(s); flash(); }).catch(() => {});
  }
  function saveKey() {
    bridge.call<CoreSettings>("settings.update", { curseforge_api_key: cfKey })
      .then((s) => { setCore(s); setCfKey(""); flash(); }).catch(() => {});
  }
  function toggleDryRun() {
    if (!core) return;
    bridge.call<CoreSettings>("settings.update", { dry_run: !core.dry_run })
      .then(setCore).catch(() => {});
  }
  function switchProfile(id: string) {
    bridge.call<CoreSettings>("profile.setActive", { profile: id })
      .then((s) => { setCore(s); onProfileChange(); }).catch(() => {});
  }

  return (
    <div className="page">
      <div className="page-head">
        <div className="page-title">
          Settings
          {saved && <span className="installed-tag">Saved</span>}
        </div>
        <div className="page-sub">Configure wowusky preferences</div>
      </div>

      <div className="page-body scroll">
        <div className="settings-wrap">
          {/* Appearance */}
          <div className="set-group">
            <h3>Appearance</h3>
            <p className="gdesc">Customize the look and feel of wowusky.</p>
            <div className="set-card">
              <div className="set-row">
                <div className="sl">
                  <div className="st">Theme</div>
                  <div className="sd">Switch between dark, light, or follow your system.</div>
                </div>
                <div className="sr">
                  <div className="seg">
                    {(["dark", "system", "light"] as Theme[]).map((t) => (
                      <button key={t} className={theme === t ? "on" : ""} onClick={() => onThemeChange(t)}>
                        {t[0].toUpperCase() + t.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
              <div className="set-row">
                <div className="sl">
                  <div className="st">Accent color</div>
                  <div className="sd">The highlight color used across the interface.</div>
                </div>
                <div className="sr" style={{ display: "flex", gap: 10 }}>
                  {ACCENTS.map((a) => (
                    <button
                      key={a.id}
                      onClick={() => onAccentChange(a.id)}
                      title={a.id}
                      aria-label={a.id}
                      style={{
                        width: 26, height: 26, borderRadius: "50%", cursor: "pointer",
                        background: a.color,
                        border: accent === a.id ? "2px solid var(--text)" : "2px solid transparent",
                        outline: accent === a.id ? "2px solid " + a.color : "none",
                        outlineOffset: 1,
                      }}
                    />
                  ))}
                </div>
              </div>
              <div className="set-row">
                <div className="sl">
                  <div className="st">Density</div>
                  <div className="sd">Comfortable spacing or a more compact layout.</div>
                </div>
                <div className="sr">
                  <div className="seg">
                    {(["comfortable", "compact"] as Density[]).map((d) => (
                      <button key={d} className={density === d ? "on" : ""} onClick={() => onDensityChange(d)}>
                        {d[0].toUpperCase() + d.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Profiles */}
          <div className="set-group">
            <h3>Profiles</h3>
            <p className="gdesc">Each profile points at one WoW installation.</p>
            <div className="set-card">
              {(core?.profiles ?? []).map((p) => (
                <div className="set-row" key={p.id}>
                  <div className="sl">
                    <div className="st" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span
                        className="ptag"
                        style={{ background: p.color_tag ?? undefined, color: p.color_tag ? "#06231f" : undefined }}
                      >
                        {p.flavor}
                      </span>
                      {p.name}
                    </div>
                    <div className="sd">{p.addons_path || "path not set"} · {p.count} addons</div>
                  </div>
                  <div className="sr">
                    {core?.active_profile === p.id ? (
                      <span className="installed-tag">Active</span>
                    ) : (
                      <button className="btn btn-sm" onClick={() => switchProfile(p.id)}>Activate</button>
                    )}
                  </div>
                </div>
              ))}
              {core && core.profiles.length === 0 && (
                <div className="set-row"><div className="sl"><div className="sd">No profiles configured.</div></div></div>
              )}
            </div>
          </div>

          {/* Paths */}
          <div className="set-group">
            <h3>Paths</h3>
            <p className="gdesc">Where the active profile's addons live.</p>
            <div className="set-card">
              <div className="set-row">
                <div className="sl" style={{ flex: 1 }}>
                  <div className="st">AddOns folder</div>
                  <div className="import-input" style={{ marginTop: 8 }}>
                    <div className="field">
                      <input
                        value={addonsPath}
                        onChange={(e) => setAddonsPath(e.target.value)}
                        placeholder="/path/to/Interface/AddOns"
                      />
                    </div>
                    <button className="btn btn-primary" onClick={savePath} disabled={addonsPath === core?.addons_path}>
                      Save
                    </button>
                  </div>
                </div>
              </div>
              {core?.wtf_path && (
                <div className="set-row">
                  <div className="sl">
                    <div className="st">WTF folder</div>
                    <div className="sd">{core.wtf_path}</div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Integrations */}
          <div className="set-group">
            <h3>Integrations</h3>
            <p className="gdesc">Optional API keys for premium sources.</p>
            <div className="set-card">
              <div className="set-row">
                <div className="sl" style={{ flex: 1 }}>
                  <div className="st">
                    CurseForge API key
                    {core?.curseforge_api_key_set && <span className="installed-tag" style={{ marginLeft: 8 }}>configured</span>}
                  </div>
                  <div className="import-input" style={{ marginTop: 8 }}>
                    <div className="field">
                      <input
                        type="password"
                        value={cfKey}
                        onChange={(e) => setCfKey(e.target.value)}
                        placeholder={core?.curseforge_api_key_set ? "•••••••• (set — enter to replace)" : "Enter API key"}
                      />
                    </div>
                    <button className="btn btn-primary" onClick={saveKey} disabled={!cfKey}>Save</button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Advanced */}
          <div className="set-group">
            <h3>Advanced</h3>
            <div className="set-card">
              <div className="set-row">
                <div className="sl">
                  <div className="st">Dry-run mode</div>
                  <div className="sd">Simulate installs and removals without touching the filesystem.</div>
                </div>
                <div className="sr">
                  <div className={`switch${core?.dry_run ? " on" : ""}`} onClick={toggleDryRun}><i /></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
