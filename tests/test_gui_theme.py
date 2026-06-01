"""Tests for wowusky.gui.theme — palettes and mode resolution.

These run headless (no Tk): theme.py is deliberately Tk-free.
"""

import wowusky.gui.theme as theme

PALETTE_KEYS = {
    "bg", "surface", "surface_hi", "border", "border_hi",
    "text", "text_dim", "text_muted",
    "accent", "accent_fg", "accent_hi", "accent_dim",
    "success", "warning", "danger", "input_bg", "input_fg",
}


def test_palettes_have_identical_key_sets():
    assert set(theme.PALETTE_DARK) == PALETTE_KEYS
    assert set(theme.PALETTE_LIGHT) == PALETTE_KEYS


def test_all_palette_values_are_hex_colours():
    for pal in (theme.PALETTE_DARK, theme.PALETTE_LIGHT):
        for k, v in pal.items():
            assert isinstance(v, str) and v.startswith("#") and len(v) == 7, f"{k}={v}"


def test_detect_system_theme_returns_valid_mode():
    assert theme.detect_system_theme() in ("dark", "light")


def test_get_palette_explicit_dark(monkeypatch):
    monkeypatch.setattr(theme._config, "load_config", lambda: {"theme": "dark"})
    pal, mode = theme.get_palette()
    assert mode == "dark"
    assert pal is theme.PALETTE_DARK


def test_get_palette_explicit_light(monkeypatch):
    monkeypatch.setattr(theme._config, "load_config", lambda: {"theme": "light"})
    pal, mode = theme.get_palette()
    assert mode == "light"
    assert pal is theme.PALETTE_LIGHT


def test_get_palette_auto_resolves_via_detect(monkeypatch):
    monkeypatch.setattr(theme._config, "load_config", lambda: {"theme": "auto"})
    monkeypatch.setattr(theme, "detect_system_theme", lambda: "light")
    pal, mode = theme.get_palette()
    assert mode == "light"
    assert pal is theme.PALETTE_LIGHT


def test_set_theme_mode_persists(monkeypatch):
    saved = {}
    monkeypatch.setattr(theme._config, "load_config", lambda: {})
    monkeypatch.setattr(theme._config, "save_config", saved.update)
    theme.set_theme_mode("light")
    assert saved == {"theme": "light"}
