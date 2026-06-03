import { useEffect, useState } from "react";
import { bridge } from "./api";
import { Titlebar } from "./components/Titlebar";
import { AppBar } from "./components/AppBar";
import { Sidebar } from "./components/Sidebar";
import { StatusBar } from "./components/StatusBar";
import { PlaceholderScreen } from "./screens/PlaceholderScreen";

export type Theme = "dark" | "light" | "system";
export type Density = "comfortable" | "compact";
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

  // Fetch version from bridge
  useEffect(() => {
    bridge
      .call<{ version: string }>("app.version")
      .then((r) => { setVersion(r.version); setBridgeOk(true); })
      .catch(() => setBridgeOk(false));
  }, []);

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
        onRescan={() => bridge.call("app.ping", { echo: "rescan" }).catch(() => {})}
      />
      <div className="body">
        <Sidebar screen={screen} onNav={setScreen} addonCount={0} />
        <div className="content">
          <PlaceholderScreen name={meta.name} icon={meta.icon} description={meta.description} />
          <StatusBar version={version} bridgeOk={bridgeOk} />
        </div>
      </div>
    </div>
  );
}
