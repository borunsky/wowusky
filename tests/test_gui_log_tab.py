"""Tests for wowusky.gui.tabs.LogTab.

LogTab builds real Tk widgets, so these tests skip cleanly when Tkinter or
an X display is unavailable (e.g. headless CI without tk, or this sandbox).
"""

import pytest

import wowusky.gui.theme as _theme
from wowusky.gui.context import AppContext
from wowusky.gui.fonts import make_font_set


def _make_root():
    """Return a hidden Tk root, or skip if Tk/display is unavailable."""
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
    return AppContext(
        palette=_theme.PALETTE_DARK,
        theme_mode="dark",
        sans_family="Helvetica",
        mono_family="monospace",
        fonts=fonts,
        root=root,
        make_button=lambda *a, **kw: None,
        app_log=lambda m: None,
    )


def test_log_tab_constructs_and_appends():
    from wowusky.gui.tabs import LogTab

    root = _make_root()
    try:
        ctx = _make_ctx(root)
        tab = LogTab(ctx, root)
        assert tab.frame is not None

        tab.log_msg("hello")
        tab.log_msg("world")
        contents = tab.box.get("1.0", "end")
        assert "hello" in contents
        assert "world" in contents
    finally:
        root.destroy()


def test_log_box_is_disabled_after_append():
    from wowusky.gui.tabs import LogTab

    root = _make_root()
    try:
        ctx = _make_ctx(root)
        tab = LogTab(ctx, root)
        tab.log_msg("x")
        # The widget is returned to the disabled (read-only) state.
        assert str(tab.box.cget("state")) == "disabled"
    finally:
        root.destroy()
