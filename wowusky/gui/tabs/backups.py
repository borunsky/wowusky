"""BackupsTab — the full-backup management pane of the wowusky GUI.

Builds its own frame (header, Create/Refresh buttons, scrollable list) and
owns :meth:`render`, which repopulates the list from a ``list_backups``
callback.  All side-effecting actions (create, restore, open folder) are
injected as callbacks so the tab carries no install/threading logic itself.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

from wowusky.gui.widgets import HoverScrollbar


class BackupsTab:
    """Full-backup list with create / restore / open-folder actions.

    Parameters
    ----------
    ctx:
        Shared :class:`~wowusky.gui.context.AppContext` — supplies palette,
        fonts and the ``make_button`` factory.
    parent:
        The Tk container the tab frame is created in.
    list_backups:
        Zero-arg callable returning a list of dicts with ``path``, ``name``,
        ``mtime`` and ``size`` keys (newest first).
    on_create:
        Called with no args when "Create full backup" is clicked.
    on_restore:
        Called with a backup ``path`` when "Restore" is clicked.
    open_folder:
        Called with a directory path when "Open folder" is clicked.
    """

    def __init__(
        self,
        ctx: Any,
        parent: Any,
        *,
        list_backups: Callable[[], list],
        on_create: Callable[[], None],
        on_restore: Callable[[str], None],
        open_folder: Callable[[str], None],
    ):
        import tkinter as tk

        self.ctx = ctx
        self._list_backups = list_backups
        self._on_restore = on_restore
        self._open_folder = open_folder
        C = ctx.palette
        mk = ctx.make_button

        self.frame = tk.Frame(parent, bg=C["bg"])

        top = tk.Frame(self.frame, bg=C["bg"])
        top.pack(fill="x", padx=10, pady=(16, 12))
        tk.Label(top, text="Backups", bg=C["bg"], fg=C["text"],
                 font=ctx.font_head).pack(side="left")
        mk(top, "Create full backup", on_create, variant="primary").pack(side="right")
        mk(top, "Refresh", self.render, variant="outline").pack(side="right", padx=(0, 8))

        tk.Label(
            self.frame,
            text=("Full backups include Interface/AddOns and WTF settings for "
                  "the active profile. Addon-specific backups are created "
                  "automatically before install/remove and can be restored per "
                  "addon in Installed."),
            bg=C["bg"], fg=C["text_dim"], font=ctx.font_sm,
            wraplength=720, justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 8))

        scroll = tk.Frame(self.frame, bg=C["bg"])
        scroll.pack(fill="both", expand=True, padx=10, pady=(0, 16))
        self.canvas = tk.Canvas(scroll, bg=C["bg"], highlightthickness=0, borderwidth=0)
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

    def render(self) -> None:
        """Repopulate the backup list from ``list_backups()``."""
        import tkinter as tk

        ctx = self.ctx
        C = ctx.palette
        mk = ctx.make_button

        for w in self.inner.winfo_children():
            w.destroy()

        items = self._list_backups()
        if not items:
            tk.Label(self.inner, text="No full backups yet",
                     bg=C["bg"], fg=C["text_muted"], font=ctx.font_body).pack(
                         anchor="w", pady=40)
            return

        tk.Frame(self.inner, bg=C["border"], height=1).pack(fill="x")
        for item in items:
            row = tk.Frame(self.inner, bg=C["bg"])
            row.pack(fill="x", pady=12)
            txt = tk.Frame(row, bg=C["bg"])
            txt.pack(side="left", fill="x", expand=True)
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(item["mtime"]))
            size = f"{item['size'] / (1024 * 1024):.1f} MB"
            tk.Label(txt, text=item["name"], bg=C["bg"], fg=C["text"],
                     font=ctx.font_name).pack(anchor="w")
            tk.Label(txt, text=f"{when} · {size}", bg=C["bg"], fg=C["text_muted"],
                     font=ctx.font_xs).pack(anchor="w", pady=(3, 0))
            actions = tk.Frame(row, bg=C["bg"])
            actions.pack(side="right")
            mk(actions, "Restore",
               lambda p=item["path"]: self._on_restore(p),
               variant="primary").pack(side="left", padx=(0, 6))
            mk(actions, "Open folder",
               lambda p=item["path"]: self._open_folder(os.path.dirname(p)),
               variant="ghost").pack(side="left")
            tk.Frame(self.inner, bg=C["border"], height=1).pack(fill="x")
