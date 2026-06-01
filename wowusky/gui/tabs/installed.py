"""InstalledTab — the installed-addon manager pane of the wowusky GUI.

Builds its own frame (header with a source-filter menu + action buttons, and
a scrollable card list) and owns :meth:`render`.  The source filter is pure
UI state owned by the tab; every side effect (rescan, check updates, update,
rollback, remove, open manager / URL) and every data lookup (catalog match,
latest version, backup presence, CurseForge-manual info) is injected as a
callback, so the tab carries no install/threading logic itself.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from wowusky.gui.widgets import HoverScrollbar

_SOURCE_LABELS = {
    "tukui": "Tukui", "github": "GitHub", "wowi": "WoWInterface",
    "curseforge": "CurseForge API", "curseforge_web": "CurseForge Web",
    "curseforge_manual": "CurseForge ZIP", "manual": "Manual",
    "external": "Local", "internal_wac": "wowusky",
}


class InstalledTab:
    """Installed-addon list with a source filter and per-card actions.

    Parameters
    ----------
    ctx:
        Shared :class:`~wowusky.gui.context.AppContext`.
    parent:
        The Tk container the tab frame is created in.
    load_installed:
        Zero-arg callable returning the ``{addon_id: entry}`` installed map.
    find_catalog:
        ``addon_id -> catalog entry | None``.
    get_latest:
        ``addon_id -> latest version string | None`` (e.g. a version cache).
    versions_equal:
        ``(a, b) -> bool`` version comparison.
    has_backup:
        ``addon_id -> truthy`` if a rollback backup exists.
    cf_manual_latest, cf_manual_url:
        ``entry -> str | None`` / ``entry -> str`` for CurseForge-manual rows.
    source_label:
        Mapping of source key to display label (used in card metadata).
    on_rescan, on_check_updates, on_check_all_profiles:
        No-arg header-button callbacks.
    on_open_manager:
        ``(addon_id, entry) -> None`` — opens the per-addon manager dialog.
    on_update:
        ``catalog_entry -> None`` — installs/updates from the catalog match.
    on_rollback, on_remove:
        ``(addon_id, entry) -> None``.
    open_url:
        ``url -> None``.
    """

    def __init__(
        self,
        ctx: Any,
        parent: Any,
        *,
        load_installed: Callable[[], dict],
        find_catalog: Callable[[str], Any],
        get_latest: Callable[[str], Any],
        versions_equal: Callable[[Any, Any], bool],
        has_backup: Callable[[str], Any],
        cf_manual_latest: Callable[[dict], Any],
        cf_manual_url: Callable[[dict], str],
        source_label: dict,
        on_rescan: Callable[[], None],
        on_check_updates: Callable[[], None],
        on_check_all_profiles: Callable[[], None],
        on_open_manager: Callable[[str, dict], None],
        on_update: Callable[[Any], None],
        on_rollback: Callable[[str, dict], None],
        on_remove: Callable[[str, dict], None],
        open_url: Callable[[str], None],
    ):
        import tkinter as tk

        self.ctx = ctx
        self._load_installed = load_installed
        self._find_catalog = find_catalog
        self._get_latest = get_latest
        self._versions_equal = versions_equal
        self._has_backup = has_backup
        self._cf_manual_latest = cf_manual_latest
        self._cf_manual_url = cf_manual_url
        self._source_label = source_label
        self._on_open_manager = on_open_manager
        self._on_update = on_update
        self._on_rollback = on_rollback
        self._on_remove = on_remove
        self._open_url = open_url
        C = ctx.palette
        mk = ctx.make_button

        self.frame = tk.Frame(parent, bg=C["bg"])

        top = tk.Frame(self.frame, bg=C["bg"])
        top.pack(fill="x", padx=10, pady=(16, 12))

        self.count_var = tk.StringVar(value="Installed")
        tk.Label(top, textvariable=self.count_var, bg=C["bg"], fg=C["text"],
                 font=ctx.font_head).pack(side="left")

        # ---- Source filter menu (UI state owned by the tab) ---------
        self._source_vars = {k: tk.BooleanVar(value=True) for k in _SOURCE_LABELS}
        self._source_btn_text = tk.StringVar(value="Sources: all")
        menu = tk.Menu(ctx.root, tearoff=0)
        for key, label in _SOURCE_LABELS.items():
            menu.add_checkbutton(label=label, variable=self._source_vars[key],
                                 command=self._on_source_change)
        menu.add_separator()
        menu.add_command(label="Select all",
                         command=lambda: self._set_all_sources(True))
        menu.add_command(label="Select none",
                         command=lambda: self._set_all_sources(False))

        btn = tk.Label(top, textvariable=self._source_btn_text, bg=C["surface"],
                       fg=C["text"], font=ctx.font_sm, padx=12, pady=7,
                       cursor="hand2")
        btn.pack(side="left", padx=(12, 0))
        btn.bind("<Button-1>", lambda e: menu.tk_popup(e.x_root, e.y_root))

        mk(top, "Rescan", on_rescan, variant="outline").pack(side="right", padx=(8, 0))
        mk(top, "Check all profiles", on_check_all_profiles,
           variant="ghost").pack(side="right", padx=(8, 0))
        mk(top, "Check updates", on_check_updates,
           variant="primary").pack(side="right")

        scroll = tk.Frame(self.frame, bg=C["bg"])
        scroll.pack(fill="both", expand=True, padx=10, pady=(0, 16))
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

    # ------------------------------------------------------------------
    # Source-filter state
    # ------------------------------------------------------------------

    def selected_sources(self) -> set:
        return {k for k, v in self._source_vars.items() if v.get()}

    def _set_all_sources(self, value: bool) -> None:
        for v in self._source_vars.values():
            v.set(value)
        self._on_source_change()

    def _on_source_change(self) -> None:
        selected = self.selected_sources()
        if len(selected) == len(self._source_vars):
            self._source_btn_text.set("Sources: all")
        elif not selected:
            self._source_btn_text.set("Sources: none")
        else:
            names = [_SOURCE_LABELS[k] for k in _SOURCE_LABELS if k in selected]
            extra = f" +{len(names) - 2}" if len(names) > 2 else ""
            self._source_btn_text.set("Sources: " + ", ".join(names[:2]) + extra)
        self.render()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self) -> None:
        import tkinter as tk

        C = self.ctx.palette
        for w in self.inner.winfo_children():
            w.destroy()

        installed_all = self._load_installed()
        selected = self.selected_sources()
        installed = {
            aid: e for aid, e in installed_all.items()
            if e.get("source", "external") in selected
        }
        self.count_var.set(f"Installed  ({len(installed)}/{len(installed_all)})")

        if not installed:
            empty = tk.Frame(self.inner, bg=C["bg"])
            empty.pack(expand=True, pady=80)
            tk.Label(empty, text="No addons installed", bg=C["bg"],
                     fg=C["text"], font=self.ctx.font_body).pack()
            tk.Label(empty, text="Install from Browse, or import a ZIP",
                     bg=C["bg"], fg=C["text_muted"],
                     font=self.ctx.font_sm).pack(pady=(6, 0))
            return

        tk.Frame(self.inner, bg=C["border"], height=1).pack(fill="x")
        sorted_items = sorted(
            installed.items(),
            key=lambda kv: (self._find_catalog(kv[0]) is None,
                            kv[1]["name"].lower()),
        )
        for aid, entry in sorted_items:
            self._render_card(aid, entry)

    def _render_card(self, addon_id: str, entry: dict) -> None:
        import tkinter as tk

        ctx = self.ctx
        C = ctx.palette
        mk = ctx.make_button

        catalog = self._find_catalog(addon_id)
        latest = self._get_latest(addon_id) if catalog else None
        installed_version = entry["version"]
        has_update = bool(
            catalog and latest and latest != "?"
            and not self._versions_equal(installed_version, latest)
        )

        card = tk.Frame(self.inner, bg=C["bg"])
        card.pack(fill="x")
        inner = tk.Frame(card, bg=C["bg"])
        inner.pack(fill="x", pady=14)

        if has_update:
            bar_color = C["accent"]
        elif catalog and latest:
            bar_color = C["accent_dim"]
        else:
            bar_color = C["border"]
        tk.Frame(inner, bg=bar_color, width=3).pack(side="left", fill="y",
                                                    padx=(0, 14))

        text_col = tk.Frame(inner, bg=C["bg"])
        text_col.pack(side="left", fill="both", expand=True)

        title_row = tk.Frame(text_col, bg=C["bg"])
        title_row.pack(anchor="w", fill="x")
        name_lbl = tk.Label(title_row, text=entry["name"], bg=C["bg"],
                            fg=C["text"], font=ctx.font_name, cursor="hand2")
        name_lbl.pack(side="left")
        name_lbl.bind(
            "<Button-1>",
            lambda e, aid=addon_id, ent=entry: self._on_open_manager(aid, ent),
        )

        ver_text = f"  {installed_version}"
        if has_update:
            ver_text += f"  →  {latest}"
        ver_color = (C["accent"] if has_update
                     else (C["accent_dim"] if (catalog and latest)
                           else C["text_muted"]))
        tk.Label(title_row, text=ver_text, bg=C["bg"], fg=ver_color,
                 font=ctx.fonts["FONT_VER"]).pack(side="left")

        src = entry.get("source", "external")
        iface = entry.get("interface", "")
        iface_text = f" · interface {iface}" if iface else ""
        hash_text = (f" · sha256 {entry.get('sha256', '')[:8]}"
                     if entry.get("sha256") else "")
        meta = (f"{self._source_label.get(src, src)} · "
                f"{len(entry['folders'])} folder(s){iface_text}{hash_text}")
        tk.Label(text_col, text=meta, bg=C["bg"], fg=C["text_muted"],
                 font=ctx.font_xs, anchor="w").pack(anchor="w", pady=(3, 6))

        folders_text = ", ".join(entry["folders"][:5])
        if len(entry["folders"]) > 5:
            folders_text += f"  +{len(entry['folders']) - 5} more"
        if len(folders_text) > 90:
            folders_text = folders_text[:87] + "…"
        tk.Label(text_col, text=folders_text, bg=C["bg"], fg=C["text_dim"],
                 font=ctx.font_sm, anchor="w").pack(anchor="w")

        btn_col = tk.Frame(inner, bg=C["bg"])
        btn_col.pack(side="right", padx=(14, 0))

        if src == "curseforge_manual":
            cf_latest = self._cf_manual_latest(entry)
            cf_url = self._cf_manual_url(entry)
            if cf_latest and not self._versions_equal(cf_latest, installed_version):
                mk(btn_col, "Open update", lambda url=cf_url: self._open_url(url),
                   variant="primary").pack(side="left", padx=(0, 6))
            else:
                mk(btn_col, "Check on CF", lambda url=cf_url: self._open_url(url),
                   variant="ghost").pack(side="left", padx=(0, 6))
        elif catalog:
            if has_update:
                mk(btn_col, "Update", lambda a=catalog: self._on_update(a),
                   variant="primary").pack(side="left", padx=(0, 6))
            elif latest is None:
                mk(btn_col, "…", lambda: None, variant="outline",
                   enabled=False).pack(side="left", padx=(0, 6))
            else:
                mk(btn_col, "Current", lambda: None, variant="outline",
                   enabled=False).pack(side="left", padx=(0, 6))

        mk(btn_col, "Manager",
           lambda aid=addon_id, ent=entry: self._on_open_manager(aid, ent),
           variant="ghost").pack(side="left", padx=(0, 6))

        if self._has_backup(addon_id):
            mk(btn_col, "Rollback",
               lambda aid=addon_id, ent=entry: self._on_rollback(aid, ent),
               variant="ghost").pack(side="left", padx=(0, 6))

        mk(btn_col, "Remove",
           lambda aid=addon_id, ent=entry: self._on_remove(aid, ent),
           variant="danger").pack(side="left")

        tk.Frame(card, bg=C["border"], height=1).pack(fill="x")
