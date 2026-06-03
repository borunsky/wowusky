#!/usr/bin/env python3
"""
wowusky — minimalist WoW addon manager for Linux.

v0.4 highlights
---------------
The application has been split into reusable modules:

  * :mod:`wowusky.core`       — paths, config, profiles, HTTP, TOC, …
  * :mod:`wowusky.providers`  — Tukui, GitHub, WoWInterface, CurseForge, Wago
  * :mod:`wowusky.catalog`    — manifest-based addon list

This file owns the addon install/update orchestration and the wiring
that the GUI calls into. The Tk main window itself now lives in
:mod:`wowusky.gui.main` (moved out in Etappe G2); ``run_gui`` here is a
thin lazy delegator. The shared helpers come from :mod:`wowusky.core`,
:mod:`wowusky.providers` and :mod:`wowusky.catalog`.

Functions kept here are the install/update orchestrator and thin
facades around the core helpers that preserve the call signatures the
GUI code (now in :mod:`wowusky.gui.main`) already uses.
"""

import glob
import hashlib
import json
import logging
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import zipfile
from logging.handlers import RotatingFileHandler
from pathlib import Path
from queue import Queue

# ── package-level re-exports ─────────────────────────────────────────
from wowusky import APP_NAME, __version__

# ── catalog loader ───────────────────────────────────────────────────
from wowusky.catalog import load_catalog as _load_manifest_catalog
from wowusky.core import http as _ws_http

# ── new core modules (replace the duplicate definitions below) ───────
from wowusky.core import logging_setup as _ws_logging
from wowusky.core.flavors import (
    FLAVOR_COMPATIBILITY,
    TOC_SUFFIXES,
    WOW_FLAVORS,
    flavor_display_name,
    flavor_for_directory,
    flavor_interface,
    is_compatible,
)
from wowusky.core.toc import (
    parse_toc_file,
    parse_toc_text,
    read_addon_toc,
    strip_color_codes,
)
from wowusky.core.versions import normalise_version, version_tokens, versions_equal
from wowusky.core.installer import (
    append_version_history as _append_version_history,
    build_import_entry,
    guess_addon_name_from_zip,
    install_addon as _core_install_addon,
    uninstall_addon as _core_uninstall_addon,
)
from wowusky.core.zipper import extract_addon_zip, sha256_file


# The catalog loader, install/provider orchestration facade and flavor
# helpers now live in wowusky.orchestrator (Etappe H). They are imported
# back below as a re-export surface for the GUI (wowusky.gui.main pulls
# them via `from wowusky.app import *`) and for the tests.


# ============================================================
# Paths & Config
# ============================================================

# Canonical, XDG-aware paths live in wowusky.core.paths. The GUI used
# to re-derive these with os.path.expanduser("~/..."), which silently
# ignored XDG_DATA_HOME and made the data location impossible to
# redirect (e.g. for testing). We now import the single source of
# truth and convert the Path objects to str, since the GUI code below
# is written against os.path string APIs.
from wowusky.core import paths as _ws_paths  # noqa: E402

CONFIG_DIR     = str(_ws_paths.CONFIG_DIR)
CONFIG_FILE    = str(_ws_paths.CONFIG_FILE)
INSTALLED_FILE = str(_ws_paths.INSTALLED_FILE)   # legacy single-profile path
PROFILES_FILE  = str(_ws_paths.PROFILES_FILE)
INSTALLED_DIR  = str(_ws_paths.INSTALLED_DIR)
BACKUP_DIR     = str(_ws_paths.BACKUP_DIR)
LOG_DIR        = str(_ws_paths.LOG_DIR)
WAGO_FILE      = str(_ws_paths.WAGO_FILE)
MANIFEST_DIR   = str(_ws_paths.MANIFEST_DIR)
PACKAGE_MANIFEST_DIR = os.path.join(os.path.dirname(__file__), "catalog", "manifests")

# Manager-state persistence layer (config / profiles / installed DB / wago).
# These used to live inline in app.py; they are pure JSON+dict logic with no
# GUI/HTTP/logging coupling, so they now live in wowusky.core.state and are
# re-exported here for the rest of app.py.
from wowusky.core.state import (  # noqa: E402
    add_or_update_profile, ensure_config_dir, get_active_profile,
    get_active_profile_id, get_addons_path, get_curseforge_api_key,
    infer_profile_from_path, installed_file_for_profile, is_dry_run,
    load_config, load_installed, load_profiles, load_wago,
    normalize_installations, normalize_profiles_data, save_config,
    save_installed, save_profiles, save_wago, set_active_profile,
    set_addons_path, set_curseforge_api_key, set_dry_run,
    slugify_profile_name)
CACHE_TTL      = 300
HTTP_CACHE     = {}
DOWNLOAD_QUEUE = Queue()

# Install / provider orchestration facade (Etappe H). These were defined
# inline in app.py; they now live in wowusky.orchestrator, which depends
# only on wowusky.core / providers / catalog (never on app.py), so this
# import carries no cycle. Re-exported here so the GUI's star import and
# the tests keep seeing them as app.* attributes.
from wowusky.orchestrator import (  # noqa: E402, F401
    ADDON_CATALOG,
    SOURCES,
    _load_addon_catalog_with_compat,
    addon_provider_page,
    app_log,
    curseforge_files_url,
    curseforge_manual_url,
    curseforge_search_url,
    downloads_dir,
    extract_zip,
    filter_catalog_by_flavor,
    find_addon_by_id,
    generate_wac_companion,
    get_categories,
    get_current_flavor,
    get_download_url,
    get_latest_version,
    install_addon,
    install_curseforge,
    install_curseforge_dependencies,
    import_zip_file,
    internal_wac_url,
    internal_wac_version,
    newest_download_zip,
    open_in_browser,
    provider_action_label,
    scan_download_zips,
    uninstall_addon,
)

# WoW install discovery + filesystem/DB reconciliation now live in
# wowusky.core.scan. WOW_SEARCH_PATHS / _display_path_preference /
# scan_wow_installations are re-exported below; sync_filesystem_with_db
# keeps a thin app.py wrapper that injects ADDON_CATALOG.
from wowusky.core.scan import (  # noqa: E402
    WOW_SEARCH_PATHS, _display_path_preference, scan_wow_installations)
from wowusky.core import scan as _scan  # noqa: E402


# Flavor compatibility map: what flavors does an addon for X also work on?
# anniversary (TBC) can use TBC and Classic addons

# Addon Catalog
# ============================================================
# flavors: list of flavor tags this addon supports
#   "all" = any flavor
#   "anniversary", "tbc", "vanilla", "classic", "mop_classic", "mop",
#   "retail", "mainline"
# ============================================================

# ADDON_CATALOG is loaded in wowusky.orchestrator (manifest files via
# wowusky.catalog) and re-exported above.


# Extra CurseForge-web catalog entries. These are shown in Browse and use the
# safe browser + Downloads import workflow when no approved Core API key exists.





# Catalog link audit notes (updated for v0.1.8-alpha):
# - Bartender4 moved from old WoWInterface id 9018 to Nevcairiel/Bartender4.
# - TellMeWhen WoWInterface id corrected to 10855.
# - KuiNameplates WoWInterface id corrected to 19390.
# - Details, Omen and Leatrix Plus use CurseForge manual flow because their
#   non-CurseForge distribution is stale, flavor-specific or inconsistent.
# - BigWigs uses flavor-aware repositories for Retail, Classic, TBC Anniversary
#   and MoP Classic.
# - Threat Plates and Bagnon point to maintained upstream GitHub repositories.


# ============================================================
# Config I/O
# ============================================================

# _setup_file_logging / app_log moved to wowusky.orchestrator (app_log is
# re-exported above for reset_manager_state and the GUI).

def reset_manager_state():
    """Reset only wowusky's own state for testing.

    This intentionally does NOT touch any World of Warcraft AddOns folders,
    WTF folders, WeakAuras SavedVariables, or downloaded ZIP files. It only
    removes files under ~/.local/share/wowusky so the app starts like fresh.
    """
    targets = [
        CONFIG_FILE,
        PROFILES_FILE,
        INSTALLED_FILE,
        WAGO_FILE,
        INSTALLED_DIR,
        BACKUP_DIR,
        LOG_DIR,
    ]
    removed = []
    for target in targets:
        try:
            if os.path.isdir(target):
                shutil.rmtree(target)
                removed.append(target)
            elif os.path.isfile(target):
                os.remove(target)
                removed.append(target)
        except Exception as exc:
            app_log(f"reset skipped {target}: {exc}", "warning")
    HTTP_CACHE.clear()
    ensure_config_dir()
    return removed

# get_current_flavor moved to wowusky.orchestrator (re-exported above).


# ============================================================
# WoW Detection
# ============================================================


# ============================================================
# TOC parsing
# ============================================================

TOC_VERSION_RX   = re.compile(r'^##\s*Version\s*:\s*(.+)$',   re.IGNORECASE | re.MULTILINE)
TOC_TITLE_RX     = re.compile(r'^##\s*Title\s*:\s*(.+)$',     re.IGNORECASE | re.MULTILINE)
TOC_INTERFACE_RX = re.compile(r'^##\s*Interface\s*:\s*(\d+)', re.IGNORECASE | re.MULTILINE)
TOC_NOTES_RX     = re.compile(r'^##\s*Notes\s*:\s*(.+)$',     re.IGNORECASE | re.MULTILINE)

# strip_color_codes is imported from wowusky.core.toc at the top.
# read_toc_info is the legacy name for read_addon_toc.
read_toc_info = read_addon_toc
# _parse_toc lives in wowusky.core.toc as parse_toc_file.
_parse_toc = parse_toc_file


def sync_filesystem_with_db(addons_path):
    """Reconcile the active profile's installed DB with the AddOns folder.

    Thin wrapper over wowusky.core.scan.sync_filesystem_with_db that injects
    the app's loaded ADDON_CATALOG.
    """
    _scan.sync_filesystem_with_db(addons_path, ADDON_CATALOG)


# ============================================================
# HTTP
# ============================================================

# _http is replaced by wowusky.core.http helpers.
# A small number of callers still want a raw urlopen-like object (for
# reading non-JSON text). We expose the underlying opener under the
# legacy name.
from wowusky.core.http import _open as _http  # noqa: E402
# http_get_json is imported via wowusky.core.http.
http_get_json = _ws_http.get_json
# http_download is imported via wowusky.core.http.
http_download = _ws_http.download
# ============================================================
# Source adapters
# ============================================================

from wowusky.providers.tukui_fns import tukui_url, tukui_version  # noqa: E402

from wowusky.providers import github_fns as _github_fns  # noqa: E402, F401
# Provider flavor/API-key monkeypatching is done in wowusky.orchestrator.
from wowusky.providers.github_fns import (  # noqa: E402, F401
    _github_branch_exists, _github_pick_asset, github_default_branch,
    github_releases, github_repo_for_addon, github_repo_url, github_tags,
    github_url, github_version)
from wowusky.providers.wowi_fns import (  # noqa: E402, F401
    wowi_info, wowi_page_url, wowi_url, wowi_version)

from wowusky.providers.curseforge_fns import (  # noqa: E402
    _cf_file_versions, cf_slug_from_ref, curseforge_file_matches_flavor,
    curseforge_headers, curseforge_web_url, curseforge_web_version)

from wowusky.providers import curseforge_fns as _cf_fns  # noqa: E402, F401

# internal_wac_version / internal_wac_url moved to wowusky.orchestrator.


# ============================================================
# CurseForge API adapter
# ============================================================
# CurseForge requires an API key. Paste it in Settings or export
# CURSEFORGE_API_KEY before launching wowusky. The key is never bundled.

# CURSEFORGE_API_BASE and CURSEFORGE_GAME_ID imported from curseforge_fns.

from wowusky.providers.curseforge_fns import (  # noqa: E402
    CF_FLAVOR_TEXT, CF_VERSION_TYPE_HINTS, CURSEFORGE_URL_RX,
    curseforge_api_diagnose, curseforge_download_url,
    curseforge_get_files, curseforge_json, curseforge_manual_latest,
    curseforge_mod_from_ref, curseforge_mod_summary,
    curseforge_pick_file, curseforge_search, curseforge_url_from_installed,
    curseforge_version_from_installed,
    install_curseforge as _cf_install_curseforge,
    install_curseforge_dependencies as _cf_install_deps,
    CURSEFORGE_API_BASE, CURSEFORGE_GAME_ID,
)

from wowusky.core.resolver import (  # noqa: E402
    CF_WEB_SEARCH_HINT, CF_WEB_VERSION_TYPE_HINTS, SEMI_MANAGED_SOURCES)
from wowusky.core import resolver as _resolver  # noqa: E402


# curseforge_json / curseforge_api_diagnose are imported from curseforge_fns.
# The CurseForge web-URL facades, Downloads helpers, manual ZIP import,
# CurseForge install wrappers and the SOURCES version/URL dispatch all moved
# to wowusky.orchestrator (re-exported above).


# ============================================================
# Version comparison
# ============================================================

# versions_equal is imported from wowusky.core.versions.
# ============================================================
# Wago.io / WeakAuras Companion
# ============================================================

from wowusky.providers.wago_fns import (  # noqa: E402
    WAGO_SLUG_RX, parse_wago_url, wago_fetch_encoded, wago_fetch_info)
from wowusky.core.state import get_wtf_path  # noqa: E402
from wowusky.core.wago import (  # noqa: E402
    extract_wago_slugs_from_text,
    find_weakauras_savedvariables,
    import_existing_weakauras_from_savedvariables,
    wago_add,
    wago_check_updates,
    wago_remove,
    wago_search,
)
# generate_wac_companion, addon_provider_page and provider_action_label moved
# to wowusky.orchestrator (re-exported above).


# sha256_file is imported from wowusky.core.zipper (single source of truth).

from wowusky.core.backup import (  # noqa: E402
    FULL_BACKUP_DIR_NAME,
    backup_addon_folders,
    create_full_backup,
    full_backup_dir,
    latest_backup_for_addon,
    list_addon_backups,
    list_full_backups,
    restore_full_backup,
    rollback_addon,
    rollback_addon_to_backup,
)

# install_addon / extract_zip / uninstall_addon and the catalog queries
# (find_addon_by_id, get_categories, filter_catalog_by_flavor) moved to
# wowusky.orchestrator (re-exported above).


# ============================================================
# Theme — mint accent returned
# ============================================================

# Theme palettes and detection moved to wowusky.gui.theme.
from wowusky.gui.theme import (  # noqa: E402
    PALETTE_DARK, PALETTE_LIGHT, detect_system_theme, get_palette, set_theme_mode)


# ============================================================
# GUI Helpers
# ============================================================

# _safe_grab / _font_exists / UltraHiddenScrollbar / HoverScrollbar moved to wowusky.gui.
from wowusky.gui.context import AppContext  # noqa: E402
from wowusky.gui.dialogs import AddonDetailsDialog, SettingsDialog  # noqa: E402
from wowusky.gui.tabs import (  # noqa: E402
    BackupsTab, BrowseTab, CurseForgeTab, ImportTab, InstalledTab, LogTab, WeakAurasTab)
from wowusky.gui.fonts import (  # noqa: E402
    _font_exists, make_font_set, resolve_mono_family, resolve_sans_family)
from wowusky.gui.widgets import (  # noqa: E402, F401
    HoverScrollbar, UltraHiddenScrollbar, _safe_grab, make_button as _gui_make_button)

# ============================================================
# GUI
# ============================================================

def run_gui():
    """Launch the Tk GUI. The implementation lives in
    :mod:`wowusky.gui.main`; it is imported lazily here so that importing
    ``wowusky.app`` never triggers the (circular) star import in that module.
    """
    from wowusky.gui.main import run_gui as _run_gui
    return _run_gui()



# ============================================================
# Terminal mode
# ============================================================

def run_terminal():
    print(f"\n  ◆ {APP_NAME} v{__version__}\n")
    path = get_addons_path()
    if not path:
        installations = scan_wow_installations()
        if installations:
            for i, inst in enumerate(installations, 1):
                print(f"  [{i}] {inst['flavor_name']}")
                print(f"      {inst['addons_path']}")
            choice = input("\n  Select (number) or 'm': ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(installations):
                path = installations[int(choice) - 1]["addons_path"]
            else:
                path = input("  Path: ").strip()
        else:
            path = input("  Path: ").strip()
        if path:
            set_addons_path(path)

    sync_filesystem_with_db(path)
    installed = load_installed()
    flavor = get_current_flavor()
    print(f"\n  Path: {path}")
    # Show the human-readable name like the GUI does, with the internal
    # key in brackets so the two interfaces agree (B5).
    if flavor:
        print(f"  Flavor: {flavor_display_name(flavor)} [{flavor}]")
    else:
        print("  Flavor: unknown")
    print(f"  Installed: {len(installed)}\n")

    filtered = filter_catalog_by_flavor(ADDON_CATALOG, flavor) if flavor else ADDON_CATALOG
    for i, a in enumerate(filtered, 1):
        mark = "●" if a["id"] in installed else "○"
        print(f"  [{mark}] {i:2}. {a['name']:30} [{a['source']}]")

    print()
    choice = input("  Install (number / blank): ").strip()
    if not choice:
        pass  # blank = install nothing, expected
    elif choice.isdigit() and 1 <= int(choice) <= len(filtered):
        install_addon(filtered[int(choice) - 1], path, log=print)
    else:
        print(f"  ✗ invalid selection {choice!r} — "
              f"expected a number between 1 and {len(filtered)}")

    input("\n  Enter to exit…")


def main():
    use_gui = os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    try:
        if use_gui:
            try:
                run_gui()
            except ImportError:
                run_terminal()
        else:
            run_terminal()
    except KeyboardInterrupt:
        # Clean terminal exit when the app is closed with Ctrl+C.
        print("\n  wowusky closed.")


if __name__ == "__main__":
    main()
