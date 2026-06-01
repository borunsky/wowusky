"""Reusable Tk widgets for the wowusky GUI."""

from __future__ import annotations


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
