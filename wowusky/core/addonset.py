"""Addon-set export / import — portable profile snapshot."""
from __future__ import annotations

import time

_FORMAT_VERSION = "1"


def export_addon_set(profile_id=None) -> dict:
    """Snapshot the installed DB for a profile into a portable dict."""
    from wowusky.core import installed as _installed
    from wowusky.core import state as _state

    data = _state.load_profiles()
    pid = profile_id or data.get("active") or "default"
    prof = data.get("profiles", {}).get(pid, {})
    db = _installed.load(pid)

    addons = []
    for addon_id, entry in sorted(db.items()):
        addons.append({
            "id": addon_id,
            "name": entry.get("name", addon_id),
            "version": entry.get("version", ""),
            "source": entry.get("source", ""),
            "folders": entry.get("folders", []),
            "interface": entry.get("interface"),
        })

    return {
        "wowusky_export": _FORMAT_VERSION,
        "profile": {
            "id": pid,
            "name": prof.get("name", pid),
            "flavor": prof.get("flavor", ""),
        },
        "exported_at": int(time.time()),
        "count": len(addons),
        "addons": addons,
    }


def _validate(data) -> None:
    if not isinstance(data, dict) or data.get("wowusky_export") != _FORMAT_VERSION:
        raise ValueError(
            'Not a valid wowusky addon-set export (expected wowusky_export == "1").'
        )


def import_addon_set_preview(data, profile_id=None) -> list[dict]:
    """Return a per-addon preview for conflict resolution.

    Each entry: {id, name, version, installed_version, source, status}
    status: "new" | "same" | "conflict"
    """
    _validate(data)
    from wowusky.core import installed as _installed
    from wowusky.core import state as _state

    pid = profile_id or _state.get_active_profile_id()
    current = _installed.load(pid)

    preview = []
    for addon in data.get("addons", []):
        addon_id = addon.get("id")
        if not addon_id:
            continue
        cur = current.get(addon_id)
        if cur is None:
            status = "new"
        elif cur.get("version") == addon.get("version"):
            status = "same"
        else:
            status = "conflict"
        preview.append({
            "id": addon_id,
            "name": addon.get("name", addon_id),
            "version": addon.get("version", ""),
            "installed_version": (cur or {}).get("version", ""),
            "source": addon.get("source", ""),
            "status": status,
        })

    return preview


def import_addon_set_apply(data, profile_id=None, skip_ids=None) -> dict:
    """Merge an addon-set into the installed DB (no file downloads).

    Returns: {imported: int, skipped: int}
    """
    _validate(data)
    from wowusky.core import installed as _installed
    from wowusky.core import state as _state

    pid = profile_id or _state.get_active_profile_id()
    skip = set(skip_ids or [])
    current = _installed.load(pid)

    imported = 0
    skipped = 0
    for addon in data.get("addons", []):
        addon_id = addon.get("id")
        if not addon_id:
            continue
        if addon_id in skip:
            skipped += 1
            continue
        current[addon_id] = {
            "name": addon.get("name", addon_id),
            "version": addon.get("version", ""),
            "source": addon.get("source", ""),
            "folders": addon.get("folders", []),
            "interface": addon.get("interface"),
            "installed_at": int(time.time()),
        }
        imported += 1

    _installed.save(pid, current)
    return {"imported": imported, "skipped": skipped}
