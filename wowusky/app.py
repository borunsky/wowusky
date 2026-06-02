#!/usr/bin/env python3
"""
wowusky — minimalist WoW addon manager for Linux.

v0.4 highlights
---------------
The application has been split into reusable modules:

  * :mod:`wowusky.core`       — paths, config, profiles, HTTP, TOC, …
  * :mod:`wowusky.providers`  — Tukui, GitHub, WoWInterface, CurseForge, Wago
  * :mod:`wowusky.catalog`    — manifest-based addon list

This file owns the Tk GUI and the addon install/update orchestration.
It imports the shared helpers from :mod:`wowusky.core` and
:mod:`wowusky.catalog`. It does **not** yet import from
:mod:`wowusky.providers` — the GUI's install path still uses a set
of provider helpers defined locally here. Migrating that path onto
the shared provider registry is the v0.5 work item; the registry
itself is already exercised by :mod:`wowusky.tools.health_check`.

Functions kept here are either GUI plumbing, the install/update
orchestrator, or thin facades around the new core helpers that
preserve the call signatures the GUI code already uses.
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


def _load_addon_catalog_with_compat() -> list[dict]:
    """Load the manifest catalog and adapt it to the legacy shape used by
    this file's GUI code.

    The old inline catalog used ``source`` and provider-specific fields
    (``api_url``, ``download_url``, ``repo``, ``wowi_id``). The new
    manifest schema uses ``provider`` and the same field names. We
    forward both spellings so neither side has to change in lockstep.
    """
    out: list[dict] = []
    for a in _load_manifest_catalog():
        entry = dict(a)
        # provider ↔ source duality
        if "source" not in entry:
            entry["source"] = entry.get("provider", "")
        # Reconstruct tukui api_url/download_url if missing
        if entry["source"] == "tukui" and "api_url" not in entry:
            slug = entry.get("slug") or entry["id"]
            entry.setdefault("api_url",
                             f"https://api.tukui.org/v1/addon/{slug}")
            entry.setdefault("download_url",
                             f"https://api.tukui.org/v1/download/dev/{slug}/main")
        out.append(entry)
    return out


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
CACHE_TTL      = 300
HTTP_CACHE     = {}
DOWNLOAD_QUEUE = Queue()

WOW_SEARCH_PATHS = [
    "~/.local/share/Steam/steamapps/compatdata/*/pfx/drive_c/Program Files (x86)/World of Warcraft",
    "~/.local/share/Steam/steamapps/compatdata/*/pfx/drive_c/Program Files/World of Warcraft",
    "~/.steam/steam/steamapps/compatdata/*/pfx/drive_c/Program Files (x86)/World of Warcraft",
    "~/.steam/steam/steamapps/compatdata/*/pfx/drive_c/Program Files/World of Warcraft",
    "~/Games/world-of-warcraft/drive_c/Program Files (x86)/World of Warcraft",
    "~/Games/battlenet/drive_c/Program Files (x86)/World of Warcraft",
    "~/.wine/drive_c/Program Files (x86)/World of Warcraft",
    "~/.wine/drive_c/Program Files/World of Warcraft",
]


# Flavor compatibility map: what flavors does an addon for X also work on?
# anniversary (TBC) can use TBC and Classic addons

# Addon Catalog
# ============================================================
# flavors: list of flavor tags this addon supports
#   "all" = any flavor
#   "anniversary", "tbc", "vanilla", "classic", "mop_classic", "mop",
#   "retail", "mainline"
# ============================================================

# ADDON_CATALOG is now loaded from manifest files via wowusky.catalog.
# See wowusky/catalog/manifests/builtin.json
ADDON_CATALOG = _load_addon_catalog_with_compat()


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

def ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(INSTALLED_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(MANIFEST_DIR, exist_ok=True)

def _setup_file_logging():
    ensure_config_dir()
    logger = logging.getLogger(APP_NAME)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    path = os.path.join(LOG_DIR, time.strftime("wowusky-%Y-%m-%d.log"))
    handler = RotatingFileHandler(path, maxBytes=512 * 1024, backupCount=7, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger

LOGGER = None

def app_log(message, level="info"):
    global LOGGER
    if LOGGER is None:
        LOGGER = _setup_file_logging()
    getattr(LOGGER, level, LOGGER.info)(str(message))

def _read_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def _write_json(path, data):
    ensure_config_dir()
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_config():    return _read_json(CONFIG_FILE, {})
def save_config(c):   _write_json(CONFIG_FILE, c)
def load_wago():      return _read_json(WAGO_FILE, {"auras": {}})
def save_wago(d):     _write_json(WAGO_FILE, d)


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

def slugify_profile_name(name):
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", (name or "profile").strip().lower()).strip("_")
    return slug or "profile"

def infer_profile_from_path(path):
    flavor_key = None
    flavor_name = "WoW"
    interface = None
    for flv_dir, (name, key, iface) in WOW_FLAVORS.items():
        if path and flv_dir in path:
            flavor_key = key
            flavor_name = name
            interface = iface
            break
    if not flavor_key:
        flavor_key = "custom"
        flavor_name = "Custom"
    pid = slugify_profile_name(flavor_key if flavor_key != "custom" else os.path.basename(os.path.dirname(os.path.dirname(path or "custom"))))
    return {
        "id": pid,
        "name": flavor_name,
        "flavor": flavor_key,
        "addons_path": path or "",
        "wtf_path": os.path.abspath(os.path.join(path, "..", "..", "WTF")) if path else "",
        "interface": interface,
        "auto_update": False,
        "color_tag": "#5eead4",
    }



def _prefer_local_steam_path(path):
    """Return a display path that prefers ~/.local/share/Steam over ~/.steam aliases."""
    if not path:
        return path
    p = os.path.expanduser(path)
    local = os.path.expanduser("~/.local/share/Steam")
    steam = os.path.expanduser("~/.steam/steam")
    if p.startswith(steam):
        candidate = local + p[len(steam):]
        if os.path.exists(candidate):
            return candidate
    return p


def _profile_real_key(profile):
    """Stable dedupe key for profile/install dropdowns."""
    addons_path = (profile or {}).get("addons_path") or ""
    if not addons_path:
        return None
    return os.path.realpath(os.path.expanduser(addons_path))


def normalize_installations(installations):
    """Deduplicate WoW install entries everywhere, preferring ~/.local Steam paths."""
    dedup = {}
    order = []
    for inst in installations or []:
        key = os.path.realpath(os.path.expanduser(inst.get("addons_path", "")))
        if not key:
            continue
        fixed = dict(inst)
        fixed["addons_path"] = _prefer_local_steam_path(fixed.get("addons_path", ""))
        old = dedup.get(key)
        if old is None:
            dedup[key] = fixed
            order.append(key)
            continue
        old_local = "/.local/share/Steam/" in old.get("addons_path", "")
        new_local = "/.local/share/Steam/" in fixed.get("addons_path", "")
        if new_local and not old_local:
            dedup[key] = fixed
    return [dedup[k] for k in order]


def normalize_profiles_data(data):
    """Remove duplicate profiles that point to the same WoW AddOns directory.

    This also fixes old configs created before Steam alias dedupe existed, so the
    profile dropdown and settings picker no longer show both ~/.local and ~/.steam
    for the same installation.
    """
    if not data or not data.get("profiles"):
        return data

    profiles = data.get("profiles", {})
    active_old = data.get("active")
    by_real = {}
    active_real = _profile_real_key(profiles.get(active_old, {}))

    for pid, prof in profiles.items():
        prof = dict(prof or {})
        if prof.get("addons_path"):
            prof["addons_path"] = _prefer_local_steam_path(prof["addons_path"])
            if not prof.get("wtf_path"):
                prof["wtf_path"] = os.path.abspath(os.path.join(prof["addons_path"], "..", "..", "WTF"))
            else:
                prof["wtf_path"] = _prefer_local_steam_path(prof["wtf_path"])

        key = _profile_real_key(prof) or f"profile:{pid}"
        current = by_real.get(key)
        if current is None:
            by_real[key] = (pid, prof)
            continue

        cur_pid, cur_prof = current
        cur_local = "/.local/share/Steam/" in (cur_prof.get("addons_path") or "")
        new_local = "/.local/share/Steam/" in (prof.get("addons_path") or "")
        cur_active = cur_pid == active_old
        new_active = pid == active_old

        # Prefer the active profile unless the duplicate is a .steam alias and
        # the other entry points at the canonical .local path.
        replace = False
        if new_local and not cur_local or new_active and not cur_active and (new_local or cur_local == new_local):
            replace = True

        if replace:
            by_real[key] = (pid, prof)

    new_profiles = {pid: prof for pid, prof in by_real.values()}

    active = active_old if active_old in new_profiles else None
    if not active and active_real:
        for key, (pid, prof) in by_real.items():
            if key == active_real:
                active = pid
                break
    if not active:
        active = next(iter(new_profiles), "default")

    return {"active": active, "profiles": new_profiles}

def load_profiles():
    data = _read_json(PROFILES_FILE, None)
    if data and data.get("profiles"):
        normalized = normalize_profiles_data(data)
        if normalized != data:
            save_profiles(normalized)
        return normalized

    # No profiles.json yet. Migrate a pre-0.4 single-profile config if
    # one exists — that path was explicitly chosen by the user before,
    # so adopting it is not a surprise. But do NOT run autodetection
    # and silently write the first WoW install found into a profile
    # (B11): a fresh data dir must stay unconfigured until the user
    # picks a path via the GUI dialog or the terminal prompt. Those
    # call sites use scan_wow_installations() to *offer* choices.
    cfg = load_config()
    legacy_path = cfg.get("addons_path", "")
    if legacy_path:
        prof = infer_profile_from_path(legacy_path)
        profiles = {prof["id"]: prof}
        active = cfg.get("active_profile") or prof["id"]
        data = {"active": active if active in profiles else prof["id"],
                "profiles": profiles}
        save_profiles(data)
        return data

    # Truly unconfigured: return an empty set without persisting it.
    # get_addons_path() returns None, which triggers the path picker.
    return {"active": None, "profiles": {}}

def save_profiles(data):
    _write_json(PROFILES_FILE, data)
    cfg = load_config()
    cfg["active_profile"] = data.get("active")
    prof = data.get("profiles", {}).get(data.get("active"), {})
    if prof.get("addons_path"):
        cfg["addons_path"] = prof["addons_path"]
    save_config(cfg)

def get_active_profile_id():
    # Falls back to "default" when unconfigured so callers that build
    # filenames from the id never see None. Real profile work only
    # happens after a path is chosen, at which point a real id exists.
    return load_profiles().get("active") or "default"

def get_active_profile():
    data = load_profiles()
    return data.get("profiles", {}).get(data.get("active"), {})

def set_active_profile(profile_id):
    data = load_profiles()
    if profile_id in data.get("profiles", {}):
        data["active"] = profile_id
        save_profiles(data)

def add_or_update_profile(name, addons_path):
    data = load_profiles()
    prof = infer_profile_from_path(addons_path)
    prof["id"] = slugify_profile_name(name or prof["name"] or prof["flavor"])
    prof["name"] = name or prof["name"]
    base = prof["id"]
    i = 2
    while prof["id"] in data["profiles"] and data["profiles"][prof["id"]].get("addons_path") != addons_path:
        prof["id"] = f"{base}_{i}"; i += 1
    data["profiles"][prof["id"]] = prof
    data["active"] = prof["id"]
    save_profiles(data)
    return prof["id"]

def installed_file_for_profile(profile_id=None):
    profile_id = profile_id or get_active_profile_id()
    return os.path.join(INSTALLED_DIR, f"{profile_id}.json")

def load_installed(profile_id=None):
    path = installed_file_for_profile(profile_id)
    data = _read_json(path, None)
    if data is not None:
        return data
    # migrate legacy file into active profile once
    legacy = _read_json(INSTALLED_FILE, {})
    if legacy:
        save_installed(legacy, profile_id)
    return legacy or {}

def save_installed(d, profile_id=None):
    _write_json(installed_file_for_profile(profile_id), d)

def get_addons_path():
    # profiles.json is the source of truth. The load_config() fallback
    # only exists to read the legacy single-profile config.json field
    # written by pre-0.4.5 versions; new code never writes it.
    return get_active_profile().get("addons_path") or load_config().get("addons_path")

def set_addons_path(p):
    data = load_profiles()
    pid = data.get("active")
    if pid and pid in data.get("profiles", {}):
        # An active profile exists — update it in place.
        data["profiles"][pid].update(infer_profile_from_path(p))
        data["profiles"][pid]["id"] = pid
        save_profiles(data)
    else:
        # Unconfigured (B11 leaves a fresh data dir with no profiles).
        # Create one rather than silently doing nothing — otherwise the
        # path is "set" but no profile carries it, get_current_flavor()
        # returns None and the catalog is shown unfiltered (B12).
        add_or_update_profile(infer_profile_from_path(p).get("name"), p)
    # Do NOT mirror the path into config.json. Storing it in both
    # config.json and profiles.json (B9) created two sources of truth
    # that could silently diverge. If an old config.json still carries
    # the legacy field, drop it so it can't shadow profiles.json later.
    c = load_config()
    if "addons_path" in c:
        del c["addons_path"]
        save_config(c)

def is_dry_run():
    return bool(load_config().get("dry_run", False))

def set_dry_run(value):
    c = load_config(); c["dry_run"] = bool(value); save_config(c)

def get_curseforge_api_key():
    return load_config().get("curseforge_api_key") or os.environ.get("CURSEFORGE_API_KEY", "")

def set_curseforge_api_key(key):
    c = load_config()
    key = (key or "").strip()
    if key:
        c["curseforge_api_key"] = key
    else:
        c.pop("curseforge_api_key", None)
    save_config(c)

def get_current_flavor():
    """Returns flavor key (anniversary, vanilla, etc.) of active profile."""
    prof = get_active_profile()
    if prof.get("flavor") and prof.get("flavor") != "custom":
        return prof.get("flavor")
    p = get_addons_path()
    if not p: return None
    for flv_dir, (name, key, _) in WOW_FLAVORS.items():
        if flv_dir in p:
            return key
    return None

def get_compatible_flavors():
    """List of flavor tags an addon needs to declare to show for current flavor."""
    cur = get_current_flavor()
    if not cur: return None
    return FLAVOR_COMPATIBILITY.get(cur, [cur])


# ============================================================
# WoW Detection
# ============================================================

def _display_path_preference(path):
    """Prefer the canonical Steam path under ~/.local over ~/.steam duplicates."""
    p = os.path.expanduser(path)
    local = os.path.expanduser("~/.local/share/Steam")
    steam = os.path.expanduser("~/.steam/steam")
    if p.startswith(steam):
        candidate = local + p[len(steam):]
        if os.path.exists(candidate):
            return candidate
    return p


def scan_wow_installations():
    """Find WoW installations and hide duplicate Steam aliases.

    Steam on Linux often exposes the same compatdata tree through both
    ~/.local/share/Steam and ~/.steam/steam.  We compare real paths and keep
    only one entry, preferring the ~/.local/share/Steam display path.
    """
    found = []
    seen = set()

    for pattern in WOW_SEARCH_PATHS:
        for wow_dir in glob.glob(os.path.expanduser(pattern)):
            if not os.path.isdir(wow_dir):
                continue

            wow_real = os.path.realpath(wow_dir)

            for flavor, (name, key, _) in WOW_FLAVORS.items():
                fp = os.path.join(wow_dir, flavor)
                if not os.path.isdir(fp):
                    continue

                addons_real = os.path.realpath(os.path.join(fp, "Interface", "AddOns"))
                dedupe_key = (wow_real, flavor, addons_real)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)

                display_fp = _display_path_preference(fp)
                found.append({
                    "flavor": flavor,
                    "flavor_name": name,
                    "flavor_key": key,
                    "addons_path": os.path.join(display_fp, "Interface", "AddOns"),
                })

    found = normalize_installations(found)
    found.sort(key=lambda x: (0 if "/.local/share/Steam/" in x["addons_path"] else 1, x["flavor_name"], x["addons_path"]))
    return found


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
    if not addons_path or not os.path.isdir(addons_path):
        return

    installed = load_installed()

    # Cleanup stale entries
    for aid in list(installed.keys()):
        entry = installed[aid]
        if not entry.get("folders"): continue
        primary = entry["folders"][0]
        if not os.path.isdir(os.path.join(addons_path, primary)):
            del installed[aid]

    try:
        fs_folders = [f for f in os.listdir(addons_path)
                      if os.path.isdir(os.path.join(addons_path, f))
                      and not f.startswith(".")]
    except Exception:
        return

    known_folders = set()
    for entry in installed.values():
        for f in entry.get("folders", []):
            known_folders.add(f)

    catalog_by_folder = {}
    catalog_by_lower = {}
    for addon in ADDON_CATALOG:
        for folder in addon["folders"]:
            catalog_by_folder[folder] = addon
            catalog_by_lower[folder.lower()] = addon

    processed = set(known_folders)

    for folder in sorted(fs_folders):
        if folder in processed: continue
        full = os.path.join(addons_path, folder)
        toc = read_toc_info(full)
        if not toc: continue

        catalog_addon = catalog_by_folder.get(folder) or catalog_by_lower.get(folder.lower())
        if catalog_addon and catalog_addon["id"] not in installed:
            actual_folders = [f for f in catalog_addon["folders"]
                              if os.path.isdir(os.path.join(addons_path, f))]
            installed[catalog_addon["id"]] = {
                "name": catalog_addon["name"],
                "version": toc.get("version") or "unknown",
                "folders": actual_folders,
                "source": catalog_addon["source"],
                "interface": toc.get("interface"),
                "discovered": True,
            }
            for f in actual_folders:
                processed.add(f)
            continue

        # External addon
        related = [folder]
        for other in fs_folders:
            if other != folder and other.startswith(folder + "_"):
                if other not in processed:
                    related.append(other)

        addon_id = "fs_" + folder.lower().replace(" ", "_")
        if addon_id in installed: continue

        installed[addon_id] = {
            "name": toc.get("title") or folder,
            "version": toc.get("version") or "unknown",
            "folders": related,
            "source": "external",
            "interface": toc.get("interface"),
            "discovered": True,
        }
        for f in related:
            processed.add(f)

    save_installed(installed)


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

from wowusky.providers import github_fns as _github_fns  # noqa: E402
_github_fns.get_current_flavor = lambda: get_current_flavor()
from wowusky.providers.github_fns import (  # noqa: E402
    _github_branch_exists, _github_pick_asset, github_default_branch,
    github_releases, github_repo_for_addon, github_repo_url, github_tags,
    github_url, github_version)
from wowusky.providers.wowi_fns import (  # noqa: E402
    wowi_info, wowi_page_url, wowi_url, wowi_version)

from wowusky.providers.curseforge_fns import (  # noqa: E402
    _cf_file_versions, cf_slug_from_ref, curseforge_file_matches_flavor,
    curseforge_headers, curseforge_web_url, curseforge_web_version)

from wowusky.providers import curseforge_fns as _cf_fns  # noqa: E402
_cf_fns.get_current_flavor = lambda: get_current_flavor()
_cf_fns.get_curseforge_api_key = lambda: get_curseforge_api_key()

def internal_wac_version(a):
    """WeakAurasCompanion is generated locally — version = number of auras."""
    wago = load_wago()
    return f"{len(wago.get('auras', {}))} auras"

def internal_wac_url(a):
    return None  # never downloaded


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
    curseforge_manual_url as _cf_manual_url, curseforge_mod_from_ref, curseforge_mod_summary,
    curseforge_pick_file, curseforge_search, curseforge_url_from_installed,
    curseforge_version_from_installed,
    install_curseforge as _cf_install_curseforge,
    install_curseforge_dependencies as _cf_install_deps,
    CURSEFORGE_API_BASE, CURSEFORGE_GAME_ID,
)

CF_WEB_VERSION_TYPE_HINTS = {
    # CurseForge web URLs use gameVersionTypeId. 67408 currently opens the
    # Classic flavor listing; for TBC Anniversary we also seed the query with
    # TBC terms so the browser starts in the correct area even when CF changes
    # the exact flavor id again.
    "retail": 517,
    "ptr": 517,
    "anniversary": 67408,
    "vanilla": 67408,
    "mop_classic": 73246,
}

CF_WEB_SEARCH_HINT = {
    "anniversary": "tbc classic anniversary",
    "vanilla": "classic era",
    "mop_classic": "mop classic",
    "retail": "",
    "ptr": "",
}


def current_cf_web_version_type():
    return CF_WEB_VERSION_TYPE_HINTS.get(get_current_flavor() or "retail")


def _cached_json(cache_key, loader):
    now = time.time()
    item = HTTP_CACHE.get(cache_key)
    if item and now - item[0] < CACHE_TTL:
        return item[1]
    data = loader()
    HTTP_CACHE[cache_key] = (now, data)
    return data


def retry(fn, attempts=3, delay=0.7):
    last = None
    for _ in range(attempts):
        try:
            return fn()
        except Exception as e:
            last = e
            time.sleep(delay)
    raise last


# curseforge_json and curseforge_api_diagnose imported from curseforge_fns.


def curseforge_search_url(query=""):
    q = (query or "").strip()
    slug = cf_slug_from_ref(q)
    if slug and ("/" in q or "curseforge.com" in q):
        return "https://www.curseforge.com/wow/addons/" + urllib.parse.quote(slug)

    flavor = get_current_flavor() or "retail"
    params = {"class": "addons", "page": 1, "sortBy": "popularity"}
    vt = current_cf_web_version_type()
    if vt:
        params["gameVersionTypeId"] = vt

    hint = CF_WEB_SEARCH_HINT.get(flavor, "")
    search = " ".join(x for x in (q, hint) if x).strip()
    if search:
        params["search"] = search

    return "https://www.curseforge.com/wow/search?" + urllib.parse.urlencode(params)


def curseforge_files_url(slug_or_url=""):
    slug = cf_slug_from_ref(slug_or_url)
    if slug:
        return f"https://www.curseforge.com/wow/addons/{urllib.parse.quote(slug)}/files/all"
    return curseforge_search_url(slug_or_url)


def open_in_browser(url):
    if not url:
        return False
    try:
        webbrowser.open(url)
        return True
    except Exception:
        return False


def downloads_dir():
    cfg = os.environ.get("XDG_DOWNLOAD_DIR")
    if cfg:
        return os.path.expanduser(cfg)
    return os.path.expanduser("~/Downloads")


def scan_download_zips(limit=25):
    d = downloads_dir()
    if not os.path.isdir(d):
        return []
    files = []
    for name in os.listdir(d):
        if name.lower().endswith(".zip"):
            path = os.path.join(d, name)
            try:
                files.append((os.path.getmtime(path), path))
            except OSError:
                pass
    files.sort(reverse=True)
    return [p for _, p in files[:limit]]


def newest_download_zip():
    zips = scan_download_zips(limit=1)
    return zips[0] if zips else ""


def import_zip_file(zip_path, addons_path, name=None, source="manual", log=print, curseforge_slug=None, curseforge_url=None):
    """Import a manual / CurseForge ZIP and record it in the active profile.

    Extraction and entry-building live in ``wowusky.core.installer``; this
    wrapper only adds the profile-aware ``installed.json`` write.
    """
    addon_id, entry = build_import_entry(
        zip_path, addons_path, name=name, source=source,
        curseforge_slug=curseforge_slug, curseforge_url=curseforge_url, log=log,
    )
    inst = load_installed()
    inst[addon_id] = entry
    save_installed(inst)
    return addon_id


# curseforge_manual_latest, curseforge_manual_url, curseforge_search,
# curseforge_mod_from_ref, curseforge_get_files, curseforge_pick_file,
# curseforge_download_url, curseforge_mod_summary, curseforge_version_from_installed,
# curseforge_url_from_installed imported from curseforge_fns.


def curseforge_manual_url(entry):
    """Thin wrapper — passes flavor-aware URL builders into the core helper."""
    return _cf_manual_url(entry, files_url_fn=curseforge_files_url, search_url_fn=curseforge_search_url)


def install_curseforge(ref_or_mod, addons_path, log=print, progress=None, install_deps=True):
    """Thin wrapper — wires profile I/O into the core CurseForge install."""
    return _cf_install_curseforge(
        ref_or_mod, addons_path,
        http_download=http_download,
        load_installed=load_installed,
        save_installed=save_installed,
        log=log, progress=progress, install_deps=install_deps,
    )


def install_curseforge_dependencies(file_data, addons_path, log=print, seen=None):
    """Thin wrapper — wires profile I/O into the dependency installer."""
    return _cf_install_deps(
        file_data, addons_path,
        http_download=http_download,
        load_installed=load_installed,
        save_installed=save_installed,
        log=log, seen=seen,
    )


SOURCES = {
    "tukui":        (tukui_version, tukui_url),
    "github":       (github_version, github_url),
    "wowi":         (wowi_version, wowi_url),
    "internal_wac": (internal_wac_version, internal_wac_url),
    "curseforge":   (lambda a: curseforge_version_from_installed(a), lambda a: curseforge_url_from_installed(a)),
    "curseforge_web": (lambda a: "manual", lambda a: ""),
    "curseforge_manual": (lambda a: curseforge_manual_latest(a), lambda a: curseforge_manual_url(a)),
}

def get_latest_version(a):
    try: return SOURCES[a["source"]][0](a)
    except Exception: return None

def get_download_url(a):
    return SOURCES[a["source"]][1](a)


# ============================================================
# Version comparison
# ============================================================

# versions_equal is imported from wowusky.core.versions.
# ============================================================
# Wago.io / WeakAuras Companion
# ============================================================

from wowusky.providers.wago_fns import (  # noqa: E402
    WAGO_SLUG_RX, parse_wago_url, wago_fetch_encoded, wago_fetch_info)

def wago_add(slug, name=None, note=None):
    """Add an aura to tracking list."""
    wago = load_wago()
    if "auras" not in wago:
        wago["auras"] = {}

    info = wago_fetch_info(slug) or {}
    if not name:
        name = info.get("name") or slug

    wago["auras"][slug] = {
        "name": name,
        "slug": slug,
        "version": info.get("version") or info.get("wagoVersion") or 1,
        "note": note or info.get("note", ""),
        "type": info.get("type", "WeakAura"),
        "url": f"https://wago.io/{slug}",
        "added_at": "now",
    }
    save_wago(wago)
    return wago["auras"][slug]


def wago_remove(slug):
    wago = load_wago()
    if slug in wago.get("auras", {}):
        del wago["auras"][slug]
        save_wago(wago)
        return True
    return False


def wago_check_updates():
    """Fetch current versions from wago for all tracked auras."""
    wago = load_wago()
    updates = []
    for slug, entry in wago.get("auras", {}).items():
        info = wago_fetch_info(slug)
        if info:
            latest = info.get("version") or info.get("wagoVersion") or 1
            try:
                if int(latest) > int(entry.get("version", 1)):
                    updates.append(slug)
                entry["latest_version"] = latest
            except (ValueError, TypeError):
                entry["latest_version"] = latest
    save_wago(wago)
    return updates


def wago_search(query, limit=20):
    """Search wago.io for auras."""
    try:
        q = urllib.parse.quote(query)
        url = f"https://data.wago.io/api/search/{q}?limit={limit}"
        return http_get_json(url)
    except Exception:
        return None


def get_wtf_path():
    prof = get_active_profile()
    if prof.get("wtf_path"):
        return prof.get("wtf_path")
    ap = get_addons_path()
    if ap:
        return os.path.abspath(os.path.join(ap, "..", "..", "WTF"))
    return ""


def find_weakauras_savedvariables(wtf_path=None):
    """Return WeakAuras SavedVariables files for the active WoW profile."""
    wtf_path = wtf_path or get_wtf_path()
    if not wtf_path or not os.path.isdir(wtf_path):
        return []
    patterns = [
        os.path.join(wtf_path, "Account", "*", "SavedVariables", "WeakAuras.lua"),
        os.path.join(wtf_path, "Account", "*", "SavedVariables", "WeakAuras.lua.bak"),
    ]
    files = []
    for pattern in patterns:
        files.extend(glob.glob(pattern))
    return sorted(set(files), key=lambda p: os.path.getmtime(p), reverse=True)


def extract_wago_slugs_from_text(text):
    """Extract Wago slugs from WeakAuras SavedVariables text.

    WeakAuras stores Wago data in different shapes over time, so we use a few
    conservative patterns instead of a fragile Lua parser.
    """
    slugs = set()
    for m in re.finditer(r'wago\.io/([A-Za-z0-9_-]{3,})', text):
        slugs.add(m.group(1))
    key_patterns = [
        r'\["wagoID"\]\s*=\s*"([A-Za-z0-9_-]{3,})"',
        r'\["wagoId"\]\s*=\s*"([A-Za-z0-9_-]{3,})"',
        r'\["wago"\]\s*=\s*"([A-Za-z0-9_-]{3,})"',
        r'wagoID\s*=\s*"([A-Za-z0-9_-]{3,})"',
        r'wagoId\s*=\s*"([A-Za-z0-9_-]{3,})"',
    ]
    for rx in key_patterns:
        for m in re.finditer(rx, text):
            slugs.add(m.group(1))
    return sorted(slugs)


def import_existing_weakauras_from_savedvariables(log=print):
    files = find_weakauras_savedvariables()
    if not files:
        return {"added": 0, "existing": 0, "failed": 0, "files": [], "slugs": []}
    wago = load_wago()
    wago.setdefault("auras", {})
    all_slugs = []
    for path in files:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            all_slugs.extend(extract_wago_slugs_from_text(content))
        except Exception as exc:
            log(f"  ! could not read {path}: {exc}")
    slugs = sorted(set(all_slugs))
    added = existing = failed = 0
    for slug in slugs:
        if slug in wago.get("auras", {}):
            existing += 1
            continue
        try:
            entry = wago_add(slug)
            if entry:
                added += 1
            else:
                failed += 1
        except Exception as exc:
            failed += 1
            log(f"  ! wago.io/{slug}: {exc}")
    return {"added": added, "existing": existing, "failed": failed, "files": files, "slugs": slugs}


def generate_wac_companion(addons_path):
    """Generate WeakAurasCompanion addon files from tracked wago data."""
    if not addons_path: return False

    wago = load_wago()
    auras = wago.get("auras", {})

    companion_dir = os.path.join(addons_path, "WeakAurasCompanion")
    os.makedirs(companion_dir, exist_ok=True)

    # ── TOC file ──
    toc_path = os.path.join(companion_dir, "WeakAurasCompanion.toc")
    interface = 120001  # default retail
    flavor = get_current_flavor()
    for flv_dir, (n, k, iface) in WOW_FLAVORS.items():
        if k == flavor:
            interface = iface
            break

    with open(toc_path, "w") as f:
        f.write(f"""## Interface: {interface}
## Title: WeakAuras Companion
## Notes: Generated by wowusky v{__version__}
## Author: wowusky
## Version: 1.0
## SavedVariables: WeakAurasCompanionDB
## Dependencies: WeakAuras

data.lua
init.lua
""")

    # ── data.lua ── (contains the actual aura data)
    data_path = os.path.join(companion_dir, "data.lua")
    with open(data_path, "w") as f:
        f.write("-- Generated by wowusky\n")
        f.write("local _, addon = ...\n")
        f.write("addon.data = {\n")
        f.write('  ["WeakAuras"] = {\n')
        f.write('    slugs = {\n')

        for slug, entry in auras.items():
            encoded = wago_fetch_encoded(slug)
            if not encoded: continue
            # Escape Lua string
            encoded_escaped = encoded.replace("\\", "\\\\").replace('"', '\\"')
            name_escaped    = entry["name"].replace('"', '\\"')
            f.write(f'      ["{slug}"] = {{\n')
            f.write(f'        name = "{name_escaped}",\n')
            f.write('        author = "wowusky",\n')
            f.write(f'        encoded = "{encoded_escaped}",\n')
            f.write(f'        wagoVersion = "{entry.get("version", 1)}",\n')
            f.write(f'        wagoSemver = "{entry.get("version", 1)}",\n')
            f.write(f'        versionNote = "{entry.get("note", "")}",\n')
            f.write('        source = "Wago",\n')
            f.write('        logo = "Interface\\\\Icons\\\\Inv_misc_questionmark",\n')
            f.write('      },\n')

        f.write('    },\n')
        f.write('    uids = {},\n')
        f.write('    ids = {},\n')
        f.write('    stash = {},\n')
        f.write('  },\n')
        f.write("}\n")

    # ── init.lua ──
    init_path = os.path.join(companion_dir, "init.lua")
    with open(init_path, "w") as f:
        f.write("""-- WeakAurasCompanion init
local _, addon = ...

local frame = CreateFrame("Frame")
frame:RegisterEvent("ADDON_LOADED")
frame:SetScript("OnEvent", function(self, event, name)
    if name == "WeakAurasCompanion" then
        if WeakAuras and addon.data then
            for addonName, data in pairs(addon.data) do
                if WeakAuras.AddCompanionData then
                    WeakAuras.AddCompanionData(data)
                end
            end
        end
    end
end)
""")

    # Mark as installed
    installed = load_installed()
    installed["wac"] = {
        "name": "WeakAuras Companion",
        "version": f"{len(auras)} auras",
        "folders": ["WeakAurasCompanion"],
        "source": "internal_wac",
        "discovered": False,
    }
    save_installed(installed)
    return True


# ============================================================
# Provider status / manual fallbacks
# ============================================================

SEMI_MANAGED_SOURCES = {"curseforge_web", "curseforge_manual", "wowi"}


def addon_provider_page(addon):
    src = addon.get("source")
    if src == "curseforge_web":
        return curseforge_files_url(addon.get("curseforge_slug", addon.get("id", "")))
    if src == "curseforge_manual":
        return curseforge_manual_url(addon)
    if src == "wowi":
        return wowi_page_url(addon)
    if src == "github":
        return github_repo_url(github_repo_for_addon(addon))
    if src == "tukui":
        return addon.get("download_url") or addon.get("api_url")
    return addon.get("url") or ""


def provider_action_label(addon, installed=False):
    src = addon.get("source")
    if src == "curseforge_web":
        return "Open CF"
    if src == "curseforge_manual":
        return "Open update"
    if src == "wowi":
        return "Install" if not installed else "Update"
    if src == "github":
        return "Install" if not installed else "Update"
    return "Install" if not installed else "Update"


# sha256_file is imported from wowusky.core.zipper (single source of truth).

def _safe_addon_id(addon_id):
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", addon_id)

def _addon_backup_meta(zip_path):
    meta = {}
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in ("wowusky-addon-backup.json", "wowusky-backup.json"):
                if name in zf.namelist():
                    meta = json.loads(zf.read(name).decode("utf-8"))
                    break
    except Exception:
        meta = {}
    return meta if isinstance(meta, dict) else {}

def list_addon_backups(addon_id):
    profile_id = get_active_profile_id()
    safe = _safe_addon_id(addon_id)
    target_dir = Path(BACKUP_DIR) / profile_id
    backups = []
    if target_dir.exists():
        for z in target_dir.glob(f"{safe}-*.zip"):
            try:
                meta = _addon_backup_meta(str(z))
                entry = meta.get("entry", {}) if isinstance(meta.get("entry"), dict) else {}
                backups.append({
                    "path": str(z),
                    "name": z.name,
                    "mtime": z.stat().st_mtime,
                    "size": z.stat().st_size,
                    "version": entry.get("version") or meta.get("version") or "unknown",
                    "source": entry.get("source") or meta.get("source") or "backup",
                    "folders": entry.get("folders") or meta.get("folders") or [],
                    "entry": entry,
                })
            except OSError:
                pass
    backups.sort(key=lambda x: x["mtime"], reverse=True)
    return backups

# _append_version_history is imported from wowusky.core.installer (single source of truth).

def backup_addon_folders(addon_id, entry, addons_path, log=print):
    if not entry or not entry.get("folders") or not addons_path:
        return None
    existing = [f for f in entry.get("folders", []) if os.path.exists(os.path.join(addons_path, f))]
    if not existing:
        return None
    profile_id = get_active_profile_id()
    ts = time.strftime("%Y%m%d-%H%M%S")
    safe = _safe_addon_id(addon_id)
    target_dir = os.path.join(BACKUP_DIR, profile_id)
    os.makedirs(target_dir, exist_ok=True)
    zip_base = os.path.join(target_dir, f"{safe}-{ts}")
    if is_dry_run():
        log(f"  dry-run: would backup {', '.join(existing)}")
        return zip_base + ".zip"
    with zipfile.ZipFile(zip_base + ".zip", "w", zipfile.ZIP_DEFLATED) as zf:
        meta = {
            "type": "addon",
            "addon_id": addon_id,
            "profile": profile_id,
            "created_at": ts,
            "version": entry.get("version"),
            "source": entry.get("source"),
            "folders": existing,
            "entry": entry,
        }
        zf.writestr("wowusky-addon-backup.json", json.dumps(meta, indent=2))
        for folder in existing:
            root_path = os.path.join(addons_path, folder)
            for root, dirs, files in os.walk(root_path):
                for name in files:
                    fp = os.path.join(root, name)
                    arc = os.path.relpath(fp, addons_path)
                    zf.write(fp, arc)
    log(f"  ↶ backup: {os.path.basename(zip_base)}.zip")
    backups = sorted(Path(target_dir).glob(f"{safe}-*.zip"), key=lambda x: x.stat().st_mtime, reverse=True)
    for old in backups[10:]:
        try: old.unlink()
        except Exception: pass
    return zip_base + ".zip"

def latest_backup_for_addon(addon_id):
    backups = list_addon_backups(addon_id)
    return backups[0]["path"] if backups else None

def rollback_addon_to_backup(addon_id, backup, addons_path, log=print):
    if not backup:
        log("  ✗ no backup selected")
        return False
    if not os.path.isfile(backup):
        log("  ✗ backup ZIP not found")
        return False
    installed = load_installed()
    entry = installed.get(addon_id)
    if entry:
        for folder in entry.get("folders", []):
            p = os.path.join(addons_path, folder)
            if os.path.exists(p):
                if is_dry_run():
                    log(f"  dry-run: would remove {folder}")
                else:
                    shutil.rmtree(p)
    if is_dry_run():
        log(f"  dry-run: would restore {os.path.basename(backup)}")
        return True
    with zipfile.ZipFile(backup, "r") as zf:
        members = [n for n in zf.namelist() if not n.startswith("wowusky-")]
        for n in members:
            zf.extract(n, addons_path)
    meta = _addon_backup_meta(backup)
    restored_entry = meta.get("entry") if isinstance(meta.get("entry"), dict) else None
    if restored_entry:
        current_entry = installed.get(addon_id)
        restored_entry = dict(restored_entry)
        restored_entry["restored_from"] = backup
        restored_entry["restored_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _append_version_history(restored_entry, current_entry, backup_path=backup, action="restore")
        installed[addon_id] = restored_entry
        save_installed(installed)
    log(f"  ✓ restored {os.path.basename(backup)}")
    return True

def rollback_addon(addon_id, addons_path, log=print):
    backup = latest_backup_for_addon(addon_id)
    if not backup:
        log("  ✗ no backup found")
        return False
    return rollback_addon_to_backup(addon_id, backup, addons_path, log)


FULL_BACKUP_DIR_NAME = "full"

def full_backup_dir():
    profile_id = get_active_profile_id()
    path = os.path.join(BACKUP_DIR, profile_id, FULL_BACKUP_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path

def list_full_backups():
    d = Path(full_backup_dir())
    items = []
    for z in d.glob("wowusky-full-*.zip"):
        try:
            items.append({"path": str(z), "name": z.name, "mtime": z.stat().st_mtime, "size": z.stat().st_size})
        except OSError:
            pass
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items

def create_full_backup(log=print):
    """Create a full profile backup containing Interface/AddOns and WTF settings."""
    prof = get_active_profile()
    addons_path = prof.get("addons_path") or get_addons_path()
    wtf_path = prof.get("wtf_path") or get_wtf_path()
    if not addons_path or not os.path.isdir(addons_path):
        raise RuntimeError("AddOns path is not configured")
    ts = time.strftime("%Y%m%d-%H%M%S")
    out = os.path.join(full_backup_dir(), f"wowusky-full-{get_active_profile_id()}-{ts}.zip")
    log(f"⟩ creating full backup for {prof.get('name', get_active_profile_id())}")
    if is_dry_run():
        log(f"  dry-run: would write {out}")
        return out
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        meta = {
            "profile": get_active_profile_id(),
            "created_at": ts,
            "addons_path": addons_path,
            "wtf_path": wtf_path,
            "installed": load_installed(),
        }
        zf.writestr("wowusky-backup.json", json.dumps(meta, indent=2))
        for label, base in (("AddOns", addons_path), ("WTF", wtf_path)):
            if not base or not os.path.isdir(base):
                continue
            for root, dirs, files in os.walk(base):
                for name in files:
                    fp = os.path.join(root, name)
                    arc = os.path.join(label, os.path.relpath(fp, base))
                    try:
                        zf.write(fp, arc)
                    except OSError:
                        pass
    log(f"  ✓ full backup: {os.path.basename(out)}")
    return out

def restore_full_backup(zip_path, log=print):
    prof = get_active_profile()
    addons_path = prof.get("addons_path") or get_addons_path()
    wtf_path = prof.get("wtf_path") or get_wtf_path()
    if not zip_path or not os.path.isfile(zip_path):
        raise RuntimeError("Backup ZIP not found")
    if not addons_path or not os.path.isdir(addons_path):
        raise RuntimeError("AddOns path is not configured")
    if is_dry_run():
        log(f"  dry-run: would restore {os.path.basename(zip_path)}")
        return True
    log(f"⟩ restoring full backup {os.path.basename(zip_path)}")
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp)
        addons_src = os.path.join(tmp, "AddOns")
        wtf_src = os.path.join(tmp, "WTF")
        if os.path.isdir(addons_src):
            os.makedirs(addons_path, exist_ok=True)
            for name in os.listdir(addons_src):
                src = os.path.join(addons_src, name)
                dst = os.path.join(addons_path, name)
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
        if os.path.isdir(wtf_src) and wtf_path:
            os.makedirs(wtf_path, exist_ok=True)
            # Preserve unknown files; overwrite backed-up settings.
            for root, dirs, files in os.walk(wtf_src):
                rel = os.path.relpath(root, wtf_src)
                dst_root = os.path.join(wtf_path, rel) if rel != "." else wtf_path
                os.makedirs(dst_root, exist_ok=True)
                for name in files:
                    shutil.copy2(os.path.join(root, name), os.path.join(dst_root, name))
        meta_path = os.path.join(tmp, "wowusky-backup.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
                if isinstance(meta.get("installed"), dict):
                    save_installed(meta["installed"])
            except Exception:
                pass
    log("  ✓ full backup restored")
    return True

# ============================================================
# Install / Uninstall
# ============================================================

def install_addon(addon, addons_path, log=print, progress=None):
    """Thin wrapper — wires profile/config state into the core install logic."""
    def _generate_wac(ap):
        ok = generate_wac_companion(ap)
        if ok:
            log(f"  ✓ generated with {len(load_wago().get('auras', {}))} auras\n")
        return ok
    return _core_install_addon(
        addon, addons_path,
        profile_id=get_active_profile_id(),
        get_latest_version=get_latest_version,
        get_download_url=get_download_url,
        load_installed=load_installed,
        save_installed=save_installed,
        backup_addon_folders=backup_addon_folders,
        http_download=http_download,
        is_dry_run=is_dry_run,
        app_log=app_log,
        addon_provider_page=addon_provider_page,
        open_in_browser=open_in_browser,
        generate_wac_companion=_generate_wac,
        log=log,
        progress=progress,
    )


def extract_zip(zip_path, addons_path, addon=None, log=None):
    """Thin wrapper around :func:`wowusky.core.zipper.extract_addon_zip`.

    The ``addon`` / ``log`` parameters are retained for the existing GUI
    call sites; extraction logic now lives in ``wowusky.core.zipper`` as
    the single source of truth (shared with ``health_check`` and tests).
    """
    return extract_addon_zip(zip_path, addons_path)


def uninstall_addon(addon_id, addons_path, log=print):
    """Thin wrapper — wires profile/config state into the core uninstall logic."""
    return _core_uninstall_addon(
        addon_id, addons_path,
        load_installed=load_installed,
        save_installed=save_installed,
        backup_addon_folders=backup_addon_folders,
        is_dry_run=is_dry_run,
        app_log=app_log,
        profile_id=get_active_profile_id(),
        log=log,
    )

def find_addon_by_id(aid):
    return next((a for a in ADDON_CATALOG if a["id"] == aid), None)

def get_categories():
    return sorted({a["category"] for a in ADDON_CATALOG})


def filter_catalog_by_flavor(addons, current_flavor):
    """Filter catalog to only show addons compatible with current flavor.

    Uses the shared :func:`wowusky.core.flavors.is_compatible` helper so
    the rules match what the GUI displays elsewhere.
    """
    if not current_flavor:
        return addons
    return [a for a in addons
            if is_compatible(a.get("flavors", ["all"]), current_flavor)]


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
from wowusky.gui.dialogs import SettingsDialog  # noqa: E402
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
        dlg = tk.Toplevel(root)
        dlg.title(addon.get("name", "Addon"))
        dlg.configure(bg=C["bg"])
        dlg.geometry("560x520")
        dlg.minsize(420, 360)
        dlg.transient(root)
        _safe_grab(dlg)
        head = tk.Frame(dlg, bg=C["bg"])
        head.pack(fill="x", padx=16, pady=(16, 8))
        tk.Label(head, text=addon.get("name", "Addon"), bg=C["bg"], fg=C["text"], font=FONT_HEAD).pack(anchor="w")
        tk.Label(head, text=f"{addon.get('author','')} · {addon.get('category','')} · {SOURCE_LABEL.get(addon.get('source'), addon.get('source',''))}", bg=C["bg"], fg=C["text_muted"], font=FONT_SM).pack(anchor="w", pady=(4,0))
        tk.Label(dlg, text=addon.get("description", ""), bg=C["bg"], fg=C["text_dim"], font=FONT_SM, wraplength=500, justify="left").pack(anchor="w", fill="x", padx=16, pady=(0, 14))
        btns = tk.Frame(dlg, bg=C["bg"])
        btns.pack(fill="x", padx=16, pady=(0, 12))
        make_button(btns, "Install latest", lambda a=addon: (dlg.destroy(), trigger_install(a)), variant="primary").pack(side="left", padx=(0,8))
        page = provider_page_url(addon)
        if page:
            make_button(btns, "Open page", lambda url=page: open_in_browser(url), variant="outline").pack(side="left", padx=(0,8))
        tk.Label(dlg, text="Available versions", bg=C["bg"], fg=C["text"], font=FONT_SECTION).pack(anchor="w", padx=16)
        list_wrap = tk.Frame(dlg, bg=C["surface"])
        list_wrap.pack(fill="both", expand=True, padx=16, pady=(8, 16))
        loading = tk.Label(list_wrap, text="Loading version choices…", bg=C["surface"], fg=C["text_muted"], font=FONT_SM)
        loading.pack(padx=12, pady=12, anchor="w")
        def fill_versions():
            choices = []
            if addon.get("source") == "github":
                choices = github_version_choices(addon)
            def ui():
                for w in list_wrap.winfo_children(): w.destroy()
                if not choices:
                    msg = "Direct version selection is only available when the provider exposes downloadable ZIP versions. For CurseForge/WoWInterface use Open page + ZIP import."
                    tk.Label(list_wrap, text=msg, bg=C["surface"], fg=C["text_dim"], font=FONT_SM, wraplength=480, justify="left").pack(anchor="w", padx=12, pady=12)
                    return
                for ch in choices:
                    row = tk.Frame(list_wrap, bg=C["surface"])
                    row.pack(fill="x", padx=8, pady=4)
                    tk.Label(row, text=ch["label"], bg=C["surface"], fg=C["text"], font=FONT_SM, anchor="w").pack(side="left", fill="x", expand=True)
                    make_button(row, "Install", lambda c=ch: (dlg.destroy(), install_direct_zip_for_addon(addon, c["url"], c["label"])), variant="primary", compact=True).pack(side="right")
            root.after(0, ui)
        threading.Thread(target=fill_versions, daemon=True).start()

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
        render_browse()
        render_installed()
        render_wago()
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
