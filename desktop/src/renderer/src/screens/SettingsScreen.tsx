import { useState, useEffect } from "react";
import { bridge } from "../api";
import type { Theme, Density, Accent } from "../App";

interface ScanResult {
  flavor: string;
  flavor_name: string;
  addons_path: string;
}

interface ProfileSummary {
  id: string;
  name: string;
  flavor: string;
  addons_path: string;
  color_tag: string | null;
  count: number;
  auto_update: boolean;
}

interface CoreSettings {
  addons_path: string;
  wtf_path: string;
  dry_run: boolean;
  auto_update_on_launch: boolean;
  curseforge_api_key_set: boolean;
  active_profile: string;
  profiles: ProfileSummary[];
}

interface DownloadZip {
  path: string;
  name: string;
  mtime: number;
  guess: { id: string; name: string } | null;
}

interface ScheduleStatus {
  available: boolean;
  installed: boolean;
  enabled?: boolean;
  active?: boolean;
  interval?: string;
  keep?: number;
  next_run?: string | null;
}

interface AddonPreviewItem {
  id: string;
  name: string;
  version: string;
  installed_version: string;
  source: string;
  status: "new" | "same" | "conflict";
}

interface ImportPreview {
  profile: string;
  profile_name: string;
  source_profile: string;
  preview: AddonPreviewItem[];
}

type SetPreviewItem = AddonPreviewItem;

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
  const [scanning, setScanning] = useState(false);
  const [scanResults, setScanResults] = useState<ScanResult[] | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [importPreview, setImportPreview] = useState<ImportPreview | null>(null);
  const [importData, setImportData] = useState<object | null>(null);
  const [skipConflicts, setSkipConflicts] = useState(false);
  const [importing, setImporting] = useState(false);
  const [schedule, setSchedule] = useState<ScheduleStatus | null>(null);
  const [scheduleInterval, setScheduleInterval] = useState<string>("daily");
  const [scheduleWorking, setScheduleWorking] = useState(false);
  // Scheduled backups (#51)
  const [bkSchedule, setBkSchedule] = useState<ScheduleStatus | null>(null);
  const [bkInterval, setBkInterval] = useState<string>("daily");
  const [bkKeep, setBkKeep] = useState<number>(5);
  const [bkWorking, setBkWorking] = useState(false);
  const [dlZips, setDlZips] = useState<DownloadZip[] | null>(null);
  const [dlScanning, setDlScanning] = useState(false);
  const [dlBusy, setDlBusy] = useState<string | null>(null);
  const [dlNotice, setDlNotice] = useState<string | null>(null);
  // Addon-set sharing (#44)
  const [setNotice, setSetNotice] = useState<string | null>(null);
  const [setPasteOpen, setSetPasteOpen] = useState(false);
  const [setPaste, setSetPaste] = useState("");
  const [setPreview, setSetPreview] = useState<SetPreviewItem[] | null>(null);
  const [shareSkip, setShareSkip] = useState(true);
  const [setBusy, setSetBusy] = useState(false);

  function exportSet() {
    setSetNotice(null);
    bridge.call<{ data: string; count: number }>("set.export", {})
      .then(async (r) => {
        await window.wowusky?.clipboardWrite?.(r.data);
        setSetNotice(`Copied ${r.count} addon${r.count === 1 ? "" : "s"} to clipboard`);
      })
      .catch((e) => setSetNotice(String(e)));
  }

  async function pasteFromClipboard() {
    const text = await window.wowusky?.clipboardRead?.();
    if (text) setSetPaste(text);
  }

  function previewSet() {
    setSetNotice(null);
    setSetPreview(null);
    bridge.call<{ ok: boolean; items?: SetPreviewItem[]; error?: string }>("set.importPreview", { data: setPaste })
      .then((r) => {
        if (!r.ok) { setSetNotice(r.error ?? "invalid addon-set"); return; }
        setSetPreview(r.items ?? []);
      })
      .catch((e) => setSetNotice(String(e)));
  }

  function applySet() {
    if (!setPreview) return;
    setSetBusy(true);
    const skip_ids = shareSkip
      ? setPreview.filter((i) => i.status === "conflict").map((i) => i.id)
      : [];
    bridge.call<{ ok: boolean; imported?: number; skipped?: number; error?: string }>(
      "set.importApply", { data: setPaste, skip_ids })
      .then((r) => {
        if (!r.ok) { setSetNotice(r.error ?? "import failed"); return; }
        setSetNotice(`Imported ${r.imported}, skipped ${r.skipped}`);
        setSetPreview(null);
        setSetPaste("");
        setSetPasteOpen(false);
        onProfileChange?.();
      })
      .catch((e) => setSetNotice(String(e)))
      .finally(() => setSetBusy(false));
  }

  function reload() {
    bridge.call<CoreSettings>("settings.get", {}).then((s) => {
      setCore(s);
      setAddonsPath(s.addons_path);
    }).catch(() => {});
    bridge.call<ScheduleStatus>("schedule.status", {}).then(setSchedule).catch(() => {});
    bridge.call<ScheduleStatus>("backupSchedule.status", {}).then((s) => {
      setBkSchedule(s);
      if (s.interval) setBkInterval(s.interval);
      if (s.keep) setBkKeep(s.keep);
    }).catch(() => {});
  }
  useEffect(reload, []);

  function enableSchedule() {
    setScheduleWorking(true);
    bridge.call<ScheduleStatus & { ok: boolean }>("schedule.enable", { interval: scheduleInterval })
      .then((r) => setSchedule(r))
      .catch(() => {})
      .finally(() => setScheduleWorking(false));
  }
  function disableSchedule() {
    setScheduleWorking(true);
    bridge.call<ScheduleStatus & { ok: boolean }>("schedule.disable", {})
      .then((r) => setSchedule(r))
      .catch(() => {})
      .finally(() => setScheduleWorking(false));
  }
  function enableBkSchedule() {
    setBkWorking(true);
    bridge.call<ScheduleStatus & { ok: boolean }>("backupSchedule.enable", { interval: bkInterval, keep: bkKeep })
      .then((r) => setBkSchedule(r))
      .catch(() => {})
      .finally(() => setBkWorking(false));
  }
  function disableBkSchedule() {
    setBkWorking(true);
    bridge.call<ScheduleStatus & { ok: boolean }>("backupSchedule.disable", {})
      .then((r) => setBkSchedule(r))
      .catch(() => {})
      .finally(() => setBkWorking(false));
  }

  function scanDownloads() {
    setDlScanning(true);
    setDlNotice(null);
    bridge.call<{ items: DownloadZip[] }>("downloads.scan", {})
      .then((r) => setDlZips(r.items))
      .catch(() => setDlZips([]))
      .finally(() => setDlScanning(false));
  }

  function importDownloadZip(zip: DownloadZip) {
    if (dlBusy) return;
    setDlBusy(zip.path);
    setDlNotice(null);
    bridge.call<{ ok: boolean; error?: string }>("downloads.import", {
      path: zip.path,
      name: zip.guess?.name,
    }).then((r) => {
      if (r.ok) {
        setDlZips((zips) => (zips ?? []).filter((z) => z.path !== zip.path));
        setDlNotice(`Imported ${zip.guess?.name ?? zip.name}`);
        onProfileChange();
      } else {
        setDlNotice(`Failed: ${r.error ?? "unknown error"}`);
      }
    })
    .catch((e) => setDlNotice(String(e)))
    .finally(() => setDlBusy(null));
  }

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
  function toggleAutoUpdateOnLaunch() {
    if (!core) return;
    bridge.call<CoreSettings>("settings.update", { auto_update_on_launch: !core.auto_update_on_launch })
      .then(setCore).catch(() => {});
  }
  function switchProfile(id: string) {
    bridge.call<CoreSettings>("profile.setActive", { profile: id })
      .then((s) => { setCore(s); setAddonsPath(s.addons_path); onProfileChange(); }).catch(() => {});
  }
  function toggleAutoUpdate(id: string, enabled: boolean) {
    bridge.call<CoreSettings>("profile.setAutoUpdate", { profile: id, enabled })
      .then((s) => { setCore(s); onProfileChange(); }).catch(() => {});
  }

  function autoscan() {
    setScanning(true);
    setScanResults(null);
    bridge.call<{ found: ScanResult[] }>("profiles.scan", {})
      .then((r) => setScanResults(r.found))
      .catch(() => setScanResults([]))
      .finally(() => setScanning(false));
  }

  function addScannedProfile(p: ScanResult) {
    bridge.call<CoreSettings>("profiles.addFromPath", { path: p.addons_path, name: p.flavor_name })
      .then((s) => {
        setCore(s);
        setAddonsPath(s.addons_path);
        // Drop the just-added install from the results; keep any others.
        setScanResults((rs) => (rs ?? []).filter((r) => r.addons_path !== p.addons_path));
        onProfileChange();
      })
      .catch(() => {});
  }

  function startRename(id: string, current: string) {
    setEditingId(id);
    setEditName(current);
  }
  function saveRename(id: string) {
    const name = editName.trim();
    if (!name) { setEditingId(null); return; }
    bridge.call<CoreSettings>("profile.rename", { profile: id, name })
      .then((s) => { setCore(s); setEditingId(null); flash(); onProfileChange(); })
      .catch(() => setEditingId(null));
  }
  function deleteProfile(id: string, name: string) {
    if (!window.confirm(`Delete profile "${name}"? Its installed list and backups on disk are kept.`)) {
      return;
    }
    bridge.call<CoreSettings>("profile.delete", { profile: id })
      .then((s) => { setCore(s); setAddonsPath(s.addons_path); onProfileChange(); })
      .catch(() => {});
  }

  function exportProfile(profileId: string) {
    bridge.call<{ json: string; filename: string }>("addons.exportSet", { profile: profileId })
      .then(({ json, filename }) => {
        const blob = new Blob([json], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch(() => {});
  }

  function handleImportFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const data = JSON.parse(ev.target?.result as string);
        bridge.call<ImportPreview>("addons.importSet", { data })
          .then((preview) => { setImportData(data); setImportPreview(preview); setSkipConflicts(false); })
          .catch(() => {});
      } catch { /* invalid JSON — ignore */ }
    };
    reader.readAsText(file);
  }

  function applyImport() {
    if (!importData || !importPreview) return;
    setImporting(true);
    const skip = skipConflicts
      ? (importPreview.preview ?? []).filter((p) => p.status === "conflict").map((p) => p.id)
      : [];
    bridge.call<CoreSettings & { imported: number; skipped: number }>(
      "addons.importSet.apply",
      { data: importData, profile: importPreview.profile, skip },
    ).then((s) => {
      setCore(s);
      setImportPreview(null);
      setImportData(null);
      onProfileChange();
      flash();
    }).catch(() => {}).finally(() => setImporting(false));
  }

  async function setPathDialog(profileId?: string) {
    const chosen = await bridge.openDirectory().catch(() => null);
    if (!chosen) return;
    const params: Record<string, string> = { path: chosen };
    if (profileId) params.profile = profileId;
    bridge.call<CoreSettings>("profile.setPath", params)
      .then((s) => { setCore(s); setAddonsPath(s.addons_path); flash(); onProfileChange(); })
      .catch(() => {});
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

          {/* Share addon set (#44) */}
          <div className="set-group">
            <h3>Share addon set</h3>
            <p className="gdesc">Copy your installed addons as a shareable snapshot, or import one from a friend.</p>
            <div className="set-card">
              <div className="set-row">
                <div className="sl">
                  <div className="st">Export current profile</div>
                  <div className="sd">Copies a portable JSON snapshot of your installed addons to the clipboard.</div>
                </div>
                <div className="sr">
                  <button className="btn btn-sm btn-primary" onClick={exportSet}>Copy to clipboard</button>
                </div>
              </div>
              <div className="set-row">
                <div className="sl">
                  <div className="st">Import a set</div>
                  <div className="sd">Paste a snapshot, preview what changes, then apply.</div>
                </div>
                <div className="sr">
                  <button className="btn btn-sm" onClick={() => { setSetPasteOpen((o) => !o); setSetPreview(null); }}>
                    {setPasteOpen ? "Cancel" : "Paste set…"}
                  </button>
                </div>
              </div>
              {setPasteOpen && (
                <div className="set-row" style={{ flexDirection: "column", alignItems: "stretch", gap: 10 }}>
                  <textarea
                    className="set-paste"
                    placeholder="Paste addon-set JSON here…"
                    value={setPaste}
                    onChange={(e) => setSetPaste(e.target.value)}
                    rows={5}
                  />
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <button className="btn btn-sm" onClick={pasteFromClipboard}>Paste from clipboard</button>
                    <button className="btn btn-sm btn-primary" disabled={!setPaste.trim()} onClick={previewSet}>Preview</button>
                  </div>
                  {setPreview && (
                    <>
                      <div className="set-preview-list">
                        {setPreview.map((it) => (
                          <div className="set-preview-row" key={it.id}>
                            <span className="spn">{it.name}</span>
                            <span className={`spbadge sp-${it.status}`}>{it.status}</span>
                            <span className="spv">
                              {it.status === "conflict" ? `${it.installed_version} → ${it.version}` : it.version}
                            </span>
                          </div>
                        ))}
                        {setPreview.length === 0 && <div className="sd">No addons in this set.</div>}
                      </div>
                      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                        <label className="set-check">
                          <input type="checkbox" checked={shareSkip} onChange={(e) => setShareSkip(e.target.checked)} />
                          Skip conflicts
                        </label>
                        <button className="btn btn-sm btn-primary" disabled={setBusy || setPreview.length === 0} onClick={applySet}>
                          {setBusy ? "Importing…" : "Apply"}
                        </button>
                      </div>
                    </>
                  )}
                </div>
              )}
              {setNotice && <div className="set-row"><div className="sl"><div className="sd">{setNotice}</div></div></div>}
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
                      {editingId === p.id ? (
                        <span className="field" style={{ display: "inline-flex" }}>
                          <input
                            autoFocus
                            value={editName}
                            onChange={(e) => setEditName(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") saveRename(p.id);
                              if (e.key === "Escape") setEditingId(null);
                            }}
                            style={{ width: 180 }}
                          />
                        </span>
                      ) : (
                        p.name
                      )}
                    </div>
                    <div className="sd" style={{ color: p.addons_path ? undefined : "var(--red)" }}>
                      {p.addons_path || "path not set"} · {p.count} addons
                    </div>
                    <label
                      className="auto-update-row"
                      style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6, cursor: "pointer" }}
                      title="Automatically update this profile's addons on launch"
                    >
                      <span className={`switch switch-sm${p.auto_update ? " on" : ""}`} onClick={(e) => { e.preventDefault(); toggleAutoUpdate(p.id, !p.auto_update); }}><i /></span>
                      <span className="sd" style={{ margin: 0 }}>Auto-update on launch</span>
                    </label>
                  </div>
                  <div className="sr" style={{ gap: 6, display: "flex", alignItems: "center" }}>
                    {editingId === p.id ? (
                      <>
                        <button className="btn btn-sm btn-primary" onClick={() => saveRename(p.id)}>Save</button>
                        <button className="btn btn-sm" onClick={() => setEditingId(null)}>Cancel</button>
                      </>
                    ) : (
                      <>
                        <button className="btn btn-sm" title="Rename profile" onClick={() => startRename(p.id, p.name)}>
                          Rename
                        </button>
                        <button className="btn btn-sm" title="Browse for AddOns folder" onClick={() => setPathDialog(p.id)}>
                          Set Path
                        </button>
                        {core?.active_profile === p.id ? (
                          <span className="installed-tag">Active</span>
                        ) : (
                          <button className="btn btn-sm" onClick={() => switchProfile(p.id)}>Activate</button>
                        )}
                        <button className="btn btn-sm" title="Export addon list" onClick={() => exportProfile(p.id)}>
                          Export
                        </button>
                        <button className="btn btn-sm btn-danger" title="Delete profile" onClick={() => deleteProfile(p.id, p.name)}>
                          Delete
                        </button>
                      </>
                    )}
                  </div>
                </div>
              ))}
              {core && core.profiles.length === 0 && (
                <div className="set-row"><div className="sl"><div className="sd">No profiles configured.</div></div></div>
              )}
              {/* Autoscan */}
              <div className="set-row" style={{ borderTop: "1px solid var(--border)", paddingTop: 12, marginTop: 4 }}>
                <div className="sl">
                  <div className="st">Auto-detect WoW installations</div>
                  <div className="sd">Scan common Steam / Lutris / Wine paths for WoW clients.</div>
                </div>
                <div className="sr">
                  <button className="btn btn-sm btn-primary" onClick={autoscan} disabled={scanning}>
                    {scanning ? "Scanning…" : "Autoscan"}
                  </button>
                </div>
              </div>
              {/* Scan results */}
              {scanResults !== null && scanResults.length === 0 && (
                <div className="set-row">
                  <div className="sl"><div className="sd">No WoW installations found automatically.</div></div>
                  <div className="sr">
                    <button className="btn btn-sm" onClick={() => setPathDialog()}>Set Path manually</button>
                  </div>
                </div>
              )}
              {(scanResults ?? []).map((r) => (
                <div className="set-row" key={r.addons_path}>
                  <div className="sl">
                    <div className="st" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span className="ptag">{r.flavor}</span>
                      {r.flavor_name}
                    </div>
                    <div className="sd">{r.addons_path}</div>
                  </div>
                  <div className="sr">
                    <button className="btn btn-sm btn-primary" onClick={() => addScannedProfile(r)}>Add</button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Addon Sets */}
          <div className="set-group">
            <h3>Addon Sets</h3>
            <p className="gdesc">Export or import a profile's full addon list as a portable JSON file.</p>
            <div className="set-card">
              <div className="set-row">
                <div className="sl">
                  <div className="st">Import addon set</div>
                  <div className="sd">Load a previously exported addon list into the active profile.</div>
                </div>
                <div className="sr">
                  <label className="btn btn-sm btn-primary" style={{ cursor: "pointer" }}>
                    Choose file…
                    <input
                      type="file"
                      accept=".json,application/json"
                      style={{ display: "none" }}
                      onChange={handleImportFile}
                    />
                  </label>
                </div>
              </div>
              {importPreview && (() => {
                const newCount = importPreview.preview.filter((p) => p.status === "new").length;
                const conflictCount = importPreview.preview.filter((p) => p.status === "conflict").length;
                const sameCount = importPreview.preview.filter((p) => p.status === "same").length;
                return (
                  <div style={{ padding: "8px 0 4px", borderTop: "1px solid var(--border)", marginTop: 4 }}>
                    <div className="sd" style={{ marginBottom: 8 }}>
                      From <strong>{importPreview.source_profile}</strong> →{" "}
                      <strong>{importPreview.profile_name}</strong>:{" "}
                      <span style={{ color: "var(--green)" }}>{newCount} new</span>
                      {conflictCount > 0 && <span style={{ color: "var(--red)", marginLeft: 6 }}>{conflictCount} conflict(s)</span>}
                      {sameCount > 0 && <span style={{ color: "var(--text-faint)", marginLeft: 6 }}>{sameCount} already installed</span>}
                    </div>
                    {conflictCount > 0 && (
                      <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, cursor: "pointer" }}>
                        <input type="checkbox" checked={skipConflicts} onChange={(e) => setSkipConflicts(e.target.checked)} />
                        <span className="sd">Skip conflicting addons</span>
                      </label>
                    )}
                    <div style={{ display: "flex", gap: 8 }}>
                      <button className="btn btn-sm btn-primary" onClick={applyImport} disabled={importing}>
                        {importing ? "Importing…" : "Apply import"}
                      </button>
                      <button className="btn btn-sm" onClick={() => { setImportPreview(null); setImportData(null); }}>
                        Cancel
                      </button>
                    </div>
                  </div>
                );
              })()}
            </div>
          </div>

          {/* Import from Downloads */}
          <div className="set-group">
            <h3>Import from Downloads</h3>
            <p className="gdesc">Install addon ZIPs directly from your Downloads folder. Catalog entries are guessed automatically.</p>
            <div className="set-card">
              <div className="set-row">
                <div className="sl">
                  <div className="st">Scan Downloads folder</div>
                  <div className="sd">Finds .zip files and matches them against the catalog.</div>
                </div>
                <div className="sr">
                  <button className="btn btn-sm btn-primary" disabled={dlScanning} onClick={scanDownloads}>
                    {dlScanning ? "Scanning…" : "Scan"}
                  </button>
                </div>
              </div>
              {dlNotice && (
                <div className="sd" style={{ marginTop: 6, color: "var(--accent)" }}>{dlNotice}</div>
              )}
              {dlZips !== null && (
                dlZips.length === 0 ? (
                  <div className="sd" style={{ marginTop: 6 }}>No addon ZIPs found in Downloads.</div>
                ) : (
                  <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
                    {dlZips.map((z) => (
                      <div key={z.path} className="set-row" style={{ alignItems: "center" }}>
                        <div className="sl" style={{ minWidth: 0 }}>
                          <div className="st" style={{ fontWeight: 500, fontSize: 13 }}>{z.name}</div>
                          {z.guess && (
                            <div className="sd">→ {z.guess.name}</div>
                          )}
                        </div>
                        <button
                          className="btn btn-sm btn-primary"
                          disabled={dlBusy !== null}
                          onClick={() => importDownloadZip(z)}
                        >
                          {dlBusy === z.path ? "Installing…" : "Install"}
                        </button>
                      </div>
                    ))}
                  </div>
                )
              )}
            </div>
          </div>

          {/* Scheduled Updates */}
          {schedule && (
            <div className="set-group">
              <h3>Scheduled Updates</h3>
              <p className="gdesc">
                Automatically check for addon updates via a systemd user timer — no GUI needed.
                Runs <code>wowusky update -q</code> on the configured schedule.
              </p>
              <div className="set-card">
                {!schedule.available ? (
                  <div className="set-row">
                    <div className="sl">
                      <div className="st">Scheduled updates</div>
                      <div className="sd">Not available — systemd user instance not detected.</div>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="set-row">
                      <div className="sl">
                        <div className="st">
                          Timer status
                          {schedule.installed && (
                            <span className={`installed-tag${schedule.enabled && schedule.active ? "" : " conflict"}`} style={{ marginLeft: 8 }}>
                              {schedule.enabled && schedule.active ? `enabled · ${schedule.interval ?? "daily"}` : schedule.enabled ? "enabled, inactive" : "disabled"}
                            </span>
                          )}
                        </div>
                        {schedule.installed && schedule.next_run && (
                          <div className="sd">Next run: {schedule.next_run}</div>
                        )}
                        {!schedule.installed && (
                          <div className="sd">No timer installed.</div>
                        )}
                      </div>
                    </div>
                    <div className="set-row" style={{ gap: 10 }}>
                      <div className="sl" style={{ flex: "none" }}>
                        <select
                          className="field"
                          value={scheduleInterval}
                          onChange={(e) => setScheduleInterval(e.target.value)}
                          disabled={scheduleWorking}
                        >
                          <option value="hourly">Hourly</option>
                          <option value="daily">Daily</option>
                          <option value="weekly">Weekly</option>
                        </select>
                      </div>
                      <button className="btn btn-sm btn-primary" disabled={scheduleWorking} onClick={enableSchedule}>
                        {scheduleWorking ? "…" : schedule.installed ? "Update timer" : "Enable"}
                      </button>
                      {schedule.installed && (
                        <button className="btn btn-sm btn-danger" disabled={scheduleWorking} onClick={disableSchedule}>
                          {scheduleWorking ? "…" : "Disable"}
                        </button>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>
          )}

          {/* Scheduled Backups (#51) */}
          {bkSchedule && (
            <div className="set-group">
              <h3>Scheduled Backups</h3>
              <p className="gdesc">
                Automatically create a full profile backup via a systemd user timer, keeping only
                the newest few. Runs <code>wowusky backup auto</code> on the configured schedule.
              </p>
              <div className="set-card">
                {!bkSchedule.available ? (
                  <div className="set-row">
                    <div className="sl">
                      <div className="st">Scheduled backups</div>
                      <div className="sd">Not available — systemd user instance not detected.</div>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="set-row">
                      <div className="sl">
                        <div className="st">
                          Timer status
                          {bkSchedule.installed && (
                            <span className={`installed-tag${bkSchedule.enabled && bkSchedule.active ? "" : " conflict"}`} style={{ marginLeft: 8 }}>
                              {bkSchedule.enabled && bkSchedule.active ? `enabled · ${bkSchedule.interval ?? "daily"} · keep ${bkSchedule.keep ?? 5}` : bkSchedule.enabled ? "enabled, inactive" : "disabled"}
                            </span>
                          )}
                        </div>
                        {bkSchedule.installed && bkSchedule.next_run && (
                          <div className="sd">Next run: {bkSchedule.next_run}</div>
                        )}
                        {!bkSchedule.installed && (
                          <div className="sd">No timer installed.</div>
                        )}
                      </div>
                    </div>
                    <div className="set-row" style={{ gap: 10 }}>
                      <div className="sl" style={{ flex: "none" }}>
                        <select
                          className="field"
                          value={bkInterval}
                          onChange={(e) => setBkInterval(e.target.value)}
                          disabled={bkWorking}
                        >
                          <option value="hourly">Hourly</option>
                          <option value="daily">Daily</option>
                          <option value="weekly">Weekly</option>
                        </select>
                      </div>
                      <label className="ss-keep" style={{ flex: "none" }}>
                        Keep
                        <input
                          type="number"
                          min={1}
                          value={bkKeep}
                          disabled={bkWorking}
                          onChange={(e) => setBkKeep(Math.max(1, Number(e.target.value) || 1))}
                        />
                      </label>
                      <button className="btn btn-sm btn-primary" disabled={bkWorking} onClick={enableBkSchedule}>
                        {bkWorking ? "…" : bkSchedule.installed ? "Update timer" : "Enable"}
                      </button>
                      {bkSchedule.installed && (
                        <button className="btn btn-sm btn-danger" disabled={bkWorking} onClick={disableBkSchedule}>
                          {bkWorking ? "…" : "Disable"}
                        </button>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>
          )}

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
                  <div className="st">Auto-update on launch</div>
                  <div className="sd">Silently update all outdated addons when the app starts. A summary toast is shown when complete.</div>
                </div>
                <div className="sr">
                  <div className={`switch${core?.auto_update_on_launch ? " on" : ""}`} onClick={toggleAutoUpdateOnLaunch}><i /></div>
                </div>
              </div>
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
