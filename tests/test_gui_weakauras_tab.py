"""Tests for wowusky.gui.tabs.WeakAurasTab.

Builds real Tk widgets, so these skip cleanly when Tk/display is unavailable.
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

    def make_button(parent, text, command, variant="ghost", **kw):
        import tkinter as tk
        btn = tk.Label(parent, text=text)
        btn._command = command
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


_AURAS = {
    "abc": {"name": "Alpha Aura", "version": 3, "type": "WeakAura"},
    "xyz": {"name": "Zeta Aura", "version": 1, "latest_version": 4,
            "type": "WeakAura"},
}


def _make_tab(root, *, auras, **cbs):
    from wowusky.gui.tabs import WeakAurasTab

    defaults = dict(
        load_auras=lambda: auras,
        on_generate=lambda: None,
        on_check=lambda: None,
        on_import=lambda: None,
        on_add=lambda: None,
        on_update=lambda s, e: None,
        on_remove=lambda s, e: None,
        open_url=lambda u: None,
    )
    defaults.update(cbs)
    return WeakAurasTab(_make_ctx(root), root, **defaults)


def _all_label_text(widget):
    out = []
    for child in widget.winfo_children():
        if child.winfo_class() == "Label":
            out.append(str(child.cget("text")))
        out.extend(_all_label_text(child))
    return out


def _click(btn):
    """Invoke a fake button's command deterministically.

    Synthetic ``event_generate("<Button-1>")`` is not reliably delivered to
    un-mapped widgets on a real X display (e.g. inside a packaging sandbox),
    so call the stored command directly instead.
    """
    cmd = getattr(btn, "_command", None)
    if cmd is not None:
        cmd()
    else:
        btn.event_generate("<Button-1>")


def _find_button(widget, text):
    for child in widget.winfo_children():
        if child.winfo_class() == "Label" and str(child.cget("text")) == text:
            return child
        found = _find_button(child, text)
        if found is not None:
            return found
    return None


def test_constructs_with_url_var_and_canvas():
    root = _make_root()
    try:
        tab = _make_tab(root, auras={})
        assert tab.frame is not None
        assert tab.canvas is not None
        assert tab.url_var.get() == ""
    finally:
        root.destroy()


def test_render_empty_shows_placeholder():
    root = _make_root()
    try:
        tab = _make_tab(root, auras={})
        tab.render()
        assert any("No auras tracked" in t for t in _all_label_text(tab.inner))
    finally:
        root.destroy()


def test_render_lists_auras_sorted():
    root = _make_root()
    try:
        tab = _make_tab(root, auras=_AURAS)
        tab.render()
        texts = _all_label_text(tab.inner)
        assert any("Alpha Aura" in t for t in texts)
        assert any("Zeta Aura" in t for t in texts)
    finally:
        root.destroy()


def test_update_button_only_when_update_available():
    root = _make_root()
    try:
        # Only the entry with latest_version > version gets an Update button.
        tab = _make_tab(root, auras={"xyz": _AURAS["xyz"]})
        tab.render()
        assert _find_button(tab.inner, "Update") is not None

        tab2 = _make_tab(root, auras={"abc": _AURAS["abc"]})
        tab2.render()
        assert _find_button(tab2.inner, "Update") is None
    finally:
        root.destroy()


def test_remove_callback_receives_slug_and_entry():
    root = _make_root()
    try:
        got = []
        tab = _make_tab(root, auras={"abc": _AURAS["abc"]},
                        on_remove=lambda s, e: got.append((s, e)))
        tab.render()
        _click(_find_button(tab.inner, "Remove"))
        assert got and got[0][0] == "abc"
    finally:
        root.destroy()


def test_clear_input():
    root = _make_root()
    try:
        tab = _make_tab(root, auras={})
        tab.url_var.set("something")
        tab.clear_input()
        assert tab.url_var.get() == ""
    finally:
        root.destroy()
