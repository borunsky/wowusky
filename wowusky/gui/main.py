"""wowusky GUI entry point — the main application window.

This module owns :func:`run_gui`: the Tk main window, sidebar navigation,
header/status bars, and the wiring of every tab/dialog class plus the
threaded install/update/backup triggers. It was moved verbatim out of
``wowusky.app`` (Etappe G2); the logic is unchanged.

The shared helpers (core/provider wrappers, catalog, palette, fonts, tab
classes) are pulled from :mod:`wowusky.app` via a star import so the moved
body keeps referencing them by their original names. ``app.py`` imports
``run_gui`` from here lazily, which avoids an import cycle.
"""

from __future__ import annotations

from wowusky.app import *  # noqa: F401,F403  (names the moved run_gui body uses)
from wowusky.app import (  # noqa: F401  (underscore names that import * skips)
    __version__,
    _append_version_history,
    _gui_make_button,
    _safe_grab,
)


def run_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog, ttk

    C, theme_mode = get_palette()

    # Fonts
    sans_family = resolve_sans_family()
    mono_family = resolve_mono_family()
    _fonts = make_font_set(sans_family, mono_family)
    FONT_LOGO    = _fonts["FONT_LOGO"]
    FONT_HEAD    = _fonts["FONT_HEAD"]
    FONT_SECTION = _fonts["FONT_SECTION"]
    FONT_BODY    = _fonts["FONT_BODY"]
    FONT_SM      = _fonts["FONT_SM"]
    FONT_XS      = _fonts["FONT_XS"]
    FONT_NAME    = _fonts["FONT_NAME"]
    FONT_VER     = _fonts["FONT_VER"]
    FONT_MONO    = _fonts["FONT_MONO"]

    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("1200x720")
    root.configure(bg=C["bg"])
    root.minsize(820, 520)

    # ---- Window / taskbar icon -------------------------------------
    _ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
    _icon_images = []
    try:
        for _sz in (256, 128, 64, 32):
            _p = os.path.join(_ASSETS_DIR, f"wowusky-icon-{_sz}.png")
            if os.path.isfile(_p):
                _icon_images.append(tk.PhotoImage(file=_p))
        if _icon_images:
            root.iconphoto(True, *_icon_images)
            root._wowusky_icons = _icon_images
    except Exception:
        pass

    # Global widget defaults
    root.option_add("*background",         C["bg"])
    root.option_add("*foreground",         C["text"])
    root.option_add("*Entry.background",   C["input_bg"])
    root.option_add("*Entry.foreground",   C["input_fg"])
    root.option_add("*Entry.insertBackground", C["accent"])
    root.option_add("*Entry.selectBackground", C["accent"])
    root.option_add("*Entry.selectForeground", C["accent_fg"])
    root.option_add("*Entry.highlightBackground", C["border"])
    root.option_add("*Entry.highlightColor",      C["accent"])
    root.option_add("*Entry.borderWidth", 0)
    root.option_add("*Entry.relief", "flat")
    root.option_add("*Text.background",    C["surface"])
    root.option_add("*Text.foreground",    C["text"])
    root.option_add("*Text.insertBackground", C["accent"])
    root.option_add("*Listbox.background", C["surface"])
    root.option_add("*Listbox.foreground", C["text"])
    root.option_add("*Menu.background",    C["surface"])
    root.option_add("*Menu.foreground",    C["text"])

    style = ttk.Style()
    style.theme_use("clam")

    style.configure("TCombobox",
                    fieldbackground=C["surface"],
                    background=C["surface"],
                    foreground=C["text"],
                    arrowcolor=C["text_dim"],
                    borderwidth=0,
                    bordercolor=C["border"],
                    lightcolor=C["surface"],
                    darkcolor=C["surface"])
    style.map("TCombobox",
              fieldbackground=[("readonly", C["surface"])],
              foreground=[("readonly", C["text"])])

    style.configure("Vertical.TScrollbar",
                    background=C["surface_hi"],
                    troughcolor=C["bg"],
                    borderwidth=0,
                    arrowcolor=C["text_muted"],
                    gripcount=0)
    style.map("Vertical.TScrollbar",
              background=[("active", C["border_hi"])])

    version_cache = {}
    checking_versions = [False]

    # ----------------------------------------------------------
    # Button helper — comfortable sizes (logic lives in wowusky.gui.widgets)
    # ----------------------------------------------------------
    import functools as _functools
    make_button = _functools.partial(_gui_make_button, palette=C, font_sm=FONT_SM)

    # ----------------------------------------------------------
    # Shared application context — passed to future tab classes (D4+)
    # ----------------------------------------------------------
    ctx = AppContext(
        palette=C,
        theme_mode=theme_mode,
        sans_family=sans_family,
        mono_family=mono_family,
        fonts=_fonts,
        root=root,
        make_button=make_button,
        app_log=app_log,
        version_cache=version_cache,
        checking_versions=checking_versions,
    )

    def open_settings(on_done, first_run=False):
        SettingsDialog(
            ctx, root,
            first_run=first_run,
            on_done=on_done,
            get_active_profile=get_active_profile,
            get_addons_path=get_addons_path,
            is_dry_run=is_dry_run,
            get_cf_api_key=get_curseforge_api_key,
            get_theme=lambda: load_config().get("theme", "auto"),
            scan_installations=scan_wow_installations,
            add_or_update_profile=add_or_update_profile,
            set_addons_path=set_addons_path,
            set_dry_run=set_dry_run,
            set_cf_api_key=set_curseforge_api_key,
            reset_manager_state=reset_manager_state,
            diagnose_cf_api=curseforge_api_diagnose,
        )

    # ----------------------------------------------------------
    # Top header bar  (matches prototype A)
    # ----------------------------------------------------------
    header_bar = tk.Frame(root, bg=C["surface"], height=44)
    header_bar.pack(side="top", fill="x")
    header_bar.pack_propagate(False)

    header_inner = tk.Frame(header_bar, bg=C["surface"])
    header_inner.pack(fill="both", expand=True, padx=14, pady=0)

    # Brand on the left
    hdr_brand = tk.Frame(header_inner, bg=C["surface"])
    hdr_brand.pack(side="left", fill="y")
    try:
        _hdr_mark_path = os.path.join(_ASSETS_DIR, "wowusky-icon-32.png")
        if os.path.isfile(_hdr_mark_path):
            _hdr_img = tk.PhotoImage(file=_hdr_mark_path)
            _hdr_lbl = tk.Label(hdr_brand, image=_hdr_img,
                                bg=C["surface"], borderwidth=0)
            _hdr_lbl.image = _hdr_img
            _hdr_lbl.pack(side="left", padx=(0, 9), pady=10)
    except Exception:
        pass
    tk.Label(hdr_brand, text="wowusky",
             bg=C["surface"], fg=C["text"],
             font=(sans_family, 13, "bold")).pack(side="left", pady=10)
    # Version pill in a separate wrapper so we can give it a real border box
    _ver_wrap = tk.Frame(hdr_brand, bg=C["surface"])
    _ver_wrap.pack(side="left", padx=(8, 0), pady=10)
    tk.Label(_ver_wrap, text=f"v{__version__}",
             bg=C["bg"], fg=C["text_muted"],
             font=(mono_family, 8),
             padx=6, pady=2,
             borderwidth=0, highlightthickness=1,
             highlightbackground=C["border"]).pack()

    # Header center (profile switcher)
    hdr_center = tk.Frame(header_inner, bg=C["surface"])
    hdr_center.pack(side="left", fill="both", expand=True, padx=(18, 0))

    # Header right: updates badge
    hdr_right = tk.Frame(header_inner, bg=C["surface"])
    hdr_right.pack(side="right", fill="y")
    updates_var = tk.StringVar(value="")
    _updates_wrap = tk.Frame(hdr_right, bg=C["surface"])
    _updates_wrap.pack(side="right", padx=(8, 0), pady=10)
    updates_badge = tk.Label(_updates_wrap, textvariable=updates_var,
                             bg="#0f3530", fg=C["accent"],
                             font=(sans_family, 9, "bold"),
                             padx=10, pady=3,
                             highlightthickness=1,
                             highlightbackground=C["accent"])
    updates_badge.pack()

    # Header bottom separator
    tk.Frame(root, bg=C["border"], height=1).pack(side="top", fill="x")

    # ----------------------------------------------------------
    # Bottom status bar
    # ----------------------------------------------------------
    tk.Frame(root, bg=C["border"], height=1).pack(side="bottom", fill="x")
    status_bar = tk.Frame(root, bg=C["surface"], height=26)
    status_bar.pack(side="bottom", fill="x")
    status_bar.pack_propagate(False)
    status_inner = tk.Frame(status_bar, bg=C["surface"])
    status_inner.pack(fill="both", expand=True, padx=14)
    status_conn_var = tk.StringVar(value="● Connected")
    tk.Label(status_inner, textvariable=status_conn_var,
             bg=C["surface"], fg=C["accent"],
             font=(sans_family, 9)).pack(side="left", pady=5)
    tk.Label(status_inner, text="·", bg=C["surface"], fg=C["text_muted"],
             font=FONT_XS).pack(side="left", padx=8, pady=5)
    status_path_var = tk.StringVar(value="No active profile")
    tk.Label(status_inner, textvariable=status_path_var,
             bg=C["surface"], fg=C["text_muted"],
             font=(mono_family, 9)).pack(side="left", pady=5)
    status_sync_var = tk.StringVar(value="ready")
    tk.Label(status_inner, textvariable=status_sync_var,
             bg=C["surface"], fg=C["text_muted"],
             font=(mono_family, 9)).pack(side="right", pady=5)

    # ----------------------------------------------------------
    # Shell: compact sidebar + responsive content
    # ----------------------------------------------------------
    shell = tk.Frame(root, bg=C["bg"])
    shell.pack(side="top", fill="both", expand=True)

    sidebar = tk.Frame(shell, bg=C["surface"], width=200)
    sidebar.pack(side="left", fill="y")
    sidebar.pack_propagate(False)

    main_area = tk.Frame(shell, bg=C["bg"])
    main_area.pack(side="left", fill="both", expand=True)

    logo_frame = tk.Frame(sidebar, bg=C["surface"], height=8)
    logo_frame.pack(fill="x")

    profile_var = tk.StringVar()
    def profile_display_items():
        data = load_profiles()
        items = []
        for pid, prof in data.get("profiles", {}).items():
            items.append(f"{prof.get('name', pid)}  [{pid}]")
        return items
    def set_profile_combo():
        data = load_profiles()
        active = data.get("active")
        prof = data.get("profiles", {}).get(active, {})
        profile_var.set(f"{prof.get('name', active)}  [{active}]")
        profile_combo.configure(values=profile_display_items())
    def on_profile_select(event=None):
        val = profile_var.get()
        m = re.search(r"\[([^\]]+)\]$", val)
        if m:
            set_active_profile(m.group(1))
            status_var.set(f"Profile: {get_active_profile().get('name', m.group(1))}")
            try:
                refresh_all()
            except NameError:
                pass
    profile_combo = ttk.Combobox(hdr_center, textvariable=profile_var,
                                  state="readonly", font=FONT_SM, width=42)
    profile_combo.pack(side="left", pady=8)
    profile_combo.bind("<<ComboboxSelected>>", on_profile_select)

    current_tab = tk.StringVar(value="browse")
    nav_buttons = {}

    # Tabs whose content refresh_all() rebuilds. Rendering every one of
    # them eagerly on each refresh (profile switch, post-install) froze the
    # UI for a few seconds, because each rebuilds many Tk widgets — the
    # Browse tab alone lays out the full 241-entry catalog. We render only
    # the visible tab now and defer the rest to the next time they're shown.
    _dirty_tabs = set()

    def _render_tab(key):
        fn = {
            "browse":    lambda: browse_tab_obj.render(),
            "installed": lambda: installed_tab_obj.render(),
            "weakauras": lambda: weakauras_tab_obj.render(),
        }.get(key)
        if fn is None:
            return
        try: fn()
        except Exception: pass
        _dirty_tabs.discard(key)

    def make_nav(parent, key, label, icon="", count_var=None):
        item = tk.Frame(parent, bg=C["surface"], cursor="hand2")
        item.pack(fill="x", padx=8, pady=1)
        indicator = tk.Frame(item, bg=C["surface"], width=3)
        indicator.pack(side="left", fill="y")
        ic = tk.Label(item, text=icon,
                      bg=C["surface"], fg=C["text_dim"],
                      font=(sans_family, 11), padx=8, pady=7)
        ic.pack(side="left")
        lbl = tk.Label(item, text=label,
                       bg=C["surface"], fg=C["text_dim"],
                       font=FONT_BODY, padx=0, pady=7, anchor="w")
        lbl.pack(side="left", fill="x", expand=True)
        badge = None
        if count_var is not None:
            badge = tk.Label(item, textvariable=count_var,
                             bg=C["surface_hi"], fg=C["text_muted"],
                             font=(mono_family, 8),
                             padx=6, pady=1)
            badge.pack(side="right", padx=(0, 10))

        widgets = (item, lbl, indicator, ic) + ((badge,) if badge else ())

        def on_click(e=None):
            current_tab.set(key)
            update_nav_styles()
            show_tab(key)
        def on_enter(e):
            if current_tab.get() != key:
                for w in (item, lbl, ic): w.configure(bg=C["surface_hi"])
                lbl.configure(fg=C["text"]); ic.configure(fg=C["text"])
                indicator.configure(bg=C["surface_hi"])
        def on_leave(e):
            if current_tab.get() != key:
                for w in (item, lbl, ic): w.configure(bg=C["surface"])
                lbl.configure(fg=C["text_dim"]); ic.configure(fg=C["text_dim"])
                indicator.configure(bg=C["surface"])

        for w in widgets:
            w.bind("<Button-1>", on_click)
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
        nav_buttons[key] = (item, lbl, indicator, ic, badge)

    def update_nav_styles():
        active = current_tab.get()
        for key, (item, lbl, indicator, ic, badge) in nav_buttons.items():
            if key == active:
                for w in (item, lbl, ic): w.configure(bg=C["surface_hi"])
                lbl.configure(fg=C["accent"]); ic.configure(fg=C["accent"])
                indicator.configure(bg=C["accent"])
                if badge:
                    badge.configure(bg=C["surface_hi"])
            else:
                for w in (item, lbl, ic): w.configure(bg=C["surface"])
                lbl.configure(fg=C["text_dim"]); ic.configure(fg=C["text_dim"])
                indicator.configure(bg=C["surface"])
                if badge:
                    badge.configure(bg=C["surface_hi"])

    # Nav count vars (live-updated by update_status_display)
    nav_installed_count = tk.StringVar(value="0")
    nav_updates_count = tk.StringVar(value="")
    nav_wago_count = tk.StringVar(value="0")

    # Section header
    tk.Label(sidebar, text="LIBRARY",
             bg=C["surface"], fg=C["text_muted"],
             font=(sans_family, 8, "bold"), anchor="w").pack(fill="x", padx=20, pady=(14, 4))

    nav_frame = tk.Frame(sidebar, bg=C["surface"])
    nav_frame.pack(fill="x", pady=(0, 8))
    make_nav(nav_frame, "browse",     "Browse",     "⌕")
    make_nav(nav_frame, "installed",  "Installed",  "◉", nav_installed_count)
    make_nav(nav_frame, "weakauras",  "WeakAuras",  "⚡", nav_wago_count)
    make_nav(nav_frame, "curseforge", "CurseForge", "⌂")
    make_nav(nav_frame, "manual",     "Import",     "↧")
    make_nav(nav_frame, "backups",    "Backups",    "⌬")
    make_nav(nav_frame, "log",        "Log",        "≡")

    # ────────────────────────────────────────────
    # Sidebar bottom: profiles list + storage bar + settings
    # ────────────────────────────────────────────
    side_bottom = tk.Frame(sidebar, bg=C["surface"])
    side_bottom.pack(side="bottom", fill="x", pady=(0, 8))

    # Settings button at very bottom
    settings_wrap = tk.Frame(side_bottom, bg=C["surface"])
    settings_wrap.pack(fill="x", padx=8, pady=(8, 0))
    make_button(settings_wrap, "Settings",
                lambda: open_settings(refresh_all),
                variant="ghost", compact=True).pack(fill="x")

    # Storage / disk indicator (placeholder — shows AddOns folder size)
    storage_wrap = tk.Frame(side_bottom, bg=C["surface"])
    storage_wrap.pack(fill="x", padx=12, pady=(10, 0))
    storage_label_var = tk.StringVar(value="Addons folder")
    storage_size_var = tk.StringVar(value="—")
    sl_row = tk.Frame(storage_wrap, bg=C["surface"])
    sl_row.pack(fill="x")
    tk.Label(sl_row, textvariable=storage_label_var,
             bg=C["surface"], fg=C["text_muted"],
             font=(sans_family, 8, "bold")).pack(side="left")
    tk.Label(sl_row, textvariable=storage_size_var,
             bg=C["surface"], fg=C["text_dim"],
             font=(mono_family, 8)).pack(side="right")
    storage_track = tk.Frame(storage_wrap, bg=C["bg"], height=3)
    storage_track.pack(fill="x", pady=(4, 0))
    storage_track.pack_propagate(False)
    storage_fill = tk.Frame(storage_track, bg=C["accent"])
    storage_fill.place(relx=0, rely=0, relwidth=0.05, relheight=1)

    # Profile list section
    tk.Label(side_bottom, text="PROFILES",
             bg=C["surface"], fg=C["text_muted"],
             font=(sans_family, 8, "bold"), anchor="w").pack(fill="x", padx=20, pady=(14, 4))
    profiles_box = tk.Frame(side_bottom, bg=C["surface"])
    profiles_box.pack(fill="x")

    FLAVOR_SHORT = {
        "retail": "Retail", "anniversary": "TBC",
        "vanilla": "Era", "mop_classic": "MoP", "ptr": "PTR",
    }

    def render_profile_list():
        for w in profiles_box.winfo_children():
            w.destroy()
        try:
            data = load_profiles()
        except Exception:
            return
        profiles = data.get("profiles", {}) or {}
        active = data.get("active")
        installed_by_profile = {}
        try:
            # Try to count addons per profile if we can
            for pid in profiles:
                pf = os.path.join(CONFIG_DIR, "installed", f"{pid}.json")
                if os.path.isfile(pf):
                    with open(pf) as f:
                        installed_by_profile[pid] = len(json.load(f))
        except Exception:
            pass
        for pid, prof in profiles.items():
            row = tk.Frame(profiles_box, bg=C["surface"], cursor="hand2")
            row.pack(fill="x", padx=8, pady=1)
            indic = tk.Frame(row, bg=C["accent"] if pid == active else C["surface"], width=3)
            indic.pack(side="left", fill="y")
            flavor_pill = tk.Label(row,
                text=FLAVOR_SHORT.get(prof.get("flavor"), prof.get("flavor", "?"))[:6],
                bg=C["bg"], fg=C["text_dim"],
                font=(mono_family, 8, "bold"),
                padx=5, pady=1)
            flavor_pill.pack(side="left", padx=(6, 6), pady=4)
            name_lbl = tk.Label(row, text=prof.get("name", pid),
                bg=C["surface"],
                fg=C["text"] if pid == active else C["text_dim"],
                font=(sans_family, 9), anchor="w")
            name_lbl.pack(side="left", fill="x", expand=True, pady=4)
            if pid in installed_by_profile:
                count = installed_by_profile[pid]
                tk.Label(row, text=str(count),
                    bg=C["surface"], fg=C["text_muted"],
                    font=(mono_family, 8)).pack(side="right", padx=(0, 10), pady=4)
            def switch(p=pid, r=row):
                try:
                    set_active_profile(p)
                    refresh_all()
                except Exception: pass
            for w in (row, name_lbl, indic, flavor_pill):
                w.bind("<Button-1>", lambda e, _=switch: _())

    # Keep status_var alive (used elsewhere) — invisible label
    status_var = tk.StringVar()
    set_profile_combo()
    render_profile_list()

    content = tk.Frame(main_area, bg=C["bg"])
    content.pack(fill="both", expand=True)

    tabs = {}

    # Log tab is a class (wowusky.gui.tabs.LogTab); created early so log_msg
    # is bound before any install/update closure can call it.
    log_tab_obj = LogTab(ctx, content)
    tabs["log"] = log_tab_obj.frame
    log_msg = log_tab_obj.log_msg

    def show_tab(key):
        for tab in tabs.values():
            tab.pack_forget()
        if key in tabs:
            tabs[key].pack(fill="both", expand=True)
        if key in _dirty_tabs:
            _render_tab(key)
        if key == "backups":
            try: backups_tab_obj.render()
            except Exception: pass
        if key == "curseforge" and get_curseforge_api_key():
            # Show popular addons when the tab is opened and no results are visible yet.
            try:
                if not cf_tab_obj._results_frame.winfo_children():
                    cf_tab_obj.search(initial=True)
            except Exception:
                pass

    # ----------------------------------------------------------
    # Tab: BROWSE
    # ----------------------------------------------------------
    # Tab: BROWSE is built below (wowusky.gui.tabs.BrowseTab), after
    # render_browse_card (its per-row renderer) is defined.

    # ----------------------------------------------------------
    # Tab: INSTALLED
    # ----------------------------------------------------------
    # Tab: INSTALLED is built below (wowusky.gui.tabs.InstalledTab), after
    # SOURCE_LABEL and the action closures it depends on are defined.

    # ----------------------------------------------------------
    # Tab: WEAKAURAS  (wowusky.gui.tabs.WeakAurasTab)
    # ----------------------------------------------------------
    def add_wago():
        url = weakauras_tab_obj.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Enter a wago.io URL or slug.")
            return
        slug, ver = parse_wago_url(url)
        if not slug:
            slug = url  # treat as slug directly

        current_tab.set("log"); update_nav_styles(); show_tab("log")

        def task():
            log_msg(f"⟩ adding wago.io/{slug}")
            entry = wago_add(slug)
            if entry:
                log_msg(f"  ✓ {entry['name']} (v{entry['version']})\n")
                root.after(0, lambda: (weakauras_tab_obj.clear_input(),
                                       weakauras_tab_obj.render()))
            else:
                log_msg("  ✗ failed to fetch info\n")

        threading.Thread(target=task, daemon=True).start()

    def update_aura(slug, entry):
        current_tab.set("log"); update_nav_styles(); show_tab("log")
        def task():
            log_msg(f"⟩ updating {entry['name']}")
            info = wago_fetch_info(slug)
            if info:
                wago = load_wago()
                wago["auras"][slug]["version"] = info.get("version") or info.get("wagoVersion") or 1
                wago["auras"][slug].pop("latest_version", None)
                save_wago(wago)
                log_msg(f"  ✓ updated to v{wago['auras'][slug]['version']}")
                log_msg("  hint: click Generate Companion to apply\n")
                root.after(0, weakauras_tab_obj.render)
            else:
                log_msg("  ✗ failed\n")
        threading.Thread(target=task, daemon=True).start()

    def remove_aura(slug, entry):
        if messagebox.askyesno("Remove", f"Stop tracking {entry['name']}?"):
            wago_remove(slug)
            weakauras_tab_obj.render()

    weakauras_tab_obj = WeakAurasTab(
        ctx, content,
        load_auras=lambda: load_wago().get("auras", {}),
        on_generate=lambda: trigger_generate_wac(),
        on_check=lambda: trigger_wago_check(),
        on_import=lambda: trigger_import_existing_weakauras(),
        on_add=add_wago,
        on_update=update_aura,
        on_remove=remove_aura,
        open_url=lambda u: open_in_browser(u),
    )
    tabs["weakauras"] = weakauras_tab_obj.frame

    # ----------------------------------------------------------
    # Tab: IMPORT  (wowusky.gui.tabs.ImportTab)
    # ----------------------------------------------------------
    def _on_install_zip(zip_path, name, cf_ref):
        ap = get_addons_path()
        if not ap:
            messagebox.showerror("No path", "Configure WoW path first.")
            return
        current_tab.set("log"); update_nav_styles(); show_tab("log")
        def task():
            try:
                import_zip_file(zip_path, ap, name=name, source="manual", log=log_msg,
                                curseforge_slug=cf_slug_from_ref(cf_ref),
                                curseforge_url=curseforge_files_url(cf_ref) if cf_ref.strip() else None)
                root.after(0, refresh_all)
                root.after(0, import_tab_obj.clear)
            except Exception as e:
                log_msg(f"  ✗ {e}\n")
        threading.Thread(target=task, daemon=True).start()

    def _on_install_cf(ref):
        if not get_curseforge_api_key():
            messagebox.showinfo("CurseForge fallback",
                                "CurseForge wird im Browser mit passendem Versionsfilter geöffnet. Lade die ZIP herunter und klicke danach auf 'Import latest from Downloads'.")
            open_in_browser(curseforge_search_url(ref))
            return
        ap = get_addons_path()
        if not ap:
            messagebox.showerror("No path", "Configure WoW path first.")
            return
        current_tab.set("log"); update_nav_styles(); show_tab("log")
        def task():
            try:
                install_curseforge(ref, ap, log=log_msg)
                root.after(0, refresh_all)
                root.after(0, lambda: import_tab_obj.cf_ref_var.set(""))
            except Exception as e:
                log_msg(f"  ✗ CurseForge: {e}\n")
        threading.Thread(target=task, daemon=True).start()

    import_tab_obj = ImportTab(
        ctx, content,
        newest_download_zip=newest_download_zip,
        guess_name_from_zip=guess_addon_name_from_zip,
        cf_slug_from_ref=cf_slug_from_ref,
        cf_files_url=curseforge_files_url,
        cf_search_url=curseforge_search_url,
        has_cf_api_key=get_curseforge_api_key,
        on_install_zip=_on_install_zip,
        on_install_cf=_on_install_cf,
        open_url=open_in_browser,
    )
    tabs["manual"] = import_tab_obj.frame

    def import_latest_download_zip():
        path = newest_download_zip()
        if not path:
            messagebox.showinfo("Downloads", "Keine ZIP-Datei im Downloads-Ordner gefunden.")
            return
        import_tab_obj.file_var.set(path)
        import_tab_obj.name_var.set(guess_addon_name_from_zip(path))
        import_tab_obj._install()

    # ----------------------------------------------------------
    # Tab: CURSEFORGE  (wowusky.gui.tabs.CurseForgeTab)
    # ----------------------------------------------------------
    def make_cf_card(parent_frame, mod):
        summary = curseforge_mod_summary(mod)
        card = tk.Frame(parent_frame, bg=C["surface"], padx=10, pady=8)
        card.pack(fill="x", pady=(0, 8))
        tk.Label(card, text=summary["name"], bg=C["surface"], fg=C["text"],
                 font=FONT_NAME, anchor="w").pack(fill="x")
        if summary["summary"]:
            tk.Label(card, text=summary["summary"], bg=C["surface"], fg=C["text_dim"],
                     font=FONT_SM, anchor="w", justify="left", wraplength=520).pack(fill="x", pady=(3, 5))
        meta = f"Project ID: {summary['id']}"
        if summary["downloads"]:
            meta += f"  ·  Downloads: {int(summary['downloads']):,}"
        tk.Label(card, text=meta, bg=C["surface"], fg=C["text_muted"],
                 font=FONT_XS, anchor="w").pack(fill="x", pady=(0, 6))
        row = tk.Frame(card, bg=C["surface"])
        row.pack(fill="x")

        def install_this():
            ap = get_addons_path()
            if not ap:
                messagebox.showerror("No path", "Configure WoW path first.")
                return
            if not get_curseforge_api_key():
                messagebox.showinfo("CurseForge fallback", "CurseForge wird im Browser mit passendem Versionsfilter geöffnet. Lade die ZIP herunter und klicke danach im Import-Tab auf 'Import latest from Downloads'.")
                if summary["url"]:
                    open_in_browser(curseforge_files_url(summary["url"]))
                current_tab.set("manual"); update_nav_styles(); show_tab("manual")
                return
            current_tab.set("log"); update_nav_styles(); show_tab("log")
            DOWNLOAD_QUEUE.put((install_curseforge, (mod, ap, log_msg)))

        make_button(row, "Install", install_this, variant="primary", compact=True).pack(side="left")
        if summary["url"]:
            make_button(row, "Open", lambda url=summary["url"]: open_in_browser(url),
                        variant="ghost", compact=True).pack(side="left", padx=(6, 0))
            tk.Label(row, text=summary["url"], bg=C["surface"], fg=C["text_muted"],
                     font=FONT_XS, anchor="w").pack(side="left", fill="x", expand=True, padx=(8, 0))

    def _run_cf_search(q, on_results, on_error):
        def task():
            try:
                results = curseforge_search(q, page_size=40)
                root.after(0, lambda: on_results(results))
            except Exception as e:
                err = str(e)
                root.after(0, lambda err=err: on_error(err))
        threading.Thread(target=task, daemon=True).start()

    cf_tab_obj = CurseForgeTab(
        ctx, content,
        has_cf_api_key=get_curseforge_api_key,
        run_cf_search=_run_cf_search,
        render_mod_card=make_cf_card,
        cf_search_url=curseforge_search_url,
        goto_import=lambda: (current_tab.set("manual"), update_nav_styles(), show_tab("manual")),
        import_latest_zip=import_latest_download_zip,
        open_url=open_in_browser,
    )
    tabs["curseforge"] = cf_tab_obj.frame

    def cf_search_ui(initial=False):
        cf_tab_obj.search(initial=initial)


    # ----------------------------------------------------------
    # Tab: BACKUPS  (wowusky.gui.tabs.BackupsTab)
    # ----------------------------------------------------------
    backups_tab_obj = BackupsTab(
        ctx, content,
        list_backups=list_full_backups,
        on_create=lambda: trigger_create_full_backup(),
        on_restore=lambda p: trigger_restore_full_backup(p),
        open_folder=lambda d: open_in_browser(d),
    )
    tabs["backups"] = backups_tab_obj.frame

    # ----------------------------------------------------------
    # Tab: LOG  (built above as wowusky.gui.tabs.LogTab)
    # ----------------------------------------------------------

    # ----------------------------------------------------------
    # Card renderers
    # ----------------------------------------------------------
    SOURCE_LABEL = {
        "tukui": "Tukui", "github": "GitHub", "wowi": "WoWI",
        "manual": "Manual", "external": "Local", "internal_wac": "wowusky",
        "curseforge": "CurseForge", "curseforge_web": "CurseForge", "curseforge_manual": "CurseForge ZIP",
    }

    # ----------------------------------------------------------
    # Tab: INSTALLED  (wowusky.gui.tabs.InstalledTab)
    # ----------------------------------------------------------
    installed_tab_obj = InstalledTab(
        ctx, content,
        load_installed=load_installed,
        find_catalog=find_addon_by_id,
        get_latest=lambda aid: version_cache.get(aid),
        versions_equal=versions_equal,
        has_backup=latest_backup_for_addon,
        cf_manual_latest=curseforge_manual_latest,
        cf_manual_url=curseforge_manual_url,
        source_label=SOURCE_LABEL,
        on_rescan=lambda: trigger_rescan(),
        on_check_updates=lambda: trigger_check_updates(),
        on_check_all_profiles=lambda: trigger_check_updates_all_profiles(),
        on_open_manager=lambda aid, ent: show_installed_addon_manager(aid, ent),
        on_update=lambda a: trigger_install(a),
        on_rollback=lambda aid, ent: do_installed_rollback(aid, ent),
        on_remove=lambda aid, ent: do_installed_remove(aid, ent),
        open_url=lambda u: open_in_browser(u),
    )
    tabs["installed"] = installed_tab_obj.frame

    def render_installed():
        installed_tab_obj.render()

    def do_installed_rollback(addon_id, entry):
        if not latest_backup_for_addon(addon_id):
            messagebox.showinfo("Rollback", "No backup found for this addon.")
            return
        if messagebox.askyesno("Rollback", f"Restore last backup for {entry['name']}?"):
            ap = get_addons_path()
            threading.Thread(
                target=lambda: (rollback_addon(addon_id, ap, log=log_msg),
                                root.after(0, refresh_all)),
                daemon=True).start()

    def do_installed_remove(addon_id, entry):
        if messagebox.askyesno("Remove",
                               f"Remove {entry['name']}?\nA backup is created first. This deletes the active folders."):
            ap = get_addons_path()
            threading.Thread(
                target=lambda: (uninstall_addon(addon_id, ap, log=log_msg),
                                root.after(0, refresh_all)),
                daemon=True).start()


    def provider_page_url(addon):
        src = addon.get("source")
        if src == "github":
            return "https://github.com/" + addon.get("repo", "")
        if src == "wowi":
            return "https://www.wowinterface.com/downloads/info" + str(addon.get("wowi_id", ""))
        if src == "tukui":
            return addon.get("api_url", "https://tukui.org/")
        if src in ("curseforge_web", "curseforge_manual", "curseforge"):
            return curseforge_files_url(addon.get("curseforge_slug") or addon.get("id", ""))
        if src == "internal_wac":
            return "https://wago.io/"
        return addon.get("url", "")

    def github_version_choices(addon):
        repo = addon.get("repo")
        if not repo:
            return []
        choices = []
        try:
            rels = http_get_json(f"https://api.github.com/repos/{repo}/releases?per_page=12")
            for rel in rels:
                tag = rel.get("tag_name") or rel.get("name") or "release"
                assets = [a for a in rel.get("assets", []) if a.get("browser_download_url") and a.get("name", "").lower().endswith(".zip")]
                url = assets[0].get("browser_download_url") if assets else rel.get("zipball_url")
                if url:
                    choices.append({"label": tag, "url": url})
        except Exception:
            pass
        if not choices:
            try:
                tags = http_get_json(f"https://api.github.com/repos/{repo}/tags?per_page=12")
                for tag in tags:
                    name = tag.get("name")
                    if name:
                        choices.append({"label": name, "url": f"https://github.com/{repo}/archive/refs/tags/{name}.zip"})
            except Exception:
                pass
        return choices

    def install_direct_zip_for_addon(addon, url, label):
        ap = get_addons_path()
        current_tab.set("log"); update_nav_styles(); show_tab("log")
        def task():
            log_msg(f"⟩ installing {addon['name']} {label}")
            try:
                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                    tmp_path = tmp.name
                http_download(url, tmp_path)
                installed = load_installed()
                previous_entry = installed.get(addon["id"])
                backup_path = backup_addon_folders(addon["id"], previous_entry, ap, log_msg) if previous_entry else None
                folders = extract_zip(tmp_path, ap, addon, log_msg)
                new_entry = {
                    "name": addon["name"], "version": label, "folders": folders or addon.get("folders", []),
                    "source": addon.get("source"), "sha256": sha256_file(tmp_path), "profile": get_active_profile_id()
                }
                installed[addon["id"]] = _append_version_history(new_entry, previous_entry, backup_path=backup_path, action="install-version")
                save_installed(installed)
                try: os.unlink(tmp_path)
                except Exception: pass
                log_msg("  ✓ installed\n")
                root.after(0, refresh_all)
            except Exception as exc:
                err = str(exc)
                log_msg(f"  ✗ {err}\n")
        threading.Thread(target=task, daemon=True).start()

    def show_addon_details(addon):
        AddonDetailsDialog(
            ctx, root, addon,
            source_label=SOURCE_LABEL,
            provider_page_url=provider_page_url,
            github_version_choices=github_version_choices,
            on_install=trigger_install,
            on_install_version=install_direct_zip_for_addon,
            open_url=open_in_browser,
        )

    # ----------------------------------------------------------
    # Source pill colors + category icon colors (match design A)
    # ----------------------------------------------------------
    SOURCE_DOT_COLOR = {
        "github":            "#c9d1da",
        "tukui":             "#5eead4",
        "wowi":              "#fbbf24",
        "curseforge":        "#fb923c",
        "curseforge_web":    "#fb923c",
        "curseforge_manual": "#fb923c",
        "manual":            "#a78bfa",
        "external":          "#a78bfa",
        "internal_wac":      "#f472b6",
    }
    CATEGORY_COLOR = {
        "I": "#5eead4", "A": "#f472b6", "B": "#fbbf24", "C": "#fb923c",
        "N": "#a78bfa", "Q": "#22c55e", "P": "#60a5fa", "M": "#34d399",
        "U": "#94a3b8", "R": "#f43f5e", "D": "#facc15", "L": "#94a3b8",
        "S": "#94a3b8",
    }

    def render_browse_card(parent, addon, installed_entry=None):
        is_installed = installed_entry is not None
        installed_version = installed_entry["version"] if is_installed else ""
        latest = version_cache.get(addon["id"])
        has_update = (
            is_installed and latest and latest != "?"
            and not versions_equal(installed_version, latest)
        )

        # Row container
        row = tk.Frame(parent, bg=C["bg"], cursor="hand2")
        row.pack(fill="x")
        body = tk.Frame(row, bg=C["bg"])
        body.pack(fill="x", padx=14, pady=8)

        # Category icon
        letter = (addon.get("category") or "?")[:1].upper() or "?"
        icon_bg = CATEGORY_COLOR.get(letter, C["surface_hi"])
        icon = tk.Label(body, text=letter, bg=icon_bg, fg="#052724",
                        font=(sans_family, 10, "bold"), width=2, height=1)
        icon.pack(side="left", padx=(0, 12))

        # Action button (right-most)
        if addon.get("source") in ("curseforge_web", "curseforge_manual"):
            btn = make_button(body, "Open CF",
                              lambda a=addon: trigger_install(a),
                              variant="primary", compact=True)
        elif not is_installed:
            btn = make_button(body, provider_action_label(addon, False),
                              lambda a=addon: trigger_install(a),
                              variant="primary", compact=True)
        elif has_update:
            btn = make_button(body, provider_action_label(addon, True),
                              lambda a=addon: trigger_install(a),
                              variant="primary", compact=True)
        elif addon.get("source") == "internal_wac":
            # WeakAuras Companion is generated locally — there is no
            # remote version to check, so it never gets a get_latest_
            # _version() pass. Without this branch it would fall through
            # to "Checking…" forever (latest stays None).
            btn = make_button(body, "✓ Installed", lambda: None,
                              variant="outline", enabled=False, compact=True)
        elif latest is None:
            btn = make_button(body, "Checking…", lambda: None,
                              variant="outline", enabled=False, compact=True)
        else:
            btn = make_button(body, "✓ Installed", lambda: None,
                              variant="outline", enabled=False, compact=True)
        btn.pack(side="right")

        # Source pill
        src        = addon.get("source", "")
        src_label  = SOURCE_LABEL.get(src, src or "—")
        src_dot_fg = SOURCE_DOT_COLOR.get(src, C["text_muted"])
        src_frame  = tk.Frame(body, bg=C["bg"])
        src_frame.pack(side="right", padx=(0, 14))
        tk.Label(src_frame, text="●", bg=C["bg"], fg=src_dot_fg,
                 font=(sans_family, 8)).pack(side="left")
        tk.Label(src_frame, text=src_label, bg=C["bg"], fg=C["text_dim"],
                 font=FONT_SM).pack(side="left", padx=(5, 0))

        # Version column
        if is_installed:
            ver_text  = installed_version
            ver_color = C["accent"] if has_update else C["text_dim"]
            if has_update and latest:
                ver_text = f"{installed_version} → {latest}"
            tk.Label(body, text=ver_text, bg=C["bg"], fg=ver_color,
                     font=FONT_MONO, width=20, anchor="e").pack(side="right", padx=(0, 14))
        elif latest and latest != "?":
            tk.Label(body, text=latest, bg=C["bg"], fg=C["text_muted"],
                     font=FONT_MONO, width=20, anchor="e").pack(side="right", padx=(0, 14))
        else:
            tk.Label(body, text="", bg=C["bg"], fg=C["text_muted"],
                     font=FONT_MONO, width=20).pack(side="right", padx=(0, 14))

        # Name + description
        text_col = tk.Frame(body, bg=C["bg"])
        text_col.pack(side="left", fill="both", expand=True)
        name_lbl = tk.Label(text_col, text=addon["name"], bg=C["bg"], fg=C["text"],
                            font=FONT_NAME, anchor="w")
        name_lbl.pack(anchor="w", fill="x")
        desc_text = addon.get("description") or f"{addon.get('author','')} · {addon.get('category','')}"
        desc_lbl = tk.Label(text_col, text=desc_text, bg=C["bg"], fg=C["text_muted"],
                            font=FONT_XS, anchor="w")
        desc_lbl.pack(anchor="w", fill="x")

        # Hover highlight
        hoverable = [row, body, text_col, name_lbl, desc_lbl, src_frame]
        def _hover(_e=None):
            for w in hoverable:
                try: w.configure(bg=C["surface_hi"])
                except Exception: pass
            for child in src_frame.winfo_children():
                try: child.configure(bg=C["surface_hi"])
                except Exception: pass
        def _leave(_e=None):
            for w in hoverable:
                try: w.configure(bg=C["bg"])
                except Exception: pass
            for child in src_frame.winfo_children():
                try: child.configure(bg=C["bg"])
                except Exception: pass
        for w in (row, body, text_col, name_lbl, desc_lbl, icon):
            w.bind("<Enter>",  _hover)
            w.bind("<Leave>",  _leave)
            w.bind("<Double-Button-1>", lambda e, a=addon: show_addon_details(a))

        # Bottom border
        tk.Frame(parent, bg=C["border"], height=1).pack(fill="x")

    browse_tab_obj = BrowseTab(
        ctx, content,
        get_catalog=lambda: ADDON_CATALOG,
        load_installed=load_installed,
        get_categories=get_categories,
        get_current_flavor=get_current_flavor,
        filter_by_flavor=filter_catalog_by_flavor,
        render_card=render_browse_card,
    )
    tabs["browse"] = browse_tab_obj.frame

    def show_installed_addon_manager(addon_id, entry):
        """Per-addon manager: version history, backups, rollback to specific backup."""
        dlg = tk.Toplevel(root)
        dlg.title(entry.get("name", addon_id))
        dlg.configure(bg=C["bg"])
        dlg.geometry("680x560")
        dlg.minsize(500, 420)
        dlg.transient(root)
        _safe_grab(dlg)

        header = tk.Frame(dlg, bg=C["bg"])
        header.pack(fill="x", padx=16, pady=(16, 10))
        tk.Label(header, text=entry.get("name", addon_id), bg=C["bg"], fg=C["text"], font=FONT_HEAD).pack(anchor="w")
        tk.Label(header, text=f"Current: {entry.get('version', 'unknown')} · {SOURCE_LABEL.get(entry.get('source'), entry.get('source', 'external'))}", bg=C["bg"], fg=C["text_muted"], font=FONT_SM).pack(anchor="w", pady=(4, 0))

        body = tk.Frame(dlg, bg=C["surface"])
        body.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        canvas = tk.Canvas(body, bg=C["surface"], highlightthickness=0, borderwidth=0)
        canvas.pack(side="left", fill="both", expand=True)
        HoverScrollbar(body, canvas)
        inner = tk.Frame(canvas, bg=C["surface"])
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))

        def restore_specific(path, version):
            if not messagebox.askyesno("Rollback", f"Restore {entry.get('name', addon_id)} to version {version}?\n\nCurrent folders are replaced from this backup."):
                return
            current_tab.set("log"); update_nav_styles(); show_tab("log")
            def task():
                ok = rollback_addon_to_backup(addon_id, path, get_addons_path(), log=log_msg)
                root.after(0, lambda: (dlg.destroy(), refresh_all()))
            threading.Thread(target=task, daemon=True).start()

        # Current snapshot
        section = tk.Frame(inner, bg=C["surface"])
        section.pack(fill="x", padx=12, pady=12)
        tk.Label(section, text="Current install", bg=C["surface"], fg=C["text"], font=FONT_SECTION).pack(anchor="w")
        folders = ", ".join(entry.get("folders", [])) or "unknown folders"
        tk.Label(section, text=f"Version: {entry.get('version', 'unknown')}\nFolders: {folders}\nSHA256: {(entry.get('sha256') or 'not tracked')}", bg=C["surface"], fg=C["text_dim"], font=FONT_SM, justify="left", anchor="w").pack(anchor="w", pady=(6, 0))

        tk.Frame(inner, bg=C["border"], height=1).pack(fill="x", padx=12)

        backups = list_addon_backups(addon_id)
        tk.Label(inner, text=f"Available backup versions ({len(backups)})", bg=C["surface"], fg=C["text"], font=FONT_SECTION).pack(anchor="w", padx=12, pady=(12, 6))
        if not backups:
            tk.Label(inner, text="No addon-specific backups yet. Backups are created before install/update/remove.", bg=C["surface"], fg=C["text_muted"], font=FONT_SM, wraplength=560, justify="left").pack(anchor="w", padx=12, pady=(0, 12))
        for item in backups:
            row = tk.Frame(inner, bg=C["surface"])
            row.pack(fill="x", padx=12, pady=6)
            txt = tk.Frame(row, bg=C["surface"])
            txt.pack(side="left", fill="x", expand=True)
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(item["mtime"]))
            size = f"{item['size'] / 1024:.0f} KB"
            tk.Label(txt, text=f"{item['version']}", bg=C["surface"], fg=C["text"], font=FONT_NAME).pack(anchor="w")
            tk.Label(txt, text=f"{when} · {SOURCE_LABEL.get(item.get('source'), item.get('source'))} · {size}", bg=C["surface"], fg=C["text_muted"], font=FONT_XS).pack(anchor="w", pady=(2, 0))
            make_button(row, "Restore", lambda p=item["path"], v=item["version"]: restore_specific(p, v), variant="primary", compact=True).pack(side="right")

        tk.Frame(inner, bg=C["border"], height=1).pack(fill="x", padx=12, pady=(10, 0))
        hist = entry.get("history", [])
        tk.Label(inner, text=f"Recorded history ({len(hist)})", bg=C["surface"], fg=C["text"], font=FONT_SECTION).pack(anchor="w", padx=12, pady=(12, 6))
        if not hist:
            tk.Label(inner, text="No previous versions recorded yet.", bg=C["surface"], fg=C["text_muted"], font=FONT_SM).pack(anchor="w", padx=12, pady=(0, 12))
        for h in reversed(hist[-30:]):
            row = tk.Frame(inner, bg=C["surface"])
            row.pack(fill="x", padx=12, pady=4)
            label = f"{h.get('version', 'unknown')} · {h.get('action', 'install')} · {h.get('time', '')}"
            tk.Label(row, text=label, bg=C["surface"], fg=C["text_dim"], font=FONT_SM, anchor="w").pack(side="left", fill="x", expand=True)
            if h.get("backup") and os.path.isfile(h["backup"]):
                make_button(row, "Restore", lambda p=h["backup"], v=h.get("version", "unknown"): restore_specific(p, v), variant="ghost", compact=True).pack(side="right")

        footer = tk.Frame(dlg, bg=C["bg"])
        footer.pack(fill="x", padx=16, pady=(0, 16))
        make_button(footer, "Close", dlg.destroy, variant="ghost").pack(side="right")

    # ----------------------------------------------------------
    # Render functions
    # ----------------------------------------------------------
    def render_browse():
        browse_tab_obj.render()

    def trigger_create_full_backup():
        current_tab.set("log"); update_nav_styles(); show_tab("log")
        def task():
            try:
                create_full_backup(log=log_msg)
                root.after(0, backups_tab_obj.render)
            except Exception as exc:
                log_msg(f"  ✗ backup failed: {exc}\n")
        threading.Thread(target=task, daemon=True).start()

    def trigger_restore_full_backup(path):
        if not messagebox.askyesno("Restore full backup", "Restore this backup into the active profile? This overwrites matching AddOns and WTF files."):
            return
        current_tab.set("log"); update_nav_styles(); show_tab("log")
        def task():
            try:
                restore_full_backup(path, log=log_msg)
                root.after(0, refresh_all)
            except Exception as exc:
                log_msg(f"  ✗ restore failed: {exc}\n")
        threading.Thread(target=task, daemon=True).start()

    def render_wago():
        weakauras_tab_obj.render()

    # ----------------------------------------------------------
    # Triggers
    # ----------------------------------------------------------
    def trigger_install(addon):
        if addon.get("source") in ("curseforge_web", "curseforge_manual"):
            page = addon_provider_page(addon)
            open_in_browser(page)
            messagebox.showinfo("CurseForge", "Die CurseForge-Dateiseite wurde mit passendem Versionsfilter geöffnet. Lade die ZIP herunter und nutze danach im Import-Tab 'Import latest from Downloads'.")
            current_tab.set("manual"); update_nav_styles(); show_tab("manual")
            return
        ap = get_addons_path()
        if not ap:
            messagebox.showerror("No path", "Configure WoW path first.")
            return

        current_tab.set("log"); update_nav_styles(); show_tab("log")

        def task():
            shown = [-1]
            def progress(dl, total):
                pct = int(dl / total * 100)
                step = pct // 20
                if step != shown[0]:
                    shown[0] = step
                    log_msg(f"  {pct}%")
            install_addon(addon, ap, log=log_msg, progress=progress)
            if addon["source"] != "internal_wac":
                version_cache[addon["id"]] = get_latest_version(addon)
            root.after(0, refresh_all)

        threading.Thread(target=task, daemon=True).start()

    def trigger_rescan():
        ap = get_addons_path()
        if not ap:
            messagebox.showerror("No path", "Configure WoW path first.")
            return
        log_msg(f"\n⟩ rescanning {ap}")
        sync_filesystem_with_db(ap)
        log_msg("  ✓ scan complete\n")
        refresh_all()
        check_versions_async()

    def trigger_check_updates():
        ap = get_addons_path()
        if not ap:
            messagebox.showerror("No path", "Configure WoW path first.")
            return

        current_tab.set("log"); update_nav_styles(); show_tab("log")

        def task():
            installed = load_installed()
            selected_sources = installed_tab_obj.selected_sources()
            updatable = [aid for aid in installed
                         if find_addon_by_id(aid)
                         and find_addon_by_id(aid)["source"] != "internal_wac"
                         and installed[aid].get("source", find_addon_by_id(aid).get("source")) in selected_sources]
            if not updatable:
                log_msg("\n⟩ nothing to check\n")
                return

            log_msg(f"\n⟩ checking {len(updatable)} addon(s)\n")
            for aid in updatable:
                addon = find_addon_by_id(aid)
                current = installed[aid]["version"]
                latest = get_latest_version(addon)
                version_cache[aid] = latest or "?"

                if latest is None:
                    log_msg(f"  {addon['name']}: check failed")
                    continue
                if versions_equal(latest, current):
                    log_msg(f"  {addon['name']}: current ({current})")
                    continue
                log_msg(f"\n⟩ {addon['name']}: {current} → {latest}")
                install_addon(addon, ap, log=log_msg)

            log_msg("\n  ✓ complete\n")
            root.after(0, refresh_all)

        threading.Thread(target=task, daemon=True).start()

    def trigger_check_updates_all_profiles():
        current_tab.set("log"); update_nav_styles(); show_tab("log")
        def task():
            data = load_profiles()
            original = data.get("active")
            log_msg("\n⟩ checking updates across all profiles")
            try:
                for pid, prof in data.get("profiles", {}).items():
                    set_active_profile(pid)
                    ap = get_addons_path()
                    if ap:
                        sync_filesystem_with_db(ap)
                    installed = load_installed(pid)
                    count = 0
                    log_msg(f"\n  {prof.get('name', pid)}")
                    for aid, entry in installed.items():
                        addon = find_addon_by_id(aid)
                        if not addon or addon.get("source") == "internal_wac":
                            continue
                        latest = get_latest_version(addon)
                        if latest and not versions_equal(latest, entry.get("version")):
                            count += 1
                            log_msg(f"    update: {entry.get('name', aid)} {entry.get('version')} → {latest}")
                    if count == 0:
                        log_msg("    all current or manual-only")
            finally:
                if original:
                    set_active_profile(original)
                root.after(0, refresh_all)
            log_msg("\n  ✓ all-profile check complete\n")
        threading.Thread(target=task, daemon=True).start()

    def trigger_wago_check():
        current_tab.set("log"); update_nav_styles(); show_tab("log")
        def task():
            log_msg("\n⟩ checking wago.io for aura updates")
            updates = wago_check_updates()
            if updates:
                log_msg(f"  {len(updates)} update(s) available")
                for slug in updates:
                    wago = load_wago()
                    entry = wago["auras"].get(slug, {})
                    log_msg(f"    {entry.get('name', slug)}: v{entry.get('version')} → v{entry.get('latest_version')}")
            else:
                log_msg("  all auras current")
            log_msg("")
            root.after(0, render_wago)
        threading.Thread(target=task, daemon=True).start()

    def trigger_import_existing_weakauras():
        current_tab.set("log"); update_nav_styles(); show_tab("log")
        def task():
            log_msg("\n⟩ scanning existing WeakAuras SavedVariables")
            result = import_existing_weakauras_from_savedvariables(log=log_msg)
            if not result["files"]:
                log_msg("  ✗ no WeakAuras.lua found in the active profile WTF folder")
                log_msg("  hint: set the correct WoW profile/path in Settings first\n")
            else:
                for p in result["files"][:3]:
                    log_msg(f"  read: {p}")
                if len(result["files"]) > 3:
                    log_msg(f"  ... plus {len(result['files']) - 3} more")
                log_msg(f"  found: {len(result['slugs'])} Wago ID(s)")
                log_msg(f"  added: {result['added']}, already tracked: {result['existing']}, failed: {result['failed']}\n")
            root.after(0, render_wago)
        threading.Thread(target=task, daemon=True).start()

    def trigger_generate_wac():
        ap = get_addons_path()
        if not ap:
            messagebox.showerror("No path", "Configure WoW path first.")
            return
        current_tab.set("log"); update_nav_styles(); show_tab("log")
        def task():
            log_msg("\n⟩ generating WeakAurasCompanion")
            ok = generate_wac_companion(ap)
            if ok:
                count = len(load_wago().get("auras", {}))
                log_msg(f"  ✓ generated with {count} auras")
                log_msg("  reload UI in-game (/reload) to see updates\n")
                root.after(0, refresh_all)
            else:
                log_msg("  ✗ generation failed\n")
        threading.Thread(target=task, daemon=True).start()

    def check_versions_async():
        if checking_versions[0]: return
        checking_versions[0] = True
        def task():
            to_check = set()
            for addon in ADDON_CATALOG:
                if addon["source"] == "internal_wac":
                    continue
                if addon["source"] in ("curseforge_web",):
                    version_cache[addon["id"]] = "manual"
                    continue
                to_check.add(addon["id"])
            for aid in to_check:
                addon = find_addon_by_id(aid)
                if not addon: continue
                v = get_latest_version(addon)
                version_cache[aid] = v or "manual"
            checking_versions[0] = False
            root.after(0, lambda: (render_browse(), render_installed()))
        threading.Thread(target=task, daemon=True).start()

    # ----------------------------------------------------------
    # Mouse wheel
    # ----------------------------------------------------------
    def on_wheel(event):
        tab = current_tab.get()
        canvas = {
            "browse":      browse_tab_obj.canvas,
            "installed":   installed_tab_obj.canvas,
            "weakauras":   weakauras_tab_obj.canvas,
            "backups":     backups_tab_obj.canvas,
            "curseforge":  cf_tab_obj.canvas,
        }.get(tab)
        if canvas is None: return
        delta = -1 if (event.num == 4 or (event.delta and event.delta > 0)) else 1
        canvas.yview_scroll(delta, "units")

    root.bind_all("<MouseWheel>", on_wheel)
    root.bind_all("<Button-4>", on_wheel)
    root.bind_all("<Button-5>", on_wheel)

    # ----------------------------------------------------------
    # Status & refresh
    # ----------------------------------------------------------
    def update_status_display():
        prof = get_active_profile()
        p = get_addons_path()
        if prof and p and os.path.isdir(p):
            status_var.set(f"● {prof.get('name', 'Profile')}\n{p}")
            status_conn_var.set(f"● Connected · {prof.get('name', 'Profile')}")
            status_path_var.set(p)
        else:
            status_var.set("○ Not connected")
            status_conn_var.set("○ Not connected")
            status_path_var.set("No active profile")
        # Updates count + nav counts
        try:
            installed = load_installed()
            updates = 0
            for aid, entry in installed.items():
                latest = version_cache.get(aid)
                if latest and latest != "?" and not versions_equal(entry.get("version", ""), latest):
                    updates += 1
            updates_var.set(f"↑ {updates} update{'s' if updates != 1 else ''}" if updates else "")
            nav_installed_count.set(str(len(installed)))
            nav_updates_count.set(str(updates) if updates else "")
        except Exception:
            updates_var.set("")
        # WeakAuras count
        try:
            wago = load_wago()
            nav_wago_count.set(str(len(wago.get("auras", {}))))
        except Exception:
            pass
        # Storage bar
        try:
            if p and os.path.isdir(p):
                total = 0
                for root_, _, files in os.walk(p):
                    for f in files:
                        try:
                            total += os.path.getsize(os.path.join(root_, f))
                        except Exception:
                            pass
                mb = total / (1024 * 1024)
                if mb > 1024:
                    storage_size_var.set(f"{mb/1024:.1f} GB")
                else:
                    storage_size_var.set(f"{mb:.0f} MB")
                # Cap at 2 GB scale for the bar
                pct = min(0.95, mb / 2048.0)
                storage_fill.place_configure(relwidth=max(0.02, pct))
            else:
                storage_size_var.set("—")
                storage_fill.place_configure(relwidth=0.02)
        except Exception:
            pass
        # Refresh profile list (active highlight may have moved)
        try: render_profile_list()
        except Exception: pass

    def refresh_all():
        try: set_profile_combo()
        except Exception: pass
        update_status_display()
        # Render only the visible tab now; mark the rest dirty so they
        # rebuild lazily when next shown. Keeps profile-switch and
        # post-install refreshes from freezing on offscreen tabs.
        active = current_tab.get()
        for key in ("browse", "installed", "weakauras"):
            if key == active:
                _render_tab(key)
            else:
                _dirty_tabs.add(key)
        try: backups_tab_obj.render()
        except Exception: pass

    # ----------------------------------------------------------
    # Init
    # ----------------------------------------------------------
    def _initial_setup():
        ap = get_addons_path()
        if ap:
            sync_filesystem_with_db(ap)
        refresh_all()
        check_versions_async()

    if not get_addons_path():
        root.after(120, lambda: open_settings(_initial_setup, first_run=True))

    if get_addons_path():
        sync_filesystem_with_db(get_addons_path())

    update_nav_styles()
    show_tab("browse")
    refresh_all()

    if get_addons_path():
        root.after(500, check_versions_async)


    def download_worker():
        while True:
            item = DOWNLOAD_QUEUE.get()
            try:
                fn, args = item
                fn(*args)
                root.after(0, refresh_all)
            except Exception as e:
                root.after(0, lambda err=e: log_msg(f"  ✗ queued task: {err}\n"))
            finally:
                DOWNLOAD_QUEUE.task_done()

    for _ in range(3):
        threading.Thread(target=download_worker, daemon=True).start()

    root.mainloop()
