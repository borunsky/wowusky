"""Manager-state persistence layer for wowusky.

This module owns the on-disk state of the *manager itself* — the config
file, the per-profile installed databases, the profiles store, and the
tracked-Wago list — plus the dict-based profile model the GUI consumes and
the path/flavor inference used when adding a profile.

It deliberately holds no GUI, HTTP, or logging coupling: callers wire those
in (for example, ``app.py``'s ``reset_manager_state`` clears the HTTP cache
and logs around :func:`ensure_config_dir`).  Everything here is plain JSON
read/write over the paths defined in :mod:`wowusky.core.paths`.
"""

from __future__ import annotations

import json
import os
import re

from wowusky.core import paths as _paths
from wowusky.core.flavors import WOW_FLAVORS

CONFIG_DIR = str(_paths.CONFIG_DIR)
CONFIG_FILE = str(_paths.CONFIG_FILE)
INSTALLED_FILE = str(_paths.INSTALLED_FILE)  # legacy single-profile path
PROFILES_FILE = str(_paths.PROFILES_FILE)
INSTALLED_DIR = str(_paths.INSTALLED_DIR)
BACKUP_DIR = str(_paths.BACKUP_DIR)
LOG_DIR = str(_paths.LOG_DIR)
WAGO_FILE = str(_paths.WAGO_FILE)
MANIFEST_DIR = str(_paths.MANIFEST_DIR)


# ----------------------------------------------------------------------
# Filesystem + raw JSON
# ----------------------------------------------------------------------

def ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(INSTALLED_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(MANIFEST_DIR, exist_ok=True)


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


def load_config():
    return _read_json(CONFIG_FILE, {})


def save_config(c):
    _write_json(CONFIG_FILE, c)


def load_wago():
    return _read_json(WAGO_FILE, {"auras": {}})


def save_wago(d):
    _write_json(WAGO_FILE, d)


# ----------------------------------------------------------------------
# Profile model + path inference
# ----------------------------------------------------------------------

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
        for key, (pid, _prof) in by_real.items():
            if key == active_real:
                active = pid
                break
    if not active:
        active = next(iter(new_profiles), "default")

    return {"active": active, "profiles": new_profiles}


# ----------------------------------------------------------------------
# Profiles store
# ----------------------------------------------------------------------

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
        prof["id"] = f"{base}_{i}"
        i += 1
    data["profiles"][prof["id"]] = prof
    data["active"] = prof["id"]
    save_profiles(data)
    return prof["id"]


# ----------------------------------------------------------------------
# Per-profile installed database
# ----------------------------------------------------------------------

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


# ----------------------------------------------------------------------
# Path + config accessors
# ----------------------------------------------------------------------

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
    c = load_config()
    c["dry_run"] = bool(value)
    save_config(c)


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
