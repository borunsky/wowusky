"""LogTab — the activity-log pane of the wowusky GUI.

The simplest tab: a read-only monospace ScrolledText that install/update
tasks append to via :meth:`LogTab.log_msg`.  It owns no network or install
logic, which makes it the natural blueprint for the remaining tab classes.
"""

from __future__ import annotations

from typing import Any


class LogTab:
    """Read-only activity log.

    Parameters
    ----------
    ctx:
        Shared :class:`~wowusky.gui.context.AppContext`; supplies the palette
        and font-set.
    parent:
        The Tk container the tab frame is created in.
    """

    def __init__(self, ctx: Any, parent: Any):
        import tkinter as tk
        from tkinter import scrolledtext

        self.ctx = ctx
        C = ctx.palette

        self.frame = tk.Frame(parent, bg=C["bg"])

        wrap = tk.Frame(self.frame, bg=C["surface"])
        wrap.pack(fill="both", expand=True, padx=10, pady=10)

        self.box = scrolledtext.ScrolledText(
            wrap, bg=C["surface"], fg=C["text"],
            font=ctx.font_mono, borderwidth=0, highlightthickness=0,
            state="disabled", wrap="word",
            padx=16, pady=16,
            insertbackground=C["accent"],
        )
        self.box.pack(fill="both", expand=True)

    def log_msg(self, msg: str) -> None:
        """Append a line to the log and scroll to the bottom."""
        self.box.configure(state="normal")
        self.box.insert("end", msg + "\n")
        self.box.see("end")
        self.box.configure(state="disabled")
