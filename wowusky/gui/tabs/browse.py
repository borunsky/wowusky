"""BrowseTab — the catalog-browsing pane of the wowusky GUI.

Owns the whole filter card (search box, sort dropdown, flavor + source
chips, category dropdown, result count), the scrollable list, and the
filter/sort logic in :meth:`render`.  Per-row rendering is delegated to an
injected ``render_card`` callback, so the install-coupled card builder stays
in ``app.py`` while all the filtering and layout lives here.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import Any

from wowusky.gui.widgets import HoverScrollbar

ACCENT_SOFT = "#0f3530"

FLAVOR_OPTS = [
    ("Active", "auto"),
    ("Retail", "retail"), ("TBC", "anniversary"),
    ("Era", "vanilla"), ("MoP", "mop_classic"),
    ("All", "all"),
]

SOURCE_FILTER_MAP = {
    "GitHub":     {"github"},
    "Tukui":      {"tukui"},
    "WoWI":       {"wowi"},
    "CurseForge": {"curseforge", "curseforge_web", "curseforge_manual"},
    "Local":      {"manual", "external"},
    "wowusky":    {"internal_wac"},
}


class BrowseTab:
    """Catalog browser with search, sort, flavor/source chips and categories.

    Parameters
    ----------
    ctx:
        Shared :class:`~wowusky.gui.context.AppContext`.
    parent:
        The Tk container the tab frame is created in.
    get_catalog:
        Zero-arg callable returning the full addon catalog list.
    load_installed:
        Zero-arg callable returning the ``{addon_id: entry}`` installed map.
    get_categories:
        Zero-arg callable returning the sorted category list.
    get_current_flavor:
        Zero-arg callable returning the active profile's flavor (or falsy).
    filter_by_flavor:
        ``(catalog, flavor) -> list`` flavor filter.
    render_card:
        ``(parent, addon, installed_entry) -> None`` per-row renderer.
    """

    def __init__(
        self,
        ctx: Any,
        parent: Any,
        *,
        get_catalog: Callable[[], list],
        load_installed: Callable[[], dict],
        get_categories: Callable[[], list],
        get_current_flavor: Callable[[], Any],
        filter_by_flavor: Callable[[list, Any], list],
        render_card: Callable[[Any, dict, Any], None],
    ):
        import tkinter as tk
        from tkinter import ttk

        self.ctx = ctx
        self._get_catalog = get_catalog
        self._load_installed = load_installed
        self._get_current_flavor = get_current_flavor
        self._filter_by_flavor = filter_by_flavor
        self._render_card = render_card
        self._render_job = [None]
        self._chips: list = []
        C = ctx.palette
        sans = ctx.sans_family

        self.frame = tk.Frame(parent, bg=C["bg"])

        filter_card = tk.Frame(self.frame, bg=C["surface"],
                               highlightbackground=C["border"],
                               highlightthickness=1)
        filter_card.pack(fill="x", padx=10, pady=(14, 10))

        # ---- Row 1: search + sort -----------------------------------
        row1 = tk.Frame(filter_card, bg=C["surface"])
        row1.pack(fill="x", padx=10, pady=(10, 8))

        search_wrap = tk.Frame(row1, bg=C["input_bg"],
                               highlightbackground=C["border"], highlightthickness=1)
        search_wrap.pack(side="left", fill="x", expand=True, padx=(0, 8))
        tk.Label(search_wrap, text="⌕", bg=C["input_bg"], fg=C["text_muted"],
                 font=(sans, 12), padx=10).pack(side="left")
        self.search_var = tk.StringVar()
        tk.Entry(search_wrap, textvariable=self.search_var, bg=C["input_bg"],
                 fg=C["text"], insertbackground=C["accent"], font=ctx.font_body,
                 borderwidth=0, highlightthickness=0, relief="flat").pack(
                     side="left", fill="x", expand=True, ipady=6, padx=(0, 10))

        self.sort_var = tk.StringVar(value="Popular")
        ttk.Combobox(row1, textvariable=self.sort_var,
                     values=["Popular", "Name (A–Z)", "Recently updated"],
                     state="readonly", font=ctx.font_sm, width=18).pack(
                         side="right", ipady=3)

        # ---- Row 2: flavor + source chips, category, count ----------
        row2 = tk.Frame(filter_card, bg=C["surface"])
        row2.pack(fill="x", padx=10, pady=(0, 10))

        self.flavor_filter_var = tk.StringVar(value="auto")

        tk.Label(row2, text="FLAVOR", bg=C["surface"], fg=C["text_muted"],
                 font=(sans, 8, "bold")).pack(side="left", padx=(0, 8))
        fl_chips = tk.Frame(row2, bg=C["surface"])
        fl_chips.pack(side="left", padx=(0, 14))
        for label, key in FLAVOR_OPTS:
            self._make_chip(
                fl_chips, label,
                (lambda k=key: self.flavor_filter_var.get() == k),
                (lambda k=key: self.flavor_filter_var.set(k)),
            ).pack(side="left", padx=2)

        self._source_vars = {n: tk.BooleanVar(value=True) for n in SOURCE_FILTER_MAP}
        tk.Label(row2, text="SOURCE", bg=C["surface"], fg=C["text_muted"],
                 font=(sans, 8, "bold")).pack(side="left", padx=(0, 8))
        src_chips = tk.Frame(row2, bg=C["surface"])
        src_chips.pack(side="left", padx=(0, 14))
        for name in SOURCE_FILTER_MAP:
            self._make_chip(
                src_chips, name,
                (lambda n=name: self._source_vars[n].get()),
                (lambda n=name: self._source_vars[n].set(
                    not self._source_vars[n].get())),
            ).pack(side="left", padx=2)

        self.cat_var = tk.StringVar(value="All categories")
        ttk.Combobox(row2, textvariable=self.cat_var,
                     values=["All categories"] + get_categories(),
                     state="readonly", font=ctx.font_sm, width=15).pack(
                         side="left", padx=(0, 8), ipady=2)

        self.result_count_var = tk.StringVar(value="")
        tk.Label(row2, textvariable=self.result_count_var, bg=C["surface"],
                 fg=C["text_muted"], font=ctx.font_mono).pack(side="right")

        # ---- List card ----------------------------------------------
        list_wrap = tk.Frame(self.frame, bg=C["surface"],
                             highlightbackground=C["border"], highlightthickness=1)
        list_wrap.pack(fill="both", expand=True, padx=10, pady=(0, 16))
        scroll = tk.Frame(list_wrap, bg=C["bg"])
        scroll.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(scroll, bg=C["bg"], highlightthickness=0,
                                borderwidth=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        HoverScrollbar(scroll, self.canvas)
        self.inner = tk.Frame(self.canvas, bg=C["bg"])
        win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>", lambda e: self.canvas.itemconfig(win, width=e.width))

        # Debounced re-render on text / dropdown changes.
        self.search_var.trace_add("write", self._schedule_render)
        self.cat_var.trace_add("write", self._schedule_render)
        self.sort_var.trace_add("write", self._schedule_render)

    # ------------------------------------------------------------------
    # Chips
    # ------------------------------------------------------------------

    def _make_chip(self, parent, text, is_active_fn, on_click_fn):
        import tkinter as tk

        C = self.ctx.palette
        c = tk.Label(parent, text=text, bg=C["surface"], fg=C["text_dim"],
                     font=(self.ctx.sans_family, 8, "bold"), padx=9, pady=2,
                     cursor="hand2", highlightbackground=C["border"],
                     highlightthickness=1)

        def refresh():
            on = is_active_fn()
            c.configure(
                bg=ACCENT_SOFT if on else C["surface"],
                fg=C["accent"] if on else C["text_dim"],
                highlightbackground=C["accent"] if on else C["border"],
            )

        c._refresh = refresh
        c.bind("<Button-1>",
               lambda e: (on_click_fn(), self._refresh_chips(), self.render()))
        refresh()
        self._chips.append(c)
        return c

    def _refresh_chips(self):
        for c in self._chips:
            with contextlib.suppress(Exception):
                c._refresh()

    def selected_source_set(self) -> set:
        enabled: set = set()
        for name, var in self._source_vars.items():
            if var.get():
                enabled.update(SOURCE_FILTER_MAP[name])
        return enabled

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _schedule_render(self, *_):
        root = self.ctx.root
        if self._render_job[0] is not None:
            with contextlib.suppress(Exception):
                root.after_cancel(self._render_job[0])
        self._render_job[0] = root.after(120, self.render)

    def render(self) -> None:
        import tkinter as tk

        ctx = self.ctx
        C = ctx.palette
        sans = ctx.sans_family

        for w in self.inner.winfo_children():
            w.destroy()

        # Column header
        header = tk.Frame(self.inner, bg=C["surface_hi"])
        header.pack(fill="x")
        hb = tk.Frame(header, bg=C["surface_hi"])
        hb.pack(fill="x", padx=14, pady=8)
        tk.Frame(hb, bg=C["surface_hi"], width=90).pack(side="right")
        tk.Label(hb, text="SOURCE", bg=C["surface_hi"], fg=C["text_muted"],
                 font=(sans, 8, "bold"), width=12, anchor="e").pack(
                     side="right", padx=(0, 14))
        tk.Label(hb, text="VERSION", bg=C["surface_hi"], fg=C["text_muted"],
                 font=(sans, 8, "bold"), width=20, anchor="e").pack(
                     side="right", padx=(0, 14))
        tk.Frame(hb, bg=C["surface_hi"], width=34).pack(side="left")
        tk.Label(hb, text="NAME", bg=C["surface_hi"], fg=C["text_muted"],
                 font=(sans, 8, "bold"), anchor="w").pack(side="left")
        tk.Frame(self.inner, bg=C["border"], height=1).pack(fill="x")

        installed = self._load_installed()
        q = self.search_var.get().lower().strip()
        cat = self.cat_var.get()
        source_allowed = self.selected_source_set()

        current_flavor = self._get_current_flavor()
        fl_key = self.flavor_filter_var.get()
        catalog = self._get_catalog()
        if fl_key == "all":
            base = catalog
        elif fl_key == "auto":
            base = (self._filter_by_flavor(catalog, current_flavor)
                    if current_flavor else catalog)
        else:
            base = self._filter_by_flavor(catalog, fl_key)

        filtered = []
        for a in base:
            if cat != "All categories" and a["category"] != cat:
                continue
            if a.get("source") not in source_allowed:
                continue
            if q:
                h = (f"{a['name']} {a['description']} {a['author']} "
                     f"{a.get('source', '')} {a.get('curseforge_slug', '')}").lower()
                if q not in h:
                    continue
            filtered.append(a)

        sk = self.sort_var.get()
        if sk.startswith(("Name", "Recently")):
            filtered.sort(key=lambda a: a.get("name", "").lower())

        with contextlib.suppress(Exception):
            self.result_count_var.set(f"{len(filtered)} results")

        if not filtered:
            empty = tk.Frame(self.inner, bg=C["bg"])
            empty.pack(expand=True, pady=60)
            tk.Label(empty, text="No addons match these filters", bg=C["bg"],
                     fg=C["text_muted"], font=ctx.font_body).pack()
            if fl_key != "all":
                tk.Label(empty,
                         text="Click the 'All' flavor chip to see the full catalog",
                         bg=C["bg"], fg=C["text_muted"],
                         font=ctx.font_sm).pack(pady=(6, 0))
            return

        for a in filtered:
            self._render_card(self.inner, a, installed.get(a["id"]))
