"""Tests for wowusky.gui.dialogs.SettingsDialog.

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

    def make_button(parent, text, command, variant="ghost", enabled=True, **kw):
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


_INSTALLS = [
    {"flavor_name": "Retail", "addons_path": "/games/wow/_retail_/Interface/AddOns"},
    {"flavor_name": "Era", "addons_path": "/games/wow/_classic_era_/Interface/AddOns"},
]


def _make_dialog(root, **overrides):
    from wowusky.gui.dialogs import SettingsDialog

    defaults = dict(
        first_run=False,
        on_done=lambda: None,
        get_active_profile=lambda: {"name": "Main"},
        get_addons_path=lambda: "/games/wow/_retail_/Interface/AddOns",
        is_dry_run=lambda: False,
        get_cf_api_key=lambda: "",
        get_theme=lambda: "auto",
        scan_installations=lambda: _INSTALLS,
        add_or_update_profile=lambda name, path: None,
        set_addons_path=lambda p: None,
        set_dry_run=lambda b: None,
        set_cf_api_key=lambda k: None,
        reset_manager_state=lambda: None,
        diagnose_cf_api=lambda: (True, "ok"),
    )
    defaults.update(overrides)
    return SettingsDialog(_make_ctx(root), root, **defaults)


def _all_label_text(widget):
    out = []
    for child in widget.winfo_children():
        if child.winfo_class() == "Label":
            out.append(str(child.cget("text")))
        out.extend(_all_label_text(child))
    return out


def test_constructs():
    root = _make_root()
    try:
        dlg = _make_dialog(root)
        assert dlg.dialog is not None
    finally:
        root.destroy()


def test_first_run_title_and_no_cancel():
    root = _make_root()
    try:
        dlg = _make_dialog(root, first_run=True)
        texts = _all_label_text(dlg.dialog)
        assert any("Connect WoW installation" in t for t in texts)
        assert not any(t == "Cancel" for t in texts)
    finally:
        root.destroy()


def test_settings_title_has_cancel():
    root = _make_root()
    try:
        dlg = _make_dialog(root, first_run=False)
        texts = _all_label_text(dlg.dialog)
        assert any(t == "Cancel" for t in texts)
        assert any(t == "Save" for t in texts)
    finally:
        root.destroy()


def test_renders_detected_installations():
    root = _make_root()
    try:
        dlg = _make_dialog(root)
        texts = _all_label_text(dlg.dialog)
        assert any("Retail" in t for t in texts)
        assert any("Era" in t for t in texts)
    finally:
        root.destroy()


def test_empty_installations_shows_placeholder():
    root = _make_root()
    try:
        dlg = _make_dialog(root, scan_installations=lambda: [])
        texts = _all_label_text(dlg.dialog)
        assert any("No installations detected" in t for t in texts)
    finally:
        root.destroy()


def test_prefills_existing_values():
    root = _make_root()
    try:
        dlg = _make_dialog(
            root,
            get_active_profile=lambda: {"name": "Beta"},
            get_addons_path=lambda: "/custom/path",
        )
        assert dlg._profile_name_var.get() == "Beta"
        assert dlg._manual_var.get() == "/custom/path"
    finally:
        root.destroy()
