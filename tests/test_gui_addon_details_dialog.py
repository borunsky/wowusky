"""Tests for wowusky.gui.dialogs.AddonDetailsDialog.

Builds a real Tk Toplevel, so these skip cleanly when Tk/display is
unavailable.
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

    def make_button(parent, text, command, variant="ghost", enabled=True,
                    compact=False, **kw):
        import tkinter as tk
        btn = tk.Label(parent, text=text)
        if enabled:
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


_SOURCE_LABEL = {"github": "GitHub", "curseforge_web": "CurseForge"}

_ADDON = {
    "id": "elvui", "name": "ElvUI", "author": "Tukz", "category": "UI",
    "source": "github", "description": "Full UI replacement.",
}


def _make_dialog(root, addon=None, **overrides):
    from wowusky.gui.dialogs import AddonDetailsDialog

    addon = _ADDON if addon is None else addon
    defaults = dict(
        source_label=_SOURCE_LABEL,
        provider_page_url=lambda a: "https://github.com/tukui-org/ElvUI",
        github_version_choices=lambda a: [],
        on_install=lambda a: None,
        on_install_version=lambda a, u, l: None,
        open_url=lambda u: None,
    )
    defaults.update(overrides)
    return AddonDetailsDialog(_make_ctx(root), root, addon, **defaults)


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


def test_constructs_with_metadata():
    root = _make_root()
    try:
        dlg = _make_dialog(root)
        texts = _all_label_text(dlg.dialog)
        assert any("ElvUI" in t for t in texts)
        assert any("GitHub" in t for t in texts)
        assert any("Full UI replacement" in t for t in texts)
        assert _find_button(dlg.dialog, "Install latest") is not None
    finally:
        root.destroy()


def test_open_page_button_present_when_url():
    root = _make_root()
    try:
        dlg = _make_dialog(root, provider_page_url=lambda a: "https://x.y")
        assert _find_button(dlg.dialog, "Open page") is not None
    finally:
        root.destroy()


def test_open_page_button_absent_when_no_url():
    root = _make_root()
    try:
        dlg = _make_dialog(root, provider_page_url=lambda a: None)
        assert _find_button(dlg.dialog, "Open page") is None
    finally:
        root.destroy()


def test_install_latest_fires_callback():
    root = _make_root()
    try:
        got = []
        dlg = _make_dialog(root, on_install=lambda a: got.append(a["id"]))
        _find_button(dlg.dialog, "Install latest")._command()
        assert got == ["elvui"]
    finally:
        root.destroy()


def test_version_choices_rendered():
    root = _make_root()
    try:
        choices = [{"label": "v13.5", "url": "u1"}, {"label": "v13.4", "url": "u2"}]
        dlg = _make_dialog(root, github_version_choices=lambda a: choices)
        # Run the worker synchronously, then drive the main-thread poll/render.
        dlg._fill_versions()
        dlg._poll_versions()
        root.update()
        texts = _all_label_text(dlg._list_wrap)
        assert any("v13.5" in t for t in texts)
        assert any("v13.4" in t for t in texts)
    finally:
        root.destroy()


def test_no_versions_shows_hint():
    root = _make_root()
    try:
        dlg = _make_dialog(root, addon={**_ADDON, "source": "curseforge_web"},
                           github_version_choices=lambda a: [])
        dlg._fill_versions()
        dlg._poll_versions()
        root.update()
        texts = _all_label_text(dlg._list_wrap)
        assert any("Direct version selection" in t for t in texts)
    finally:
        root.destroy()
