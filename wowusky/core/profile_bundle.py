"""Full profile bundle — portable snapshot of a whole profile (#65).

Unlike :mod:`wowusky.core.addonset` (which only carries the installed-addon
list), a bundle also includes the tracked Wago auras and a safe subset of the
global settings, so a profile can be reconstructed on another machine or after
a reinstall. The CurseForge API key is deliberately excluded.
"""

from __future__ import annotations

import time

_FORMAT_VERSION = "1"

# Global settings that are safe and useful to carry across machines. The
# CurseForge API key is intentionally omitted.
_SYNCED_SETTINGS = (
    "theme",
    "dry_run",
    "auto_update_on_launch",
    "desktop_notifications",
    "update_diff_before_install",
)


def export_profile_bundle(profile_id=None) -> dict:
    """Snapshot a profile's addons, tracked auras and synced settings."""
    from wowusky.core import config as _config
    from wowusky.core import installed as _installed
    from wowusky.core import state as _state

    data = _state.load_profiles()
    pid = profile_id or data.get("active") or "default"
    prof = data.get("profiles", {}).get(pid, {})
    db = _installed.load(pid)

    addons = [
        {
            "id": addon_id,
            "name": entry.get("name", addon_id),
            "version": entry.get("version", ""),
            "source": entry.get("source", ""),
            "folders": entry.get("folders", []),
            "interface": entry.get("interface"),
        }
        for addon_id, entry in sorted(db.items())
    ]

    auras = _state.load_wago().get("auras", {})
    cfg = _config.load_config()
    settings = {k: cfg[k] for k in _SYNCED_SETTINGS if k in cfg}

    return {
        "wowusky_profile_bundle": _FORMAT_VERSION,
        "profile": {
            "id": pid,
            "name": prof.get("name", pid),
            "flavor": prof.get("flavor", ""),
        },
        "exported_at": int(time.time()),
        "addons": addons,
        "auras": auras,
        "settings": settings,
    }


def _validate(data) -> None:
    if not isinstance(data, dict) or data.get("wowusky_profile_bundle") != _FORMAT_VERSION:
        raise ValueError(
            'Not a valid wowusky profile bundle (expected wowusky_profile_bundle == "1").'
        )


def import_bundle_preview(data, profile_id=None) -> dict:
    """Summarise what applying the bundle would change.

    Returns counts for addons (new/same/conflict) and auras (new/existing),
    plus the source profile metadata.
    """
    _validate(data)
    from wowusky.core import installed as _installed
    from wowusky.core import state as _state

    pid = profile_id or _state.get_active_profile_id()
    current = _installed.load(pid)
    cur_auras = _state.load_wago().get("auras", {})

    new = same = conflict = 0
    for addon in data.get("addons", []):
        aid = addon.get("id")
        if not aid:
            continue
        cur = current.get(aid)
        if cur is None:
            new += 1
        elif cur.get("version") == addon.get("version"):
            same += 1
        else:
            conflict += 1

    incoming_auras = data.get("auras", {})
    auras_new = sum(1 for s in incoming_auras if s not in cur_auras)

    return {
        "profile": data.get("profile", {}),
        "addons_new": new,
        "addons_same": same,
        "addons_conflict": conflict,
        "auras_new": auras_new,
        "auras_existing": len(incoming_auras) - auras_new,
        "settings_keys": sorted(data.get("settings", {}).keys()),
    }


def import_bundle_apply(data, profile_id=None, *, skip_ids=None,
                        include_auras=True, include_settings=True) -> dict:
    """Merge a bundle into the active profile.

    Installed addons are recorded in the DB (no downloads), tracked auras are
    merged, and the synced settings are applied. Returns a summary dict.
    """
    _validate(data)
    from wowusky.core import config as _config
    from wowusky.core import installed as _installed
    from wowusky.core import state as _state

    pid = profile_id or _state.get_active_profile_id()
    skip = set(skip_ids or [])
    current = _installed.load(pid)

    imported = skipped = 0
    for addon in data.get("addons", []):
        aid = addon.get("id")
        if not aid:
            continue
        if aid in skip:
            skipped += 1
            continue
        current[aid] = {
            "name": addon.get("name", aid),
            "version": addon.get("version", ""),
            "source": addon.get("source", ""),
            "folders": addon.get("folders", []),
            "interface": addon.get("interface"),
            "installed_at": int(time.time()),
        }
        imported += 1
    _installed.save(pid, current)

    auras_added = 0
    if include_auras and data.get("auras"):
        wago = _state.load_wago()
        wago.setdefault("auras", {})
        for slug, entry in data["auras"].items():
            if slug not in wago["auras"]:
                wago["auras"][slug] = entry
                auras_added += 1
        _state.save_wago(wago)

    settings_applied = 0
    if include_settings and data.get("settings"):
        cfg = _config.load_config()
        for k in _SYNCED_SETTINGS:
            if k in data["settings"]:
                cfg[k] = data["settings"][k]
                settings_applied += 1
        _config.save_config(cfg)

    return {
        "imported": imported,
        "skipped": skipped,
        "auras_added": auras_added,
        "settings_applied": settings_applied,
    }
