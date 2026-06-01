"""ImportTab — the manual ZIP import pane of the wowusky GUI.

Builds its own frame and owns the ZIP-file picker, name field, and the
CurseForge-ref input.  All side effects (install, path resolution, URL
opening) are injected as callbacks so the tab carries no threading logic.
"""

from __future__ import annotations

import contextlib
import os
import re
from collections.abc import Callable
from typing import Any


class ImportTab:
    """Manual ZIP import pane with an optional CurseForge-ref shortcut."""

    def __init__(
        self,
        ctx: Any,
        parent: Any,
        *,
        newest_download_zip: Callable[[], Any],
        guess_name_from_zip: Callable[[str], str],
        cf_slug_from_ref: Callable[[str], str],
        cf_files_url: Callable[[str], str],
        cf_search_url: Callable[[str], str],
        has_cf_api_key: Callable[[], bool],
        on_install_zip: Callable[[str, str, str], None],
        on_install_cf: Callable[[str], None],
        open_url: Callable[[str], None],
    ) -> None:
        import tkinter as tk
        from tkinter import filedialog, messagebox

        self._ctx = ctx
        self._on_install_zip = on_install_zip
        self._on_install_cf = on_install_cf
        self._newest_download_zip = newest_download_zip
        self._guess_name_from_zip = guess_name_from_zip
        self._cf_slug_from_ref = cf_slug_from_ref
        self._cf_files_url = cf_files_url
        self._cf_search_url = cf_search_url
        self._has_cf_api_key = has_cf_api_key
        self._open_url = open_url

        C = ctx.palette
        make_button = ctx.make_button

        self.frame = tk.Frame(parent, bg=C["bg"])
        inner = tk.Frame(self.frame, bg=C["bg"])
        inner.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Title row ---
        tk.Label(inner, text="Import from ZIP",
                 bg=C["bg"], fg=C["text"],
                 font=ctx.font_head).pack(anchor="w")
        tk.Label(inner,
                 text="For addons not in our catalog (CurseForge, manual downloads, etc.)",
                 bg=C["bg"], fg=C["text_dim"],
                 font=ctx.font_body).pack(anchor="w", pady=(4, 20))

        # --- ZIP file row ---
        tk.Label(inner, text="ZIP file",
                 bg=C["bg"], fg=C["text_muted"],
                 font=ctx.font_sm, anchor="w").pack(fill="x", pady=(0, 6))

        file_row = tk.Frame(inner, bg=C["surface"])
        file_row.pack(fill="x", pady=(0, 16))

        self.file_var = tk.StringVar()
        self.name_var = tk.StringVar()

        tk.Entry(file_row, textvariable=self.file_var,
                 bg=C["surface"], fg=C["text"],
                 insertbackground=C["accent"],
                 font=ctx.font_body, borderwidth=0,
                 highlightthickness=0, relief="flat").pack(
            side="left", fill="x", expand=True, ipady=8, padx=12)

        def pick_zip() -> None:
            path = filedialog.askopenfilename(
                title="Select addon ZIP",
                filetypes=[("ZIP files", "*.zip"), ("All", "*.*")],
                initialdir=os.path.expanduser("~/Downloads"))
            if path:
                self.file_var.set(path)
                if not self.name_var.get():
                    guess = os.path.splitext(os.path.basename(path))[0]
                    guess = re.sub(r'[-_]?\d+(\.\d+)*.*$', '', guess)
                    self.name_var.set(guess)

        make_button(file_row, "Browse…", pick_zip, variant="ghost").pack(
            side="right", padx=6, pady=4)

        def use_latest() -> None:
            path = self._newest_download_zip()
            if not path:
                messagebox.showinfo("Downloads", "Keine ZIP-Datei im Downloads-Ordner gefunden.")
                return
            self.file_var.set(path)
            self.name_var.set(self._guess_name_from_zip(path))

        make_button(file_row, "Latest", use_latest, variant="ghost").pack(
            side="right", padx=(0, 2), pady=4)

        # --- Name row ---
        tk.Label(inner, text="Name",
                 bg=C["bg"], fg=C["text_muted"],
                 font=ctx.font_sm, anchor="w").pack(fill="x", pady=(0, 6))

        name_row = tk.Frame(inner, bg=C["surface"])
        name_row.pack(fill="x", pady=(0, 20))

        tk.Entry(name_row, textvariable=self.name_var,
                 bg=C["surface"], fg=C["text"],
                 insertbackground=C["accent"],
                 font=ctx.font_body, borderwidth=0,
                 highlightthickness=0, relief="flat").pack(
            fill="x", ipady=8, padx=12)

        # --- Button row ---
        btn_row = tk.Frame(inner, bg=C["bg"])
        btn_row.pack(anchor="w", fill="x")

        make_button(btn_row, "Import selected ZIP", self._install,
                    variant="primary").pack(side="left")
        make_button(btn_row, "Import latest from Downloads", self._import_latest,
                    variant="ghost").pack(side="left", padx=(8, 0))

        # --- Separator ---
        tk.Frame(inner, bg=C["border"], height=1).pack(fill="x", pady=(28, 16))

        # --- CurseForge section ---
        tk.Label(inner, text="CurseForge",
                 bg=C["bg"], fg=C["text"],
                 font=ctx.font_body).pack(anchor="w", pady=(0, 4))
        tk.Label(inner,
                 text='Ohne freigeschalteten API-Key öffnet wowusky die CurseForge-Seite im Browser. Lade dort die ZIP herunter und klicke danach auf "Import latest from Downloads".',
                 bg=C["bg"], fg=C["text_dim"],
                 font=ctx.font_sm, justify="left", wraplength=520).pack(anchor="w", pady=(0, 10))

        cf_row = tk.Frame(inner, bg=C["surface"])
        cf_row.pack(fill="x", pady=(0, 12))

        self.cf_ref_var = tk.StringVar()
        tk.Entry(cf_row, textvariable=self.cf_ref_var,
                 bg=C["surface"], fg=C["text"],
                 insertbackground=C["accent"],
                 font=ctx.font_body, borderwidth=0,
                 highlightthickness=0, relief="flat").pack(
            side="left", fill="x", expand=True, ipady=8, padx=12)

        def install_cf() -> None:
            ref = self.cf_ref_var.get().strip()
            if not ref:
                messagebox.showerror("Error", "Paste a CurseForge URL, slug, or project id.")
                return
            self._on_install_cf(ref)

        def open_cf() -> None:
            ref = self.cf_ref_var.get().strip()
            url = self._cf_files_url(ref) if self._cf_slug_from_ref(ref) else self._cf_search_url(ref)
            self._open_url(url)

        make_button(cf_row, "Install", install_cf, variant="primary").pack(
            side="right", padx=6, pady=4)
        make_button(cf_row, "Open", open_cf, variant="ghost").pack(
            side="right", padx=(0, 2), pady=4)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def clear(self) -> None:
        with contextlib.suppress(Exception):
            self.file_var.set("")
            self.name_var.set("")

    # ------------------------------------------------------------------
    # Private methods
    # ------------------------------------------------------------------

    def _install(self) -> None:
        import tkinter.messagebox as messagebox

        zp = self.file_var.get().strip()
        name = self.name_var.get().strip()
        if not zp or not os.path.isfile(zp):
            messagebox.showerror("Error", "Please select a valid ZIP file.")
            return
        if not name:
            messagebox.showerror("Error", "Please enter a name.")
            return
        self._on_install_zip(zp, name, self.cf_ref_var.get())

    def _import_latest(self) -> None:
        import tkinter.messagebox as messagebox

        path = self._newest_download_zip()
        if not path:
            messagebox.showinfo("Downloads", "Keine ZIP-Datei im Downloads-Ordner gefunden.")
            return
        self.file_var.set(path)
        self.name_var.set(self._guess_name_from_zip(path))
        self._install()
