"""Tests for wowusky.gui.tabs.InstalledTab.

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


_SOURCE_LABEL = {
    "github": "GitHub", "external": "Local", "curseforge_manual": "CurseForge ZIP",
}

_INSTALLED = {
    "elvui": {"name": "ElvUI", "version": "13.5", "source": "github",
              "folders": ["ElvUI", "ElvUI_Options"]},
    "weakauras": {"name": "WeakAuras", "version": "5.0", "source": "external",
                  "folders": ["WeakAuras"]},
}


def _make_tab(root, *, installed=None, latest=None, catalog_ids=None, **cbs):
    from wowusky.gui.tabs import InstalledTab

    installed = _INSTALLED if installed is None else installed
    latest = latest or {}
    catalog_ids = catalog_ids if catalog_ids is not None else set(installed)

    defaults = dict(
        load_installed=lambda: installed,
        find_catalog=lambda aid: {"id": aid, "source": installed.get(aid, {}).get("source")} if aid in catalog_ids else None,
        get_latest=lambda aid: latest.get(aid),
        versions_equal=lambda a, b: str(a) == str(b),
        has_backup=lambda aid: False,
        cf_manual_latest=lambda e: None,
        cf_manual_url=lambda e: "https://example.com",
        source_label=_SOURCE_LABEL,
        on_rescan=lambda: None,
        on_check_updates=lambda: None,
        on_check_all_profiles=lambda: None,
        on_open_manager=lambda aid, ent: None,
        on_update=lambda a: None,
        on_rollback=lambda aid, ent: None,
        on_remove=lambda aid, ent: None,
        open_url=lambda u: None,
    )
    defaults.update(cbs)
    return InstalledTab(_make_ctx(root), root, **defaults)


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


def test_constructs():
    root = _make_root()
    try:
        tab = _make_tab(root)
        assert tab.frame is not None
        assert tab.canvas is not None
        assert tab.selected_sources() == set(tab._source_vars)
    finally:
        root.destroy()


def test_render_empty():
    root = _make_root()
    try:
        tab = _make_tab(root, installed={})
        tab.render()
        assert any("No addons installed" in t for t in _all_label_text(tab.inner))
        assert "(0/0)" in tab.count_var.get()
    finally:
        root.destroy()


def test_render_lists_installed_and_count():
    root = _make_root()
    try:
        tab = _make_tab(root)
        tab.render()
        texts = _all_label_text(tab.inner)
        assert any("ElvUI" in t for t in texts)
        assert any("WeakAuras" in t for t in texts)
        assert "(2/2)" in tab.count_var.get()
    finally:
        root.destroy()


def test_update_button_when_newer_version_available():
    root = _make_root()
    try:
        tab = _make_tab(root, installed={"elvui": _INSTALLED["elvui"]},
                        latest={"elvui": "14.0"})
        tab.render()
        assert _find_button(tab.inner, "Update") is not None
    finally:
        root.destroy()


def test_current_button_when_up_to_date():
    root = _make_root()
    try:
        tab = _make_tab(root, installed={"elvui": _INSTALLED["elvui"]},
                        latest={"elvui": "13.5"})
        tab.render()
        assert _find_button(tab.inner, "Current") is not None
        assert _find_button(tab.inner, "Update") is None
    finally:
        root.destroy()


def test_source_filter_excludes_unselected():
    root = _make_root()
    try:
        tab = _make_tab(root)
        # Deselect "external" -> only the github addon remains.
        tab._source_vars["external"].set(False)
        tab._on_source_change()
        texts = _all_label_text(tab.inner)
        assert any("ElvUI" in t for t in texts)
        assert not any("WeakAuras" in t for t in texts)
        assert "(1/2)" in tab.count_var.get()
    finally:
        root.destroy()


def test_remove_callback_receives_id():
    root = _make_root()
    try:
        got = []
        tab = _make_tab(root, installed={"elvui": _INSTALLED["elvui"]},
                        on_remove=lambda aid, ent: got.append(aid))
        tab.render()
        _click(_find_button(tab.inner, "Remove"))
        assert got == ["elvui"]
    finally:
        root.destroy()


def test_rollback_button_only_when_backup_exists():
    root = _make_root()
    try:
        tab = _make_tab(root, installed={"elvui": _INSTALLED["elvui"]},
                        has_backup=lambda aid: True)
        tab.render()
        assert _find_button(tab.inner, "Rollback") is not None
    finally:
        root.destroy()
