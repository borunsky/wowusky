"""Tests for wowusky.gui.tabs.BrowseTab.

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


_CATALOG = [
    {"id": "elvui", "name": "ElvUI", "description": "UI replacement", "author": "Tukz",
     "source": "tukui", "category": "UI", "flavors": ["retail", "vanilla"]},
    {"id": "weakauras", "name": "WeakAuras", "description": "Aura framework", "author": "Ace",
     "source": "github", "category": "Combat", "flavors": ["retail"]},
    {"id": "bagnon", "name": "Bagnon", "description": "Inventory", "author": "Tuller",
     "source": "curseforge", "category": "Inventory", "flavors": ["retail", "vanilla"]},
]

_INSTALLED = {
    "elvui": {"name": "ElvUI", "version": "13.5", "source": "tukui"},
}


def _make_tab(root, *, catalog=None, installed=None, **kw):
    from wowusky.gui.tabs import BrowseTab

    catalog = _CATALOG if catalog is None else catalog
    installed = _INSTALLED if installed is None else installed

    defaults = dict(
        get_catalog=lambda: catalog,
        load_installed=lambda: installed,
        get_categories=lambda: sorted({a["category"] for a in catalog}),
        get_current_flavor=lambda: "retail",
        filter_by_flavor=lambda ads, fl: [a for a in ads if fl in a.get("flavors", [])],
        render_card=lambda parent, addon, inst: None,
    )
    defaults.update(kw)
    return BrowseTab(_make_ctx(root), root, **defaults)


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
        tab = _make_tab(root)
        assert tab.frame is not None
        assert tab.canvas is not None
        assert tab.selected_source_set()
    finally:
        root.destroy()


def test_render_calls_render_card():
    root = _make_root()
    try:
        rendered = []
        tab = _make_tab(root, render_card=lambda p, a, i: rendered.append(a["id"]))
        tab.render()
        assert len(rendered) > 0
    finally:
        root.destroy()


def test_search_filters_results():
    root = _make_root()
    try:
        rendered = []
        tab = _make_tab(root, render_card=lambda p, a, i: rendered.append(a["id"]))
        tab.search_var.set("ElvUI")
        rendered.clear()
        tab.render()
        assert rendered == ["elvui"]
    finally:
        root.destroy()


def test_flavor_filter_all_shows_everything():
    root = _make_root()
    try:
        rendered = []
        tab = _make_tab(root, render_card=lambda p, a, i: rendered.append(a["id"]))
        tab.flavor_filter_var.set("all")
        tab.render()
        assert set(rendered) == {"elvui", "weakauras", "bagnon"}
    finally:
        root.destroy()


def test_flavor_filter_auto_uses_current_flavor():
    root = _make_root()
    try:
        rendered = []
        tab = _make_tab(
            root,
            get_current_flavor=lambda: "vanilla",
            render_card=lambda p, a, i: rendered.append(a["id"]),
        )
        tab.flavor_filter_var.set("auto")
        tab.render()
        # vanilla addons: elvui + bagnon
        assert set(rendered) == {"elvui", "bagnon"}
    finally:
        root.destroy()


def test_source_filter_excludes_deselected():
    root = _make_root()
    try:
        rendered = []
        tab = _make_tab(
            root,
            render_card=lambda p, a, i: rendered.append(a["id"]),
        )
        tab.flavor_filter_var.set("all")
        tab._source_vars["GitHub"].set(False)
        tab.render()
        assert "weakauras" not in rendered
    finally:
        root.destroy()


def test_result_count_var_updated():
    root = _make_root()
    try:
        tab = _make_tab(root)
        tab.flavor_filter_var.set("all")
        tab.render()
        assert tab.result_count_var.get() == f"{len(_CATALOG)} results"
    finally:
        root.destroy()


def test_empty_state_when_no_match():
    root = _make_root()
    try:
        tab = _make_tab(root, render_card=lambda p, a, i: None)
        tab.search_var.set("zzznomatch")
        tab.render()
        texts = _all_label_text(tab.inner)
        assert any("No addons" in t for t in texts)
    finally:
        root.destroy()
