"""SettingsDialog — the WoW-path / settings modal of the wowusky GUI.

Replaces the historic ``show_path_picker`` closure.  The dialog builds its
own Toplevel and owns the detected-installations list, profile name, path,
CurseForge API key, dry-run toggle, theme buttons and the reset action.
All config / profile / provider side effects are injected as callbacks, so
the dialog carries no persistence or scanning logic of its own.
"""

from __future__ import annotations

import contextlib
import os
import threading
from collections.abc import Callable
from typing import Any

from wowusky.gui.theme import set_theme_mode
from wowusky.gui.widgets import _safe_grab


class SettingsDialog:
    """First-run / settings modal.

    Parameters
    ----------
    ctx:
        Shared :class:`~wowusky.gui.context.AppContext` (palette + fonts).
    parent:
        Tk parent the Toplevel is transient to.
    first_run:
        When true the dialog is titled "Connect WoW installation" and omits
        the Cancel button.
    on_done:
        Zero-arg callback fired after a successful save / reset.
    get_active_profile / get_addons_path / is_dry_run / get_cf_api_key /
    get_theme:
        Zero-arg state getters.
    scan_installations:
        ``() -> list`` of detected installs (each a dict with
        ``flavor_name`` and ``addons_path``).
    add_or_update_profile:
        ``(name, path) -> None``.
    set_addons_path / set_dry_run / set_cf_api_key:
        Single-value setters.
    reset_manager_state:
        ``() -> Any`` — wipes wowusky's own state, returns what was removed.
    diagnose_cf_api:
        ``() -> (ok: bool, msg: str)`` — tests the CurseForge API key.
    """

    def __init__(
        self,
        ctx: Any,
        parent: Any,
        *,
        first_run: bool = False,
        on_done: Callable[[], None],
        get_active_profile: Callable[[], dict],
        get_addons_path: Callable[[], Any],
        is_dry_run: Callable[[], bool],
        get_cf_api_key: Callable[[], str],
        get_theme: Callable[[], str],
        scan_installations: Callable[[], list],
        add_or_update_profile: Callable[[str, str], None],
        set_addons_path: Callable[[str], None],
        set_dry_run: Callable[[bool], None],
        set_cf_api_key: Callable[[str], None],
        reset_manager_state: Callable[[], Any],
        diagnose_cf_api: Callable[[], tuple],
    ) -> None:
        import tkinter as tk
        from tkinter import filedialog, messagebox

        self._on_done = on_done
        self._scan_installations = scan_installations
        self._reset_manager_state = reset_manager_state
        self._diagnose_cf_api = diagnose_cf_api

        C = ctx.palette
        FONT_BODY = ctx.font_body
        FONT_SM = ctx.font_sm
        FONT_XS = ctx.font_xs
        FONT_HEAD = ctx.font_head

        dialog = tk.Toplevel(parent)
        self.dialog = dialog
        dialog.title("Settings")
        dialog.geometry("620x620")
        dialog.minsize(420, 420)
        dialog.resizable(True, True)
        dialog.configure(bg=C["bg"])
        dialog.transient(parent)
        dialog.after(60, lambda: _safe_grab(dialog))

        dialog.option_add("*background", C["bg"])
        dialog.option_add("*foreground", C["text"])
        dialog.option_add("*Entry.background", C["input_bg"])
        dialog.option_add("*Entry.foreground", C["input_fg"])
        dialog.option_add("*Entry.insertBackground", C["accent"])
        dialog.option_add("*Entry.selectBackground", C["accent"])
        dialog.option_add("*Entry.selectForeground", C["accent_fg"])

        body = tk.Frame(dialog, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=28, pady=24)

        title = "Connect WoW installation" if first_run else "Settings"
        tk.Label(body, text=title, bg=C["bg"], fg=C["text"],
                 font=FONT_HEAD).pack(anchor="w")

        tk.Label(body, text="Detected installations on your system",
                 bg=C["bg"], fg=C["text_dim"],
                 font=FONT_SM).pack(anchor="w", pady=(4, 16))

        list_frame = tk.Frame(body, bg=C["surface"])
        list_frame.pack(fill="both", expand=True, pady=(0, 16))

        list_canvas = tk.Canvas(list_frame, bg=C["surface"],
                                highlightthickness=0, borderwidth=0)
        list_canvas.pack(side="left", fill="both", expand=True)

        list_inner = tk.Frame(list_canvas, bg=C["surface"])
        lcw = list_canvas.create_window((0, 0), window=list_inner, anchor="nw")
        list_inner.bind(
            "<Configure>",
            lambda e: list_canvas.configure(scrollregion=list_canvas.bbox("all")))
        list_canvas.bind(
            "<Configure>", lambda e: list_canvas.itemconfig(lcw, width=e.width))

        active_prof = get_active_profile()
        profile_name_var = tk.StringVar(value=active_prof.get("name", "Default"))
        manual_var = tk.StringVar(value=get_addons_path() or "")
        dry_run_var = tk.BooleanVar(value=is_dry_run())

        tk.Label(body, text="Profile name", bg=C["bg"], fg=C["text_muted"],
                 font=FONT_SM, anchor="w").pack(fill="x", pady=(0, 6))
        profile_row = tk.Frame(body, bg=C["surface"])
        profile_row.pack(fill="x", pady=(0, 12))
        tk.Entry(profile_row, textvariable=profile_name_var,
                 bg=C["surface"], fg=C["text"], insertbackground=C["accent"],
                 font=FONT_BODY, borderwidth=0, highlightthickness=0,
                 relief="flat").pack(fill="x", ipady=9, padx=12)

        tk.Label(body, text="Path", bg=C["bg"], fg=C["text_muted"],
                 font=FONT_SM, anchor="w").pack(fill="x", pady=(0, 6))

        path_row = tk.Frame(body, bg=C["surface"])
        path_row.pack(fill="x", pady=(0, 16))

        tk.Entry(path_row, textvariable=manual_var,
                 bg=C["surface"], fg=C["text"], insertbackground=C["accent"],
                 font=FONT_BODY, borderwidth=0, highlightthickness=0,
                 relief="flat").pack(
                     side="left", fill="x", expand=True, ipady=9, padx=12)

        def browse_manual():
            path = filedialog.askdirectory(
                title="Select AddOns folder",
                initialdir=os.path.expanduser("~"))
            if path:
                manual_var.set(path)

        browse_btn = tk.Label(path_row, text="Browse", bg=C["surface"],
                              fg=C["text_dim"], font=FONT_SM, cursor="hand2",
                              padx=14, pady=7)
        browse_btn.pack(side="right", padx=6, pady=4)
        browse_btn.bind("<Enter>",
                        lambda e: browse_btn.configure(bg=C["surface_hi"], fg=C["text"]))
        browse_btn.bind("<Leave>",
                        lambda e: browse_btn.configure(bg=C["surface"], fg=C["text_dim"]))
        browse_btn.bind("<Button-1>", lambda e: browse_manual())

        tk.Label(body, text="CurseForge API key", bg=C["bg"], fg=C["text_muted"],
                 font=FONT_SM, anchor="w").pack(fill="x", pady=(0, 6))

        cf_key_var = tk.StringVar(value=get_cf_api_key())
        cf_key_row = tk.Frame(body, bg=C["surface"])
        cf_key_row.pack(fill="x", pady=(0, 6))
        tk.Entry(cf_key_row, textvariable=cf_key_var, show="•",
                 bg=C["surface"], fg=C["text"], insertbackground=C["accent"],
                 font=FONT_BODY, borderwidth=0, highlightthickness=0,
                 relief="flat").pack(fill="x", ipady=9, padx=12)
        tk.Label(body,
                 text="Required only for direct CurseForge API installs. Without a valid Third-Party/Core API key, use Open on CurseForge + ZIP Import.",
                 bg=C["bg"], fg=C["text_dim"], font=FONT_XS, anchor="w",
                 wraplength=520, justify="left").pack(fill="x", pady=(0, 8))

        cf_diag_var = tk.StringVar(value="")
        cf_diag_row = tk.Frame(body, bg=C["bg"])
        cf_diag_row.pack(fill="x", pady=(0, 12))

        def test_cf_key():
            set_cf_api_key(cf_key_var.get())
            cf_diag_var.set("Testing CurseForge API key...")

            def task():
                ok, msg = self._diagnose_cf_api()
                prefix = "OK: " if ok else "Fehler: "
                dialog.after(0, lambda msg=msg, prefix=prefix: cf_diag_var.set(prefix + msg))

            threading.Thread(target=task, daemon=True).start()

        test_btn = tk.Label(cf_diag_row, text="Test API key", bg=C["surface"],
                            fg=C["text_dim"], font=FONT_SM, cursor="hand2",
                            padx=12, pady=6)
        test_btn.pack(side="left")
        test_btn.bind("<Enter>",
                      lambda e: test_btn.configure(bg=C["surface_hi"], fg=C["text"]))
        test_btn.bind("<Leave>",
                      lambda e: test_btn.configure(bg=C["surface"], fg=C["text_dim"]))
        test_btn.bind("<Button-1>", lambda e: test_cf_key())
        tk.Label(cf_diag_row, textvariable=cf_diag_var, bg=C["bg"],
                 fg=C["text_dim"], font=FONT_XS, anchor="w", justify="left",
                 wraplength=420).pack(side="left", fill="x", expand=True, padx=(10, 0))

        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", pady=(8, 14))

        dry_row = tk.Frame(body, bg=C["bg"])
        dry_row.pack(fill="x", pady=(0, 12))
        tk.Checkbutton(dry_row,
                       text="Dry-run mode (log actions, do not change files)",
                       variable=dry_run_var, bg=C["bg"], fg=C["text_dim"],
                       selectcolor=C["surface"], activebackground=C["bg"],
                       activeforeground=C["text"], font=FONT_SM,
                       anchor="w").pack(anchor="w")

        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", pady=(8, 14))

        tk.Label(body, text="Testing", bg=C["bg"], fg=C["text_muted"],
                 font=FONT_SM, anchor="w").pack(fill="x", pady=(0, 8))

        reset_row = tk.Frame(body, bg=C["bg"])
        reset_row.pack(fill="x", pady=(0, 12))

        def do_reset_manager_state():
            warning = (
                "This resets only wowusky's own memory:\n\n"
                "• profiles and selected paths\n"
                "• installed-state database\n"
                "• tracked WeakAura/Wago list inside wowusky\n"
                "• manager backups, logs and temporary cache\n\n"
                "It does NOT delete your actual WoW AddOns, WTF settings, "
                "WeakAuras SavedVariables, or ZIP downloads.\n\n"
                "Reset wowusky now?"
            )
            if not messagebox.askyesno("Reset wowusky", warning, parent=dialog):
                return
            self._reset_manager_state()
            messagebox.showinfo(
                "Reset complete",
                "wowusky was reset to its first-start state.\n\n"
                "Close and start wowusky again, or choose a WoW path now.",
                parent=dialog,
            )
            manual_var.set("")
            profile_name_var.set("Default")
            cf_key_var.set("")
            dry_run_var.set(False)
            self._render_list()
            with contextlib.suppress(Exception):
                self._on_done()

        reset_btn = tk.Label(reset_row, text="Reset wowusky state",
                             bg=C["surface"], fg=C["danger"], font=FONT_SM,
                             cursor="hand2", padx=12, pady=7)
        reset_btn.pack(side="left")
        reset_btn.bind("<Enter>", lambda e: reset_btn.configure(bg=C["surface_hi"]))
        reset_btn.bind("<Leave>", lambda e: reset_btn.configure(bg=C["surface"]))
        reset_btn.bind("<Button-1>", lambda e: do_reset_manager_state())

        tk.Label(reset_row,
                 text="For testing only. Does not remove real AddOns or WTF settings.",
                 bg=C["bg"], fg=C["text_dim"], font=FONT_XS, anchor="w",
                 justify="left", wraplength=380).pack(
                     side="left", fill="x", expand=True, padx=(10, 0))

        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", pady=(8, 14))

        tk.Label(body, text="Appearance", bg=C["bg"], fg=C["text_muted"],
                 font=FONT_SM, anchor="w").pack(fill="x", pady=(0, 8))

        theme_row = tk.Frame(body, bg=C["bg"])
        theme_row.pack(fill="x", pady=(0, 20))

        current_theme = get_theme()

        def make_theme_btn(parent_, key, label):
            is_active = current_theme == key
            bg = C["surface_hi"] if is_active else C["surface"]
            fg = C["accent"] if is_active else C["text_dim"]
            btn = tk.Label(parent_, text=label, bg=bg, fg=fg, font=FONT_SM,
                           cursor="hand2", padx=18, pady=8)
            btn.pack(side="left", padx=(0, 6))

            def on_click(e=None):
                set_theme_mode(key)
                messagebox.showinfo("Theme", "Restart wowusky to apply.")

            def on_enter(e):
                if current_theme != key:
                    btn.configure(bg=C["surface_hi"], fg=C["text"])

            def on_leave(e):
                if current_theme != key:
                    btn.configure(bg=C["surface"], fg=C["text_dim"])

            btn.bind("<Button-1>", on_click)
            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)
            return btn

        make_theme_btn(theme_row, "auto", "Auto")
        make_theme_btn(theme_row, "light", "Light")
        make_theme_btn(theme_row, "dark", "Dark")

        btn_row = tk.Frame(body, bg=C["bg"])
        btn_row.pack(fill="x")

        def save_and_close():
            p = manual_var.get().strip()
            if not p:
                messagebox.showerror("Error", "Select or enter a path")
                return
            if not os.path.isdir(p):
                if not messagebox.askyesno(
                    "Path missing",
                    f"Path doesn't exist:\n{p}\n\nSave anyway?"):
                    return
            add_or_update_profile(profile_name_var.get().strip() or "Default", p)
            set_addons_path(p)
            set_dry_run(dry_run_var.get())
            set_cf_api_key(cf_key_var.get())
            dialog.destroy()
            self._on_done()

        save_btn = tk.Label(btn_row, text="Save", bg=C["accent"],
                            fg=C["accent_fg"], font=FONT_BODY, cursor="hand2",
                            padx=10, pady=9)
        save_btn.pack(side="right")
        save_btn.bind("<Enter>", lambda e: save_btn.configure(bg=C["accent_hi"]))
        save_btn.bind("<Leave>", lambda e: save_btn.configure(bg=C["accent"]))
        save_btn.bind("<Button-1>", lambda e: save_and_close())

        if not first_run:
            cancel_btn = tk.Label(btn_row, text="Cancel", bg=C["bg"],
                                  fg=C["text_dim"], font=FONT_BODY,
                                  cursor="hand2", padx=10, pady=9)
            cancel_btn.pack(side="right", padx=(0, 8))
            cancel_btn.bind("<Enter>", lambda e: cancel_btn.configure(fg=C["text"]))
            cancel_btn.bind("<Leave>", lambda e: cancel_btn.configure(fg=C["text_dim"]))
            cancel_btn.bind("<Button-1>", lambda e: dialog.destroy())

        # Stash what _render_list needs.
        self._tk = tk
        self._C = C
        self._FONT_BODY = FONT_BODY
        self._FONT_SM = FONT_SM
        self._FONT_XS = FONT_XS
        self._list_inner = list_inner
        self._manual_var = manual_var
        self._profile_name_var = profile_name_var

        self._render_list()

    # ------------------------------------------------------------------
    # Detected-installations list
    # ------------------------------------------------------------------

    def _render_list(self) -> None:
        tk = self._tk
        C = self._C
        list_inner = self._list_inner

        for w in list_inner.winfo_children():
            w.destroy()

        installations = self._scan_installations()

        if not installations:
            tk.Label(list_inner,
                     text="\n  No installations detected — enter path below\n",
                     bg=C["surface"], fg=C["text_muted"],
                     font=self._FONT_SM, justify="left").pack(anchor="w", padx=14)
            return

        for i, inst in enumerate(installations):
            row = tk.Frame(list_inner, bg=C["surface"], cursor="hand2")
            row.pack(fill="x")

            row_inner = tk.Frame(row, bg=C["surface"])
            row_inner.pack(fill="x", padx=16, pady=12)

            text_col = tk.Frame(row_inner, bg=C["surface"])
            text_col.pack(side="left", fill="both", expand=True)

            tk.Label(text_col, text=inst["flavor_name"], bg=C["surface"],
                     fg=C["text"], font=self._FONT_BODY).pack(anchor="w")

            short = inst["addons_path"]
            if len(short) > 70:
                short = "…" + short[-67:]
            tk.Label(text_col, text=short, bg=C["surface"], fg=C["text_muted"],
                     font=self._FONT_XS).pack(anchor="w", pady=(2, 0))

            select_btn = tk.Label(row_inner, text="Use", bg=C["surface_hi"],
                                  fg=C["text"], font=self._FONT_SM,
                                  cursor="hand2", padx=14, pady=6)
            select_btn.pack(side="right")

            def make_handler(p, n):
                return lambda e=None: (self._manual_var.set(p),
                                       self._profile_name_var.set(n))

            handler = make_handler(inst["addons_path"], inst["flavor_name"])
            select_btn.bind("<Button-1>", handler)
            row.bind("<Button-1>", handler)
            row_inner.bind("<Button-1>", handler)
            text_col.bind("<Button-1>", handler)

            def make_hover(r, enter):
                def fn(e):
                    bg = C["surface_hi"] if enter else C["surface"]
                    r.configure(bg=bg)
                    for c1 in r.winfo_children():
                        with contextlib.suppress(Exception):
                            c1.configure(bg=bg)
                            for c2 in c1.winfo_children():
                                with contextlib.suppress(Exception):
                                    c2.configure(bg=bg)
                return fn

            row.bind("<Enter>", make_hover(row, True))
            row.bind("<Leave>", make_hover(row, False))

            if i < len(installations) - 1:
                tk.Frame(list_inner, bg=C["border"], height=1).pack(fill="x")
