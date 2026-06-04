import { useEffect, useRef, useState } from "react";
import { bridge } from "./api";
import { Titlebar } from "./components/Titlebar";
import { AppBar } from "./components/AppBar";
import { Sidebar } from "./components/Sidebar";
import { StatusBar } from "./components/StatusBar";
import { PlaceholderScreen } from "./screens/PlaceholderScreen";
import { BrowseScreen } from "./screens/BrowseScreen";
import { InstalledScreen } from "./screens/InstalledScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import { HealthScreen } from "./screens/HealthScreen";
import { WeakAurasScreen } from "./screens/WeakAurasScreen";
import { BackupsScreen } from "./screens/BackupsScreen";

export type Theme = "dark" | "light" | "system";
export type Density = "comfortable" | "compact";
export type Accent = "teal" | "blue" | "purple" | "orange";
export type Screen = "browse" | "installed" | "weakauras" | "backups" | "health" | "settings";

function resolveTheme(t: Theme): "dark" | "light" {
  if (t === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return t;
}

const SCREEN_META: Record<Screen, { name: string; icon: string; description: string }> = {
  browse:    { name: "Browse",    icon: "🔍", description: "Discover and install addons from all sources" },
  installed: { name: "Installed", icon: "✓",  description: "Manage your installed addons" },
  weakauras: { name: "WeakAuras", icon: "⚡", description: "Import and manage WeakAura strings" },
  backups:   { name: "Backups",   icon: "💾", description: "Backup and restore addon configurations" },
  health:    { name: "Health",    icon: "♥",  description: "Diagnose addon conflicts and issues" },
  settings:  { name: "Settings",  icon: "⚙",  description: "Configure wowusky preferences" },
};

export default function App(): JSX.Element {
  const [version, setVersion] = useState("…");
  const [bridgeOk, setBridgeOk] = useState(false);
  const [screen, setScreen] = useState<Screen>(() => {
    return (localStorage.getItem("wowusky:screen") as Screen | null) ?? "browse";
  });
  const [theme, setTheme] = useState<Theme>(() => {
    return (localStorage.getItem("wowusky:theme") as Theme | null) ?? "dark";
  });
  const [density, setDensity] = useState<Density>(() => {
    return (localStorage.getItem("wowusky:density") as Density | null) ?? "comfortable";
  });
  const [accent, setAccent] = useState<Accent>(() => {
    return (localStorage.getItem("wowusky:accent") as Accent | null) ?? "teal";
  });
  const [refreshKey, setRefreshKey] = useState(0);
  const [rescanning, setRescanning] = useState(false);
  const [installedCount, setInstalledCount] = useState(0);
  const [updateCount, setUpdateCount] = useState(0);
  // Auto-update runs at most once per session, only for the active profile.
  const autoUpdateRan = useRef(false);

  function handleRescan() {
    setRescanning(true);
    bridge
      .call("app.rescan", {})
      .catch(() => {})
      .finally(() => {
        setRescanning(false);
        setRefreshKey((k) => k + 1);
      });
  }

  // Fetch version from bridge
  useEffect(() => {
    bridge
      .call<{ version: string }>("app.version")
      .then((r) => { setVersion(r.version); setBridgeOk(true); })
      .catch(() => setBridgeOk(false));
  }, []);

  // Keep the sidebar installed-count badge in sync (also after rescans).
  useEffect(() => {
    bridge
      .call<{ count: number }>("installed.list", {})
      .then((r) => setInstalledCount(r.count))
      .catch(() => {});
  }, [refreshKey]);

  // Background update check → "updates available" badge. If the active profile
  // has auto-update enabled, apply them once per session, then re-check.
  useEffect(() => {
    let cancelled = false;
    bridge
      .call<{ updates: Record<string, string> }>("installed.updates", {})
      .then((r) => {
        if (cancelled) return;
        const ids = Object.keys(r.updates ?? {});
        setUpdateCount(ids.length);
        if (ids.length === 0 || autoUpdateRan.current) return;
        return bridge
          .call<{ active_profile: string; profiles: Array<{ id: string; auto_update?: boolean }> }>("settings.get", {})
          .then((s) => {
            const active = s.profiles.find((p) => p.id === s.active_profile);
            if (!active?.auto_update) return;
            autoUpdateRan.current = true;
            return bridge
              .call("installed.updateAll", { ids })
              .then(() => { if (!cancelled) { setUpdateCount(0); setRefreshKey((k) => k + 1); } });
          });
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [refreshKey]);

  // Apply theme to document
  useEffect(() => {
    const resolved = resolveTheme(theme);
    document.documentElement.setAttribute("data-theme", resolved);
    localStorage.setItem("wowusky:theme", theme);

    if (theme === "system") {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      const handler = (e: MediaQueryListEvent) => {
        document.documentElement.setAttribute("data-theme", e.matches ? "dark" : "light");
      };
      mq.addEventListener("change", handler);
      return () => mq.removeEventListener("change", handler);
    }
  }, [theme]);

  // Apply density to document
  useEffect(() => {
    document.documentElement.setAttribute("data-density", density);
    localStorage.setItem("wowusky:density", density);
  }, [density]);

  // Apply accent to document
  useEffect(() => {
    document.documentElement.setAttribute("data-accent", accent);
    localStorage.setItem("wowusky:accent", accent);
  }, [accent]);

  // Persist screen choice
  useEffect(() => {
    localStorage.setItem("wowusky:screen", screen);
  }, [screen]);

  const meta = SCREEN_META[screen];

  return (
    <div className="win">
      <Titlebar />
      <AppBar
        version={version}
        theme={theme}
        density={density}
        onThemeChange={setTheme}
        onDensityChange={setDensity}
        onRescan={handleRescan}
        rescanning={rescanning}
        refreshKey={refreshKey}
        onProfileChange={() => setRefreshKey((k) => k + 1)}
      />
      <div className="body">
        <Sidebar screen={screen} onNav={setScreen} addonCount={installedCount} updateCount={updateCount} refreshKey={refreshKey} />
        <div className="content">
          {screen === "browse" ? (
            <BrowseScreen refreshKey={refreshKey} />
          ) : screen === "installed" ? (
            <InstalledScreen
              refreshKey={refreshKey}
              onChanged={() => setRefreshKey((k) => k + 1)}
            />
          ) : screen === "weakauras" ? (
            <WeakAurasScreen />
          ) : screen === "backups" ? (
            <BackupsScreen />
          ) : screen === "health" ? (
            <HealthScreen />
          ) : screen === "settings" ? (
            <SettingsScreen
              theme={theme}
              density={density}
              accent={accent}
              onThemeChange={setTheme}
              onDensityChange={setDensity}
              onAccentChange={setAccent}
              onProfileChange={() => setRefreshKey((k) => k + 1)}
            />
          ) : (
            <PlaceholderScreen name={meta.name} icon={meta.icon} description={meta.description} />
          )}
          <StatusBar version={version} bridgeOk={bridgeOk} refreshKey={refreshKey} />
        </div>
      </div>
    </div>
  );
}
