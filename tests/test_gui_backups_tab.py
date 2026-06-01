"""Tests for wowusky.gui.tabs.BackupsTab.

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


_SAMPLE = [
    {"path": "/tmp/wowusky-full-1.zip", "name": "wowusky-full-1.zip",
     "mtime": 1_700_000_000, "size": 5 * 1024 * 1024},
    {"path": "/tmp/wowusky-full-2.zip", "name": "wowusky-full-2.zip",
     "mtime": 1_700_100_000, "size": 12 * 1024 * 1024},
]


def _make_tab(root, *, items, **cbs):
    from wowusky.gui.tabs import BackupsTab

    defaults = dict(
        list_backups=lambda: items,
        on_create=lambda: None,
        on_restore=lambda p: None,
        open_folder=lambda d: None,
    )
    defaults.update(cbs)
    return BackupsTab(_make_ctx(root), root, **defaults)


def test_constructs_with_canvas_and_inner():
    root = _make_root()
    try:
        tab = _make_tab(root, items=[])
        assert tab.frame is not None
        assert tab.canvas is not None
        assert tab.inner is not None
    finally:
        root.destroy()


def test_render_empty_shows_placeholder():
    root = _make_root()
    try:
        tab = _make_tab(root, items=[])
        tab.render()
        labels = [w for w in tab.inner.winfo_children()
                  if w.winfo_class() == "Label"]
        assert any("No full backups" in lbl.cget("text") for lbl in labels)
    finally:
        root.destroy()


def test_render_lists_items():
    root = _make_root()
    try:
        tab = _make_tab(root, items=_SAMPLE)
        tab.render()
        # One placeholder absent; rows + separators created.
        assert len(tab.inner.winfo_children()) > 0
        text_dump = " ".join(
            _all_label_text(tab.inner)
        )
        assert "wowusky-full-1.zip" in text_dump
        assert "wowusky-full-2.zip" in text_dump
        assert "5.0 MB" in text_dump
        assert "12.0 MB" in text_dump
    finally:
        root.destroy()


def test_render_clears_previous_content():
    root = _make_root()
    try:
        tab = _make_tab(root, items=_SAMPLE)
        tab.render()
        first_count = len(tab.inner.winfo_children())
        tab.render()
        assert len(tab.inner.winfo_children()) == first_count
    finally:
        root.destroy()


def test_restore_callback_receives_path():
    root = _make_root()
    try:
        got = []
        tab = _make_tab(root, items=_SAMPLE, on_restore=got.append)
        tab.render()
        btn = _find_button(tab.inner, "Restore")
        assert btn is not None
        btn.event_generate("<Button-1>")
        root.update_idletasks()
        assert got and got[0] in (_SAMPLE[0]["path"], _SAMPLE[1]["path"])
    finally:
        root.destroy()


def _all_label_text(widget):
    out = []
    for child in widget.winfo_children():
        if child.winfo_class() == "Label":
            out.append(str(child.cget("text")))
        out.extend(_all_label_text(child))
    return out


def _find_button(widget, text):
    for child in widget.winfo_children():
        if child.winfo_class() == "Label" and str(child.cget("text")) == text:
            return child
        found = _find_button(child, text)
        if found is not None:
            return found
    return None
