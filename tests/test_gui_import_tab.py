"""Tests for wowusky.gui.tabs.ImportTab and CurseForgeTab.

Builds real Tk widgets — skips cleanly when Tk/display is unavailable.
"""

import pytest

import wowusky.gui.theme as _theme
from wowusky.gui.context import AppContext
from wowusky.gui.fonts import make_font_set


def _make_root():
    try:
        import tkinter as tk
    except Exception:
        pytest.skip("tkinter not available")
    try:
        root = tk.Tk()
    except Exception:
        pytest.skip("no Tk display available")
    root.withdraw()
    return root


def _make_ctx(root):
    fonts = make_font_set("Helvetica", "monospace")

    def make_button(parent, text, command, variant="ghost", enabled=True, **kw):
        import tkinter as tk
        btn = tk.Label(parent, text=text)
        if enabled:
            btn.bind("<Button-1>", lambda e: command())
        return btn

    return AppContext(
        palette=_theme.PALETTE_DARK,
        theme_mode="dark",
        sans_family="Helvetica",
        mono_family="monospace",
        fonts=fonts,
        root=root,
        make_button=make_button,
        app_log=lambda m: None,
    )


# ---------------------------------------------------------------------------
# ImportTab
# ---------------------------------------------------------------------------

def _make_import_tab(root, **overrides):
    from wowusky.gui.tabs import ImportTab

    defaults = dict(
        newest_download_zip=lambda: None,
        guess_name_from_zip=lambda p: "TestAddon",
        cf_slug_from_ref=lambda r: r if r.startswith("test") else "",
        cf_files_url=lambda r: f"https://example.com/files/{r}",
        cf_search_url=lambda q: f"https://example.com/search?q={q}",
        has_cf_api_key=lambda: False,
        on_install_zip=lambda zp, name, cf_ref: None,
        on_install_cf=lambda ref: None,
        open_url=lambda u: None,
    )
    defaults.update(overrides)
    return ImportTab(_make_ctx(root), root, **defaults)


def test_import_tab_constructs():
    root = _make_root()
    try:
        tab = _make_import_tab(root)
        assert tab.frame is not None
        assert tab.file_var is not None
        assert tab.name_var is not None
        assert tab.cf_ref_var is not None
    finally:
        root.destroy()


def test_import_tab_clear_resets_fields():
    root = _make_root()
    try:
        tab = _make_import_tab(root)
        tab.file_var.set("/some/path.zip")
        tab.name_var.set("SomeAddon")
        tab.clear()
        assert tab.file_var.get() == ""
        assert tab.name_var.get() == ""
    finally:
        root.destroy()


def test_import_tab_install_calls_on_install_zip():
    root = _make_root()
    try:
        import os
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            tmp = f.name
        try:
            calls = []
            tab = _make_import_tab(root, on_install_zip=lambda zp, n, r: calls.append((zp, n, r)))
            tab.file_var.set(tmp)
            tab.name_var.set("MyAddon")
            tab._install()
            assert calls == [(tmp, "MyAddon", "")]
        finally:
            os.unlink(tmp)
    finally:
        root.destroy()


def test_import_tab_install_skips_when_no_file():
    root = _make_root()
    try:
        calls = []
        tab = _make_import_tab(root, on_install_zip=lambda *a: calls.append(a))
        tab.file_var.set("/nonexistent/path.zip")
        tab.name_var.set("MyAddon")
        tab._install()
        assert calls == []
    finally:
        root.destroy()


# ---------------------------------------------------------------------------
# CurseForgeTab
# ---------------------------------------------------------------------------

def _make_cf_tab(root, **overrides):
    from wowusky.gui.tabs import CurseForgeTab

    defaults = dict(
        has_cf_api_key=lambda: False,
        run_cf_search=lambda q, on_ok, on_err: None,
        render_mod_card=lambda parent, mod: None,
        cf_search_url=lambda q: f"https://example.com?q={q}",
        goto_import=lambda: None,
        import_latest_zip=lambda: None,
        open_url=lambda u: None,
    )
    defaults.update(overrides)
    return CurseForgeTab(_make_ctx(root), root, **defaults)


def test_cf_tab_constructs():
    root = _make_root()
    try:
        tab = _make_cf_tab(root)
        assert tab.frame is not None
        assert tab.canvas is not None
        assert tab.search_var is not None
        assert tab.status_var is not None
    finally:
        root.destroy()


def test_cf_tab_search_shows_fallback_when_no_key():
    root = _make_root()
    try:
        tab = _make_cf_tab(root, has_cf_api_key=lambda: False)
        tab.search()
        assert "Fallback" in tab.status_var.get()
    finally:
        root.destroy()


def test_cf_tab_search_calls_run_cf_search_when_key_present():
    root = _make_root()
    try:
        calls = []
        tab = _make_cf_tab(
            root,
            has_cf_api_key=lambda: True,
            run_cf_search=lambda q, ok, err: calls.append(q),
        )
        tab.search_var.set("elvui")
        tab.search()
        assert calls == ["elvui"]
    finally:
        root.destroy()


def test_cf_tab_on_results_renders_cards():
    root = _make_root()
    try:
        rendered = []
        tab = _make_cf_tab(
            root,
            has_cf_api_key=lambda: True,
            run_cf_search=lambda q, on_ok, on_err: on_ok([{"id": 1}, {"id": 2}]),
            render_mod_card=lambda parent, mod: rendered.append(mod["id"]),
        )
        tab.search()
        assert rendered == [1, 2]
        assert "2" in tab.status_var.get()
    finally:
        root.destroy()
