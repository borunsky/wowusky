"""AddonDetailsDialog — the per-catalog-addon detail modal.

Replaces the historic ``show_addon_details`` closure.  Shows an addon's
metadata, an install button, an optional provider-page link, and an
asynchronously-loaded list of selectable download versions.  All install /
URL / version-lookup side effects are injected as callbacks.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from wowusky.gui.widgets import _safe_grab


class AddonDetailsDialog:
    """Detail modal for a single catalog addon.

    Parameters
    ----------
    ctx:
        Shared :class:`~wowusky.gui.context.AppContext`.
    parent:
        Tk parent the Toplevel is transient to.
    addon:
        The catalog entry dict to display.
    source_label:
        ``{source_key: human_label}`` mapping.
    provider_page_url:
        ``(addon) -> url|None`` for the optional "Open page" button.
    github_version_choices:
        ``(addon) -> list`` of ``{"label", "url"}`` version choices
        (called off the UI thread).
    on_install:
        ``(addon) -> None`` — install the latest version.
    on_install_version:
        ``(addon, url, label) -> None`` — install a specific ZIP version.
    open_url:
        ``(url) -> None``.
    """

    def __init__(
        self,
        ctx: Any,
        parent: Any,
        addon: dict,
        *,
        source_label: dict,
        provider_page_url: Callable[[dict], Any],
        github_version_choices: Callable[[dict], list],
        on_install: Callable[[dict], None],
        on_install_version: Callable[[dict, str, str], None],
        open_url: Callable[[str], None],
    ) -> None:
        import tkinter as tk

        self._ctx = ctx
        self._addon = addon
        self._github_version_choices = github_version_choices
        self._on_install_version = on_install_version

        C = ctx.palette
        root = ctx.root
        make_button = ctx.make_button
        FONT_HEAD = ctx.font_head
        FONT_SM = ctx.font_sm
        FONT_SECTION = ctx.font_section

        dlg = tk.Toplevel(root)
        self.dialog = dlg
        dlg.title(addon.get("name", "Addon"))
        dlg.configure(bg=C["bg"])
        dlg.geometry("560x520")
        dlg.minsize(420, 360)
        dlg.transient(root)
        _safe_grab(dlg)

        head = tk.Frame(dlg, bg=C["bg"])
        head.pack(fill="x", padx=16, pady=(16, 8))
        tk.Label(head, text=addon.get("name", "Addon"), bg=C["bg"],
                 fg=C["text"], font=FONT_HEAD).pack(anchor="w")
        meta = (f"{addon.get('author', '')} · {addon.get('category', '')} · "
                f"{source_label.get(addon.get('source'), addon.get('source', ''))}")
        tk.Label(head, text=meta, bg=C["bg"], fg=C["text_muted"],
                 font=FONT_SM).pack(anchor="w", pady=(4, 0))
        tk.Label(dlg, text=addon.get("description", ""), bg=C["bg"],
                 fg=C["text_dim"], font=FONT_SM, wraplength=500,
                 justify="left").pack(anchor="w", fill="x", padx=16, pady=(0, 14))

        btns = tk.Frame(dlg, bg=C["bg"])
        btns.pack(fill="x", padx=16, pady=(0, 12))
        make_button(btns, "Install latest",
                    lambda a=addon: (dlg.destroy(), on_install(a)),
                    variant="primary").pack(side="left", padx=(0, 8))
        page = provider_page_url(addon)
        if page:
            make_button(btns, "Open page",
                        lambda url=page: open_url(url),
                        variant="outline").pack(side="left", padx=(0, 8))

        tk.Label(dlg, text="Available versions", bg=C["bg"], fg=C["text"],
                 font=FONT_SECTION).pack(anchor="w", padx=16)
        self._list_wrap = tk.Frame(dlg, bg=C["surface"])
        self._list_wrap.pack(fill="both", expand=True, padx=16, pady=(8, 16))
        tk.Label(self._list_wrap, text="Loading version choices…",
                 bg=C["surface"], fg=C["text_muted"], font=FONT_SM).pack(
                     padx=12, pady=12, anchor="w")

        threading.Thread(target=self._fill_versions, daemon=True).start()

    # ------------------------------------------------------------------
    # Async version list
    # ------------------------------------------------------------------

    def _fill_versions(self) -> None:
        import tkinter as tk

        ctx = self._ctx
        C = ctx.palette
        FONT_SM = ctx.font_sm
        addon = self._addon
        list_wrap = self._list_wrap
        dlg = self.dialog

        choices = []
        if addon.get("source") == "github":
            choices = self._github_version_choices(addon)

        def ui():
            for w in list_wrap.winfo_children():
                w.destroy()
            if not choices:
                msg = ("Direct version selection is only available when the "
                       "provider exposes downloadable ZIP versions. For "
                       "CurseForge/WoWInterface use Open page + ZIP import.")
                tk.Label(list_wrap, text=msg, bg=C["surface"], fg=C["text_dim"],
                         font=FONT_SM, wraplength=480, justify="left").pack(
                             anchor="w", padx=12, pady=12)
                return
            for ch in choices:
                row = tk.Frame(list_wrap, bg=C["surface"])
                row.pack(fill="x", padx=8, pady=4)
                tk.Label(row, text=ch["label"], bg=C["surface"], fg=C["text"],
                         font=FONT_SM, anchor="w").pack(
                             side="left", fill="x", expand=True)
                ctx.make_button(
                    row, "Install",
                    lambda c=ch: (dlg.destroy(),
                                  self._on_install_version(addon, c["url"], c["label"])),
                    variant="primary", compact=True).pack(side="right")

        ctx.root.after(0, ui)
