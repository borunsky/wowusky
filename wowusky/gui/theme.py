"""Theme palettes and mode detection for the wowusky GUI.

Self-contained: depends only on ``subprocess`` (for desktop-theme
detection) and :mod:`wowusky.core.config` for the persisted theme
preference. No Tk imports, so it stays importable headless.
"""

from __future__ import annotations

from wowusky.core import config as _config

PALETTE_DARK = {
    # Surfaces (matches design A: Sidebar + Liste · Dark)
    "bg":         "#0a0c0f",   # app canvas
    "surface":    "#0e1116",   # header / sidebar / cards
    "surface_hi": "#141821",   # hover / panel
    "border":     "#1f2533",
    "border_hi":  "#2b3344",
    # Text
    "text":       "#e7ecf3",
    "text_dim":   "#b5bdcc",
    "text_muted": "#7c869a",
    # Mint accent
    "accent":     "#5eead4",
    "accent_fg":  "#052724",
    "accent_hi":  "#99f6e4",
    "accent_dim": "#134e4a",
    # Status
    "success":    "#5eead4",
    "warning":    "#fbbf24",
    "danger":     "#f43f5e",
    # Inputs
    "input_bg":   "#141821",
    "input_fg":   "#e7ecf3",
}

PALETTE_LIGHT = {
    "bg":         "#fafbfc",
    "surface":    "#ffffff",
    "surface_hi": "#f0f3f6",
    "border":     "#e4e8ed",
    "border_hi":  "#d0d7de",
    "text":       "#1f2328",
    "text_dim":   "#656d76",
    "text_muted": "#8b949e",
    "accent":     "#1e8e6e",
    "accent_fg":  "#ffffff",
    "accent_hi":  "#176b54",
    "accent_dim": "#a3d9c8",
    "success":    "#1e8e6e",
    "warning":    "#bf8700",
    "danger":     "#cf222e",
    "input_bg":   "#f6f8fa",
    "input_fg":   "#1f2328",
}


def detect_system_theme() -> str:
    """Probe the desktop for a dark/light preference.

    Tries GNOME (``gsettings``) then KDE (``kreadconfig``); defaults to
    ``"dark"`` when nothing usable is found.
    """
    import contextlib
    import subprocess
    with contextlib.suppress(Exception):
        r = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                           capture_output=True, text=True, timeout=2)
        if r.returncode == 0:
            v = r.stdout.strip().strip("'\"").lower()
            if "dark" in v:
                return "dark"
            if "light" in v:
                return "light"
    with contextlib.suppress(Exception):
        r = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
                           capture_output=True, text=True, timeout=2)
        if r.returncode == 0:
            v = r.stdout.strip().strip("'\"").lower()
            if "dark" in v:
                return "dark"
    for cmd in ("kreadconfig5", "kreadconfig6"):
        with contextlib.suppress(Exception):
            r = subprocess.run([cmd, "--group", "General", "--key", "ColorScheme"],
                               capture_output=True, text=True, timeout=2)
            if r.returncode == 0:
                v = r.stdout.strip().lower()
                if "dark" in v:
                    return "dark"
                if v:
                    return "light"
    return "dark"


def get_palette() -> tuple[dict, str]:
    """Return ``(palette, mode)`` for the configured theme.

    ``mode`` is the resolved concrete mode ("dark"/"light"); an "auto"
    preference is resolved via :func:`detect_system_theme`.
    """
    mode = _config.load_config().get("theme", "auto")
    if mode == "auto":
        mode = detect_system_theme()
    return (PALETTE_DARK if mode == "dark" else PALETTE_LIGHT), mode


def set_theme_mode(mode: str) -> None:
    cfg = _config.load_config()
    cfg["theme"] = mode
    _config.save_config(cfg)
