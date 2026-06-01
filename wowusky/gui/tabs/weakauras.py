"""WeakAurasTab — the Wago.io aura-tracking pane of the wowusky GUI.

Builds its own frame (header with action buttons, an add-by-URL row, and a
scrollable card list) and owns :meth:`render`, which repopulates the list
from a ``load_auras`` callback.  Every side effect — generate companion,
check updates, import, add, per-card update / remove / open — is injected as
a callback, so the tab carries no Wago/threading logic itself.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from wowusky.gui.widgets import HoverScrollbar


class WeakAurasTab:
    """Wago.io aura tracker.

    Parameters
    ----------
    ctx:
        Shared :class:`~wowusky.gui.context.AppContext`.
    parent:
        The Tk container the tab frame is created in.
    load_auras:
        Zero-arg callable returning the ``{slug: entry}`` aura mapping.
    on_generate, on_check, on_import:
        No-arg callbacks for the three header buttons.
    on_add:
        No-arg callback for the "Add" button; reads :attr:`url_var`.
    on_update, on_remove:
        Called with ``(slug, entry)`` for a card's Update / Remove buttons.
    open_url:
        Called with a URL string for a card's Open button.
    """

    def __init__(
        self,
        ctx: Any,
        parent: Any,
        *,
        load_auras: Callable[[], dict],
        on_generate: Callable[[], None],
        on_check: Callable[[], None],
        on_import: Callable[[], None],
        on_add: Callable[[], None],
        on_update: Callable[[str, dict], None],
        on_remove: Callable[[str, dict], None],
        open_url: Callable[[str], None],
    ):
        import tkinter as tk

        self.ctx = ctx
        self._load_auras = load_auras
        self._on_update = on_update
        self._on_remove = on_remove
        self._open_url = open_url
        C = ctx.palette
        mk = ctx.make_button

        self.frame = tk.Frame(parent, bg=C["bg"])

        # ---- Header -------------------------------------------------
        header = tk.Frame(self.frame, bg=C["bg"])
        header.pack(fill="x", padx=10, pady=(16, 12))

        title_row = tk.Frame(header, bg=C["bg"])
        title_row.pack(fill="x")
        tk.Label(title_row, text="WeakAuras", bg=C["bg"], fg=C["text"],
                 font=ctx.font_head).pack(side="left")
        tk.Label(title_row, text="  via Wago.io", bg=C["bg"], fg=C["text_muted"],
                 font=ctx.font_sm).pack(side="left")

        mk(title_row, "Generate Companion", on_generate,
           variant="primary").pack(side="right")
        mk(title_row, "Check updates", on_check,
           variant="outline").pack(side="right", padx=(0, 8))
        mk(title_row, "Import existing", on_import,
           variant="outline").pack(side="right", padx=(0, 8))

        tk.Label(
            header,
            text=("Track auras from Wago.io. wowusky generates a "
                  "WeakAurasCompanion addon so updates show up in-game."),
            bg=C["bg"], fg=C["text_dim"], font=ctx.font_sm,
            wraplength=720, justify="left",
        ).pack(anchor="w", pady=(8, 0))

        # ---- Add row ------------------------------------------------
        add_row = tk.Frame(self.frame, bg=C["bg"])
        add_row.pack(fill="x", padx=10, pady=(16, 8))

        input_wrap = tk.Frame(add_row, bg=C["surface"])
        input_wrap.pack(side="left", fill="x", expand=True, padx=(0, 8))
        tk.Label(input_wrap, text="wago.io/", bg=C["surface"], fg=C["text_muted"],
                 font=ctx.font_mono, padx=12).pack(side="left")

        self.url_var = tk.StringVar()
        tk.Entry(input_wrap, textvariable=self.url_var,
                 bg=C["surface"], fg=C["text"], insertbackground=C["accent"],
                 font=ctx.font_body, borderwidth=0, highlightthickness=0,
                 relief="flat").pack(side="left", fill="x", expand=True,
                                     ipady=8, padx=(0, 12))

        mk(add_row, "Add", on_add, variant="primary").pack(side="left")

        # ---- Scrollable card list -----------------------------------
        scroll = tk.Frame(self.frame, bg=C["bg"])
        scroll.pack(fill="both", expand=True, padx=10, pady=(6, 10))
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

    def clear_input(self) -> None:
        """Empty the add-by-URL entry."""
        self.url_var.set("")

    def render(self) -> None:
        """Repopulate the aura list from ``load_auras()``."""
        import tkinter as tk

        C = self.ctx.palette
        for w in self.inner.winfo_children():
            w.destroy()

        auras = self._load_auras()
        if not auras:
            empty = tk.Frame(self.inner, bg=C["bg"])
            empty.pack(expand=True, pady=60)
            tk.Label(empty, text="No auras tracked", bg=C["bg"], fg=C["text"],
                     font=self.ctx.font_body).pack()
            tk.Label(empty, text="Paste a wago.io URL above to start tracking",
                     bg=C["bg"], fg=C["text_muted"],
                     font=self.ctx.font_sm).pack(pady=(6, 0))
            return

        tk.Frame(self.inner, bg=C["border"], height=1).pack(fill="x")
        for slug, entry in sorted(auras.items(),
                                  key=lambda kv: kv[1].get("name", "").lower()):
            self._render_card(slug, entry)

    def _render_card(self, slug: str, entry: dict) -> None:
        import tkinter as tk

        ctx = self.ctx
        C = ctx.palette
        mk = ctx.make_button

        latest_ver = entry.get("latest_version")
        current_ver = entry.get("version", 1)
        has_update = False
        try:
            if latest_ver and int(latest_ver) > int(current_ver):
                has_update = True
        except (ValueError, TypeError):
            pass

        card = tk.Frame(self.inner, bg=C["bg"])
        card.pack(fill="x")

        inner = tk.Frame(card, bg=C["bg"])
        inner.pack(fill="x", pady=14)

        bar_color = C["accent"] if has_update else C["accent_dim"]
        bar = tk.Frame(inner, bg=bar_color, width=3)
        bar.pack(side="left", fill="y", padx=(0, 14))

        text_col = tk.Frame(inner, bg=C["bg"])
        text_col.pack(side="left", fill="both", expand=True)

        title_row = tk.Frame(text_col, bg=C["bg"])
        title_row.pack(anchor="w", fill="x")
        tk.Label(title_row, text=entry.get("name", slug), bg=C["bg"],
                 fg=C["text"], font=ctx.font_name).pack(side="left")

        ver_text = f"  v{current_ver}"
        if has_update:
            ver_text += f"  →  v{latest_ver}"
        tk.Label(title_row, text=ver_text, bg=C["bg"],
                 fg=C["accent"] if has_update else C["accent_dim"],
                 font=ctx.fonts["FONT_VER"]).pack(side="left")

        tk.Label(text_col,
                 text=f"wago.io/{slug}  ·  {entry.get('type', 'WeakAura')}",
                 bg=C["bg"], fg=C["text_muted"], font=ctx.font_xs,
                 anchor="w").pack(anchor="w", pady=(3, 0))

        if entry.get("note"):
            tk.Label(text_col, text=entry["note"][:120], bg=C["bg"],
                     fg=C["text_dim"], font=ctx.font_sm, anchor="w",
                     wraplength=480, justify="left").pack(anchor="w", pady=(6, 0))

        btn_col = tk.Frame(inner, bg=C["bg"])
        btn_col.pack(side="right", padx=(14, 0))

        if has_update:
            mk(btn_col, "Update",
               lambda s=slug, e=entry: self._on_update(s, e),
               variant="primary").pack(side="left", padx=(0, 6))

        url = entry.get("url") or f"https://wago.io/{slug}"
        mk(btn_col, "Open", lambda u=url: self._open_url(u),
           variant="ghost").pack(side="left", padx=(0, 6))
        mk(btn_col, "Remove",
           lambda s=slug, e=entry: self._on_remove(s, e),
           variant="danger").pack(side="left")

        tk.Frame(card, bg=C["border"], height=1).pack(fill="x")
