"""Reusable Tk widgets and GUI helpers for the wowusky GUI."""

from __future__ import annotations


def _safe_grab(dialog, attempts: int = 10) -> None:
    """Attempt grab_set, retrying via after() if the window is not yet ready."""
    try:
        dialog.grab_set()
    except Exception:
        if attempts > 0:
            dialog.after(50, lambda: _safe_grab(dialog, attempts - 1))


def make_button(
    parent,
    text: str,
    command,
    variant: str = "ghost",
    enabled: bool = True,
    compact: bool = False,
    *,
    palette: dict,
    font_sm: tuple,
):
    """Create and return a styled tk.Label that acts as a button."""
    import tkinter as tk

    C = palette
    styles = {
        "primary": (C["accent"],   C["accent_fg"], C["accent_hi"]),
        "ghost":   (C["surface"],  C["text"],      C["surface_hi"]),
        "outline": (C["bg"],       C["text_dim"],  C["surface_hi"]),
        "danger":  (C["surface"],  C["danger"],    C["surface_hi"]),
        "subtle":  (C["bg"],       C["text_dim"],  C["surface"]),
    }
    bg, fg, hover_bg = styles.get(variant, styles["ghost"])

    if not enabled:
        bg = C["bg"]
        fg = C["text_muted"]
        hover_bg = bg

    padx = 12 if compact else 16
    pady = 6 if compact else 8

    btn = tk.Label(
        parent, text=text, bg=bg, fg=fg,
        font=font_sm,
        cursor="hand2" if enabled else "arrow",
        padx=padx, pady=pady, anchor="center",
    )

    if enabled:
        btn.bind("<Enter>", lambda e: btn.configure(bg=hover_bg))
        btn.bind("<Leave>", lambda e: btn.configure(bg=bg))
        btn.bind("<Button-1>", lambda e: command())

    return btn


class UltraHiddenScrollbar:
    """Scrollbar hidden by default; appears only near the right edge."""
    def __init__(self, parent, canvas):
        from tkinter import ttk
        self.parent = parent
        self.canvas = canvas
        self.visible = False
        self.scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=self.scrollbar.set)
        parent.bind("<Motion>", self._on_motion, add="+")
        canvas.bind("<Motion>", self._on_motion, add="+")
        parent.bind("<Leave>", lambda e: self._hide(), add="+")

    def _content_overflows(self):
        try:
            first, last = self.scrollbar.get()
            return not (float(first) <= 0.0 and float(last) >= 1.0)
        except Exception:
            return True

    def _on_motion(self, event):
        if not self._content_overflows():
            self._hide()
            return
        width = self.parent.winfo_width()
        if event.x >= width - 14:
            self._show()
        else:
            self._hide()

    def _show(self):
        if not self.visible:
            self.scrollbar.place(relx=1.0, rely=0, relheight=1.0, anchor="ne")
            self.visible = True

    def _hide(self):
        if self.visible:
            self.scrollbar.place_forget()
            self.visible = False


# Backwards-compatible name for existing call sites.
HoverScrollbar = UltraHiddenScrollbar
