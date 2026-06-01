"""CurseForgeTab — the CurseForge search pane of the wowusky GUI.

Builds its own frame with a search row, a scrollable results canvas and a
status label.  All network I/O, card rendering, and navigation side effects
are injected as callbacks so the tab carries no threading or install logic.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import Any

from wowusky.gui.widgets import HoverScrollbar


class CurseForgeTab:
    """CurseForge search pane with scrollable mod cards."""

    def __init__(
        self,
        ctx: Any,
        parent: Any,
        *,
        has_cf_api_key: Callable[[], bool],
        run_cf_search: Callable[[str, Callable, Callable], None],
        render_mod_card: Callable[[Any, Any], None],
        cf_search_url: Callable[[str], str],
        goto_import: Callable[[], None],
        import_latest_zip: Callable[[], None],
        open_url: Callable[[str], None],
    ) -> None:
        import tkinter as tk

        self._ctx = ctx
        self._has_cf_api_key = has_cf_api_key
        self._run_cf_search = run_cf_search
        self._render_mod_card = render_mod_card
        self._cf_search_url = cf_search_url
        self._goto_import = goto_import
        self._import_latest_zip = import_latest_zip
        self._open_url = open_url

        C = ctx.palette
        make_button = ctx.make_button

        self.frame = tk.Frame(parent, bg=C["bg"])
        outer = tk.Frame(self.frame, bg=C["bg"])
        outer.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Title ---
        tk.Label(outer, text="CurseForge",
                 bg=C["bg"], fg=C["text"],
                 font=ctx.font_head).pack(anchor="w")
        tk.Label(outer,
                 text="CurseForge API-Suche mit freigeschaltetem Key. Ohne Key: Webseite mit passendem Flavor-Filter öffnen, ZIP laden, danach automatisch die neueste ZIP aus ~/Downloads importieren.",
                 bg=C["bg"], fg=C["text_dim"], font=ctx.font_sm,
                 wraplength=520, justify="left").pack(anchor="w", pady=(3, 8))

        # --- Search row ---
        cf_search_row = tk.Frame(outer, bg=C["surface"])
        cf_search_row.pack(fill="x", pady=(0, 8))

        self.search_var = tk.StringVar()
        tk.Entry(cf_search_row, textvariable=self.search_var,
                 bg=C["surface"], fg=C["text"],
                 insertbackground=C["accent"],
                 font=ctx.font_body, borderwidth=0,
                 highlightthickness=0, relief="flat").pack(
            side="left", fill="x", expand=True, ipady=8, padx=10)

        make_button(cf_search_row, "Search", self.search,
                    variant="primary", compact=True).pack(side="right", padx=5, pady=4)

        # --- Scrollable results area ---
        results_wrap = tk.Frame(outer, bg=C["bg"])
        results_wrap.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(results_wrap, bg=C["bg"],
                                highlightthickness=0, borderwidth=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        HoverScrollbar(results_wrap, self.canvas)

        self._results_frame = tk.Frame(self.canvas, bg=C["bg"])
        cfw = self.canvas.create_window((0, 0), window=self._results_frame, anchor="nw")
        self._results_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(cfw, width=e.width))

        # --- Status label ---
        self.status_var = tk.StringVar(value="")
        tk.Label(outer, textvariable=self.status_var,
                 bg=C["bg"], fg=C["text_dim"], font=ctx.font_xs,
                 anchor="w").pack(fill="x", pady=(6, 0))

        # --- Tip text ---
        tk.Label(outer,
                 text="Tipp: Ohne API-Key öffnet Search die CurseForge-Webseite. ZIP danach im Import-Tab installieren.",
                 bg=C["bg"], fg=C["text_muted"], font=ctx.font_xs,
                 anchor="w", justify="left").pack(fill="x", pady=(6, 0))

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def search(self, initial: bool = False) -> None:
        q = self.search_var.get().strip()
        if not self._has_cf_api_key():
            self._show_fallback()
            return
        self._clear_results()
        self.status_var.set("Searching...")
        self._run_cf_search(q, self._on_results, self._on_error)

    # ------------------------------------------------------------------
    # Private methods
    # ------------------------------------------------------------------

    def _show_fallback(self, reason: str = "") -> None:
        import tkinter as tk

        C = self._ctx.palette
        make_button = self._ctx.make_button

        self._clear_results()
        card = tk.Frame(self._results_frame, bg=C["surface"], padx=12, pady=10)
        card.pack(fill="x", pady=(0, 8))

        tk.Label(card, text="CurseForge API nicht verfuegbar",
                 bg=C["surface"], fg=C["text"],
                 font=self._ctx.font_name, anchor="w").pack(fill="x")

        msg = reason or "Kein freigeschalteter Third-Party/Core API-Key vorhanden."
        tk.Label(card, text=msg, bg=C["surface"], fg=C["text_dim"],
                 font=self._ctx.font_sm, anchor="w", justify="left",
                 wraplength=520).pack(fill="x", pady=(4, 8))

        tk.Label(card,
                 text="Fallback: Addon auf CurseForge im Browser oeffnen, ZIP herunterladen und im Import-Tab installieren.",
                 bg=C["surface"], fg=C["text_muted"], font=self._ctx.font_xs,
                 anchor="w", justify="left", wraplength=520).pack(fill="x", pady=(0, 8))

        row = tk.Frame(card, bg=C["surface"])
        row.pack(fill="x")

        make_button(
            row, "Open CurseForge",
            lambda: self._open_url(self._cf_search_url(self.search_var.get())),
            variant="primary", compact=True).pack(side="left")
        make_button(
            row, "Import Tab", self._goto_import,
            variant="ghost", compact=True).pack(side="left", padx=(6, 0))
        make_button(
            row, "Import latest ZIP", self._import_latest_zip,
            variant="ghost", compact=True).pack(side="left", padx=(6, 0))

        self.status_var.set("Fallback aktiv: Browser + ZIP Import")

    def _on_results(self, results: list) -> None:
        self._clear_results()
        if not results:
            self.status_var.set("Keine CurseForge-Addons gefunden.")
            return
        for mod in results:
            self._render_mod_card(self._results_frame, mod)
        self.status_var.set(f"{len(results)} Ergebnisse")

    def _on_error(self, err_str: str) -> None:
        self._show_fallback(err_str)

    def _clear_results(self) -> None:
        with contextlib.suppress(Exception):
            for w in self._results_frame.winfo_children():
                w.destroy()
