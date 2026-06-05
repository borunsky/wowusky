"""Newline-delimited JSON-RPC 2.0 server over stdin/stdout.

Run with ``python -m wowusky.bridge``. Each line on stdin is one JSON-RPC
request; each response is written as a single line on stdout. Anything the
methods want to log goes to stderr so it never corrupts the protocol stream.

Phase 0 exposes a minimal, read-only surface so the Electron shell can prove
the round-trip works:

  * ``app.version``  -> {"version": "x.y.z"}
  * ``app.ping``     -> {"pong": <echo>}

Later phases register catalog/search/install/profile methods here, reusing the
existing ``wowusky.orchestrator`` and ``wowusky.core`` logic unchanged.
"""

from __future__ import annotations

import json
import sys
import traceback
from collections.abc import Callable
from typing import Any

# Method registry: name -> callable(params: dict) -> result
_METHODS: dict[str, Callable[[dict[str, Any]], Any]] = {}


def method(name: str) -> Callable[[Callable], Callable]:
    """Register ``fn`` as the handler for JSON-RPC ``name``."""

    def deco(fn: Callable[[dict[str, Any]], Any]) -> Callable:
        _METHODS[name] = fn
        return fn

    return deco


def _log(*args: Any) -> None:
    """Diagnostics go to stderr to keep stdout a clean protocol channel."""
    print("[wowusky.bridge]", *args, file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Phase 0 methods
# ---------------------------------------------------------------------------


@method("app.version")
def _app_version(_params: dict[str, Any]) -> dict[str, Any]:
    from wowusky import __version__

    return {"version": __version__}


@method("app.ping")
def _app_ping(params: dict[str, Any]) -> dict[str, Any]:
    return {"pong": params.get("echo")}


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

# Map internal provider ids to the UI's source pill classes.
_PROVIDER_SOURCE = {
    "curseforge_web": "curse",
    "github": "github",
    "wowi": "wowi",
    "tukui": "tukui",
    "internal_wac": "wowusky",
}


def _entry_to_addon(entry: dict[str, Any], favorites: set[str] | None = None) -> dict[str, Any]:
    """Project a catalog manifest entry onto the shape the UI expects."""
    name = entry.get("name", entry.get("id", "?"))
    provider = entry.get("provider", "")
    addon_id = entry.get("id")
    return {
        "id": addon_id,
        "name": name,
        "author": entry.get("author", "Unknown"),
        "category": entry.get("category", "Other"),
        "description": entry.get("description", ""),
        "source": _PROVIDER_SOURCE.get(provider, "local"),
        "glyph": (name[:1] or "?").upper(),
        "flavors": entry.get("flavors", []),
        "folders": entry.get("folders", []),
        "depends": entry.get("depends", []),
        "tags": entry.get("tags", []),
        "favorite": favorites is not None and addon_id in favorites,
    }


@method("catalog.search")
def _catalog_search(params: dict[str, Any]) -> dict[str, Any]:
    """Filter the catalog using fuzzy search + tags.

    params: {query?: str, category?: str, limit?: int, only_favorites?: bool}
    returns: {total: int, count: int, categories: [str], tags: [str], items: [addon]}
    """
    from wowusky.catalog import load_catalog
    from wowusky.core import favorites as _fav
    from wowusky.core import installed as _installed
    from wowusky.core import search as _search
    from wowusky.core import state as _state

    catalog = load_catalog()
    query = str(params.get("query", ""))
    category = params.get("category") or "All"
    limit = int(params.get("limit", 200))
    only_favorites = bool(params.get("only_favorites", False))

    try:
        installed_ids = set(_installed.load(_state.get_active_profile_id()).keys())
    except Exception:  # noqa: BLE001
        installed_ids = set()

    try:
        fav_ids = _fav.load()
    except Exception:  # noqa: BLE001
        fav_ids = set()

    categories = sorted({e.get("category", "Other") for e in catalog})
    all_tags = sorted({t for e in catalog for t in e.get("tags", [])})

    matched = _search.search(catalog, query, category=category,
                             only_favorites=only_favorites, favorites=fav_ids)

    items: list[dict[str, Any]] = []
    for entry in matched:
        addon = _entry_to_addon(entry, fav_ids)
        addon["installed"] = addon["id"] in installed_ids
        items.append(addon)

    return {
        "total": len(catalog),
        "count": len(items),
        "categories": ["All", *categories],
        "tags": all_tags,
        "items": items[:limit],
    }


# ---------------------------------------------------------------------------
# Installed addons
# ---------------------------------------------------------------------------

# Map installer source strings onto the UI's source pill classes.
_SOURCE_PILL = {
    "github": "github",
    "tukui": "tukui",
    "wowi": "wowi",
    "curseforge": "curse",
    "curseforge_web": "curse",
    "curseforge_manual": "curse",
    "internal_wac": "wowusky",
    "import": "local",
    "imported": "local",
}


def _installed_entry_to_addon(addon_id: str, entry: dict[str, Any]) -> dict[str, Any]:
    name = entry.get("name", addon_id)
    raw_source = str(entry.get("source", "") or "")
    return {
        "id": addon_id,
        "name": name,
        "version": entry.get("version", "unknown"),
        "source": _SOURCE_PILL.get(raw_source, "local"),
        "folders": entry.get("folders", []),
        "interface": entry.get("interface"),
        "url": entry.get("url"),
        "glyph": (name[:1] or "?").upper(),
        "note": entry.get("note", ""),
    }


@method("installed.list")
def _installed_list(params: dict[str, Any]) -> dict[str, Any]:
    """List addons installed under the active (or given) profile.

    params: {profile?: str}
    returns: {profile: str, count: int, addons_path: str, items: [addon]}
    """
    from wowusky.core import installed as _installed
    from wowusky.core import state as _state

    profile = params.get("profile") or _state.get_active_profile_id()
    data = _installed.load(profile)
    items = [
        _installed_entry_to_addon(addon_id, entry)
        for addon_id, entry in data.items()
    ]
    items.sort(key=lambda a: a["name"].lower())
    try:
        addons_path = _state.get_addons_path()
    except Exception:  # noqa: BLE001 — path may be unconfigured
        addons_path = ""
    return {
        "profile": profile,
        "count": len(items),
        "addons_path": addons_path,
        "items": items,
    }


@method("installed.updates")
def _installed_updates(params: dict[str, Any]) -> dict[str, Any]:
    """Check installed addons for available updates (does network I/O).

    Compares each installed addon's recorded version against the latest
    version its provider reports. Only addons that are in the catalog, have a
    known current version, and whose latest differs are reported.

    params: {profile?: str}
    returns: {profile: str, updates: {id: latest_version}}
    """
    from wowusky import orchestrator as _orch
    from wowusky.core import installed as _installed
    from wowusky.core import state as _state

    profile = params.get("profile") or _state.get_active_profile_id()
    db = _installed.load(profile)

    updates: dict[str, str] = {}
    for addon_id, entry in db.items():
        cat_entry = _orch.find_addon_by_id(addon_id)
        if cat_entry is None:
            continue
        current = entry.get("version") or ""
        if not current:
            continue
        try:
            latest = _orch.get_latest_version(cat_entry)
        except Exception:  # noqa: BLE001 — a single lookup failure shouldn't break the rest
            latest = None
        if latest and latest != current:
            updates[addon_id] = latest

    return {"profile": profile, "updates": updates}


@method("app.rescan")
def _app_rescan(_params: dict[str, Any]) -> dict[str, Any]:
    """Re-scan the filesystem and reconcile it with the installed DB.

    Returns the refreshed installed list for the active profile.
    """
    from wowusky.catalog import load_catalog
    from wowusky.core import scan as _scan
    from wowusky.core import state as _state

    try:
        addons_path = _state.get_addons_path()
        _scan.sync_filesystem_with_db(addons_path, load_catalog())
    except Exception as exc:  # noqa: BLE001 — surface scan issues without crashing
        _log("rescan error:", traceback.format_exc())
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    profile = _state.get_active_profile_id()
    return {"ok": True, **_installed_list({"profile": profile})}


# ---------------------------------------------------------------------------
# Settings & profiles
# ---------------------------------------------------------------------------


def _profile_summaries() -> list[dict[str, Any]]:
    from wowusky.core import installed as _installed
    from wowusky.core import state as _state

    data = _state.load_profiles()
    profiles = data.get("profiles", {})
    out: list[dict[str, Any]] = []
    for pid, p in profiles.items():
        try:
            count = len(_installed.load(pid))
        except Exception:  # noqa: BLE001 — a broken profile shouldn't hide the rest
            count = 0
        out.append(
            {
                "id": pid,
                "name": p.get("name", pid),
                "flavor": p.get("flavor", pid),
                "addons_path": p.get("addons_path", ""),
                "color_tag": p.get("color_tag"),
                "count": count,
                "auto_update": bool(p.get("auto_update", False)),
            }
        )
    out.sort(key=lambda p: p["name"].lower())
    return out


@method("settings.get")
def _settings_get(_params: dict[str, Any]) -> dict[str, Any]:
    """Return the persisted core settings the GUI can edit."""
    from wowusky.core import state as _state

    try:
        addons_path = _state.get_addons_path()
    except Exception:  # noqa: BLE001
        addons_path = ""
    try:
        wtf_path = _state.get_wtf_path()
    except Exception:  # noqa: BLE001
        wtf_path = ""

    from wowusky.core import config as _config

    cf_key = _state.get_curseforge_api_key() or ""
    return {
        "addons_path": addons_path,
        "wtf_path": wtf_path,
        "dry_run": bool(_state.is_dry_run()),
        "curseforge_api_key_set": bool(cf_key),
        "auto_update_on_launch": bool(_config.get_auto_update_on_launch()),
        "desktop_notifications": bool(_config.get_desktop_notifications()),
        "update_diff_before_install": bool(_config.get_update_diff_before_install()),
        "active_profile": _state.get_active_profile_id(),
        "profiles": _profile_summaries(),
    }


@method("settings.update")
def _settings_update(params: dict[str, Any]) -> dict[str, Any]:
    """Apply any provided settings fields, then return the fresh settings.

    Recognised fields: addons_path, dry_run, curseforge_api_key.
    """
    from wowusky.core import state as _state

    if "addons_path" in params:
        _state.set_addons_path(str(params["addons_path"]))
    if "dry_run" in params:
        _state.set_dry_run(bool(params["dry_run"]))
    if "curseforge_api_key" in params:
        _state.set_curseforge_api_key(str(params["curseforge_api_key"]))
    if "auto_update_on_launch" in params:
        from wowusky.core import config as _config
        _config.set_auto_update_on_launch(bool(params["auto_update_on_launch"]))
    if "desktop_notifications" in params:
        from wowusky.core import config as _config
        _config.set_desktop_notifications(bool(params["desktop_notifications"]))
    if "update_diff_before_install" in params:
        from wowusky.core import config as _config
        _config.set_update_diff_before_install(bool(params["update_diff_before_install"]))

    return _settings_get({})


@method("profile.setActive")
def _profile_set_active(params: dict[str, Any]) -> dict[str, Any]:
    """Switch the active profile and return refreshed settings."""
    from wowusky.core import state as _state

    pid = params.get("profile")
    if not pid:
        raise ValueError("profile is required")
    _state.set_active_profile(str(pid))
    return _settings_get({})


@method("profile.setPath")
def _profile_set_path(params: dict[str, Any]) -> dict[str, Any]:
    """Set the addons_path for a specific profile (or the active one).

    params: {path: str, profile?: str}
    returns: updated settings
    """
    from wowusky.core import state as _state

    path = params.get("path")
    if not path:
        raise ValueError("path is required")
    pid = params.get("profile")
    if pid:
        _state.set_active_profile(str(pid))
    _state.set_addons_path(str(path))
    return _settings_get({})


@method("profile.rename")
def _profile_rename(params: dict[str, Any]) -> dict[str, Any]:
    """Rename a profile's display name (id stays stable)."""
    from wowusky.core import state as _state

    pid = params.get("profile")
    name = params.get("name")
    if not pid:
        raise ValueError("profile is required")
    if not (name or "").strip():
        raise ValueError("name is required")
    _state.rename_profile(str(pid), str(name))
    return _settings_get({})


@method("profile.delete")
def _profile_delete(params: dict[str, Any]) -> dict[str, Any]:
    """Delete a profile. Its installed DB / backups on disk are kept."""
    from wowusky.core import state as _state

    pid = params.get("profile")
    if not pid:
        raise ValueError("profile is required")
    _state.delete_profile(str(pid))
    return _settings_get({})


@method("profile.setAutoUpdate")
def _profile_set_auto_update(params: dict[str, Any]) -> dict[str, Any]:
    """Toggle a profile's auto-update flag, then return refreshed settings."""
    from wowusky.core import state as _state

    pid = params.get("profile")
    if not pid:
        raise ValueError("profile is required")
    _state.set_auto_update(str(pid), bool(params.get("enabled")))
    return _settings_get({})


def _sync_diff(source: str, target: str) -> dict[str, Any]:
    """Compare the source and target installed DBs.

    Returns the source profile's catalog addons bucketed by how they relate
    to the target: ``new`` (absent), ``conflict`` (present, different version)
    or ``same`` (present, identical version). Non-catalog (orphan/imported)
    addons can't be reinstalled elsewhere and are reported separately.
    """
    from wowusky import orchestrator as _orch
    from wowusky.core import installed as _installed

    src_db = _installed.load(source)
    tgt_db = _installed.load(target)

    new: list[dict[str, Any]] = []
    conflict: list[dict[str, Any]] = []
    same: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for addon_id, entry in sorted(src_db.items(), key=lambda kv: (kv[1].get("name") or kv[0]).lower()):
        name = entry.get("name") or addon_id
        if _orch.find_addon_by_id(addon_id) is None:
            skipped.append({"id": addon_id, "name": name, "reason": "not in catalog"})
            continue
        row = {
            "id": addon_id,
            "name": name,
            "version": entry.get("version") or "",
        }
        if addon_id not in tgt_db:
            new.append(row)
        elif (tgt_db[addon_id].get("version") or "") != row["version"]:
            conflict.append({**row, "target_version": tgt_db[addon_id].get("version") or ""})
        else:
            same.append(row)
    return {"new": new, "conflict": conflict, "same": same, "skipped": skipped}


@method("profile.syncPreview")
def _profile_sync_preview(params: dict[str, Any]) -> dict[str, Any]:
    """Preview a cross-profile sync without changing anything.

    params: {source: str, target?: str}  (target defaults to the active profile)
    returns: {source, target, new: [...], conflict: [...], same: [...], skipped: [...]}
    """
    from wowusky.core import state as _state

    source = params.get("source")
    if not source:
        raise ValueError("source is required")
    target = params.get("target") or _state.get_active_profile_id()
    if source == target:
        raise ValueError("source and target must differ")
    return {"source": source, "target": target, **_sync_diff(source, target)}


@method("profile.syncApply")
def _profile_sync_apply(params: dict[str, Any]) -> dict[str, Any]:
    """Install the source profile's addons into the target profile.

    Installs every catalog addon present in *source* into *target* unless its
    id is listed in ``skip_ids``. Addons already at the same version are
    skipped automatically. The active profile is restored afterwards.

    params: {source: str, target?: str, skip_ids?: [str]}
    returns: {ok, installed: [str], failed: [{id, error}], log: [str]}
    """
    from wowusky import orchestrator as _orch
    from wowusky.core import state as _state

    source = params.get("source")
    if not source:
        raise ValueError("source is required")
    target = params.get("target") or _state.get_active_profile_id()
    if source == target:
        raise ValueError("source and target must differ")
    skip = set(params.get("skip_ids") or [])

    diff = _sync_diff(source, target)
    # Sync new + conflicting addons; "same" needs no work.
    candidates = [r["id"] for r in (diff["new"] + diff["conflict"]) if r["id"] not in skip]

    previous_active = _state.get_active_profile_id()
    installed_ok: list[str] = []
    failed: list[dict[str, str]] = []
    log: list[str] = []
    try:
        _state.set_active_profile(target)
        addons_path = _state.get_addons_path()
        for addon_id in candidates:
            entry = _orch.find_addon_by_id(addon_id)
            if entry is None:
                failed.append({"id": addon_id, "error": "not in catalog"})
                continue
            try:
                _orch.install_addon(entry, addons_path, log=log.append)
                installed_ok.append(addon_id)
            except Exception as exc:  # noqa: BLE001 — keep syncing the rest
                _log("sync install error:", traceback.format_exc())
                failed.append({"id": addon_id, "error": f"{type(exc).__name__}: {exc}"})
    finally:
        _state.set_active_profile(previous_active)

    return {
        "ok": not failed,
        "installed": installed_ok,
        "failed": failed,
        "log": log,
    }


@method("profiles.scan")
def _profiles_scan(_params: dict[str, Any]) -> dict[str, Any]:
    """Scan the filesystem for WoW installations not already configured.

    Installations whose AddOns path matches an existing profile (compared by
    real path) are dropped so Autoscan only surfaces genuinely new clients.

    returns: {count: int, found: [{flavor, flavor_name, addons_path}]}
    """
    import os

    from wowusky.core import scan as _scan
    from wowusky.core import state as _state

    def _key(path: str) -> str:
        return os.path.realpath(os.path.expanduser(path or ""))

    existing = {
        _key(p.get("addons_path", ""))
        for p in _state.load_profiles().get("profiles", {}).values()
        if p.get("addons_path")
    }

    found = [
        inst for inst in _scan.scan_wow_installations()
        if _key(inst.get("addons_path", "")) not in existing
    ]
    return {"count": len(found), "found": found}


@method("profiles.addFromPath")
def _profiles_add_from_path(params: dict[str, Any]) -> dict[str, Any]:
    """Create or update a profile for the given addons_path, make it active.

    params: {path: str, name?: str}
    returns: updated settings
    """
    from wowusky.core import state as _state

    path = params.get("path")
    if not path:
        raise ValueError("path is required")
    name = params.get("name") or ""
    _state.add_or_update_profile(name, str(path))
    return _settings_get({})


# ---------------------------------------------------------------------------
# WeakAuras (wago tracking)
# ---------------------------------------------------------------------------


@method("weakauras.list")
def _weakauras_list(_params: dict[str, Any]) -> dict[str, Any]:
    """List the tracked Wago auras for the active profile (offline read)."""
    from wowusky.core import wago as _wago

    data = _wago.load_wago()
    auras = data.get("auras", {})
    items = [
        {
            "slug": slug,
            "name": a.get("name", slug),
            "version": a.get("version", 1),
            "latest_version": a.get("latest_version", a.get("version", 1)),
            "has_update": _has_aura_update(a),
            "type": a.get("type", "WeakAura"),
            "note": a.get("note", ""),
            "author": a.get("author", ""),
            "modified": a.get("modified", ""),
            "url": a.get("url", f"https://wago.io/{slug}"),
        }
        for slug, a in auras.items()
    ]
    items.sort(key=lambda x: str(x["name"]).lower())
    return {"count": len(items), "items": items}


def _has_aura_update(a: dict) -> bool:
    try:
        cur = int(a.get("version", 1))
        lat = int(a.get("latest_version", cur))
        return lat > cur
    except (ValueError, TypeError):
        return False


@method("wago.checkUpdates")
def _wago_check_updates(_params: dict[str, Any]) -> dict[str, Any]:
    """Fetch latest version info for all tracked auras and return those with updates."""
    from wowusky.core import wago as _wago

    updated_slugs = _wago.wago_check_updates()
    return {"updates": updated_slugs, "count": len(updated_slugs)}


@method("wago.update")
def _wago_update(params: dict[str, Any]) -> dict[str, Any]:
    """Update a single aura to its latest version on wago.io."""
    from wowusky.core import wago as _wago
    from wowusky.providers.wago_fns import wago_fetch_info

    slug = str(params.get("slug", "")).strip()
    if not slug:
        raise ValueError("slug is required")

    info = wago_fetch_info(slug)
    if not info:
        return {"ok": False, "error": "could not fetch aura info from wago.io"}

    wago = _wago.load_wago()
    if slug not in wago.get("auras", {}):
        return {"ok": False, "error": "aura not tracked"}

    entry = wago["auras"][slug]
    latest = info.get("version") or info.get("wagoVersion") or entry.get("version", 1)
    entry["version"] = latest
    entry["latest_version"] = latest
    entry["author"] = info.get("username") or info.get("author") or entry.get("author", "")
    entry["modified"] = info.get("modified") or info.get("date") or entry.get("modified", "")
    entry["note"] = info.get("versionString") or info.get("changelog", {}).get("text", "") or entry.get("note", "")
    _wago.save_wago(wago)
    return {"ok": True, "slug": slug, "version": latest}


@method("wago.updateAll")
def _wago_update_all(_params: dict[str, Any]) -> dict[str, Any]:
    """Update all tracked auras that have pending updates."""
    from wowusky.core import wago as _wago
    from wowusky.providers.wago_fns import wago_fetch_info

    wago = _wago.load_wago()
    auras = wago.get("auras", {})
    updated = []
    failed = []
    for slug, entry in auras.items():
        if not _has_aura_update(entry):
            continue
        try:
            info = wago_fetch_info(slug)
            if not info:
                failed.append(slug)
                continue
            latest = info.get("version") or info.get("wagoVersion") or entry.get("latest_version")
            entry["version"] = latest
            entry["latest_version"] = latest
            entry["author"] = info.get("username") or info.get("author") or entry.get("author", "")
            entry["modified"] = info.get("modified") or info.get("date") or entry.get("modified", "")
            updated.append(slug)
        except Exception:  # noqa: BLE001
            failed.append(slug)
    _wago.save_wago(wago)
    return {"ok": True, "updated": updated, "failed": failed}


@method("wago.search")
def _wago_search(params: dict[str, Any]) -> dict[str, Any]:
    """Search wago.io and return a normalised list of auras (#48)."""
    from wowusky.core import wago as _wago

    query = str(params.get("query", "")).strip()
    if not query:
        return {"items": []}
    limit = int(params.get("limit", 20) or 20)

    data = _wago.wago_search(query, limit=limit)
    if isinstance(data, dict):
        raw = data.get("data") or data.get("results") or []
    elif isinstance(data, list):
        raw = data
    else:
        raw = []

    items = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        slug = r.get("slug") or r.get("_id")
        if not slug:
            continue
        items.append(
            {
                "slug": slug,
                "name": r.get("name") or slug,
                "author": r.get("username") or r.get("author") or "",
                "type": r.get("type") or "WeakAura",
            }
        )
    return {"items": items}


@method("wago.add")
def _wago_add(params: dict[str, Any]) -> dict[str, Any]:
    """Track a wago aura by slug (#48)."""
    from wowusky.core import wago as _wago

    slug = str(params.get("slug", "")).strip()
    if not slug:
        raise ValueError("slug is required")
    name = params.get("name")
    note = params.get("note")
    try:
        entry = _wago.wago_add(slug, name=name, note=note)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "slug": slug, "name": (entry or {}).get("name", slug)}


@method("wago.importFromSavedVariables")
def _wago_import_sv(_params: dict[str, Any]) -> dict[str, Any]:
    """Scan WoW SavedVariables and track all discovered auras (#49)."""
    from wowusky.core import wago as _wago

    try:
        result = _wago.import_existing_weakauras_from_savedvariables(log=lambda *_: None)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "added": result.get("added", 0),
        "existing": result.get("existing", 0),
        "failed": result.get("failed", 0),
        "slugs": result.get("slugs", []),
    }


@method("wago.generateCompanion")
def _wago_generate_companion(_params: dict[str, Any]) -> dict[str, Any]:
    """Generate the WeakAurasCompanion addon for the active profile (#50)."""
    from wowusky.core import state as _state
    from wowusky.core import wago as _wago
    from wowusky.orchestrator import generate_wac_companion

    try:
        addons_path = _state.get_addons_path()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"no addons path: {exc}"}
    if not addons_path:
        return {"ok": False, "error": "no addons path configured for the active profile"}

    count = len(_wago.load_wago().get("auras", {}))
    try:
        ok = generate_wac_companion(addons_path)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
    if not ok:
        return {"ok": False, "error": "companion generation failed"}
    return {"ok": True, "count": count, "path": addons_path}


@method("wago.updateNotes")
def _wago_update_notes(params: dict[str, Any]) -> dict[str, Any]:
    """Return a tracked aura's version transition + changelog (#62).

    params: {slug: str}
    returns: {slug, name, current_version, latest_version, changelog} or
             {error} when the slug is not tracked.
    """
    from wowusky.core import wago as _wago

    slug = str(params.get("slug", "")).strip()
    if not slug:
        raise ValueError("slug is required")
    try:
        notes = _wago.wago_update_notes(slug)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
    if notes is None:
        return {"error": "not tracked"}
    return notes


@method("wago.untrackMany")
def _wago_untrack_many(params: dict[str, Any]) -> dict[str, Any]:
    """Untrack several auras at once (#64).

    params: {slugs: [str]}
    returns: {ok, removed}
    """
    from wowusky.core import wago as _wago

    slugs = list(params.get("slugs") or [])
    if not slugs:
        raise ValueError("slugs is required")
    removed = _wago.wago_untrack_many(slugs)
    return {"ok": True, "removed": removed}


@method("wago.addCollection")
def _wago_add_collection(params: dict[str, Any]) -> dict[str, Any]:
    """Track every aura in a wago collection (#64).

    params: {url: str}  (a wago collection URL or bare collection id)
    returns: {ok, total, added, already} or {ok: False, error}
    """
    from wowusky.core import wago as _wago

    raw = str(params.get("url", "")).strip()
    if not raw:
        raise ValueError("url is required")
    # Accept a full URL (…/collections/<id> or …/<id>) or a bare id.
    cid = raw.rstrip("/").split("/")[-1]
    try:
        result = _wago.wago_add_collection(cid)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
    if result.get("total", 0) == 0:
        return {"ok": False, "error": "no auras found in that collection"}
    return {"ok": True, **result}


# ---------------------------------------------------------------------------
# Full profile bundle (#65)
# ---------------------------------------------------------------------------


@method("profile.exportBundle")
def _profile_export_bundle(params: dict[str, Any]) -> dict[str, Any]:
    """Return a full profile bundle (addons + auras + settings) as a dict."""
    from wowusky.core import profile_bundle as _pb
    from wowusky.core import state as _state

    pid = params.get("profile") or _state.get_active_profile_id()
    bundle = _pb.export_profile_bundle(pid)
    return {"ok": True, "bundle": bundle}


@method("profile.importBundlePreview")
def _profile_import_bundle_preview(params: dict[str, Any]) -> dict[str, Any]:
    """Summarise what applying a bundle would change."""
    from wowusky.core import profile_bundle as _pb

    data = params.get("bundle")
    if not isinstance(data, dict):
        raise ValueError("bundle is required")
    try:
        return {"ok": True, **_pb.import_bundle_preview(data)}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}


@method("profile.importBundleApply")
def _profile_import_bundle_apply(params: dict[str, Any]) -> dict[str, Any]:
    """Apply a bundle into the active profile."""
    from wowusky.core import profile_bundle as _pb

    data = params.get("bundle")
    if not isinstance(data, dict):
        raise ValueError("bundle is required")
    try:
        result = _pb.import_bundle_apply(
            data,
            skip_ids=params.get("skip_ids"),
            include_auras=params.get("include_auras", True),
            include_settings=params.get("include_settings", True),
        )
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, **result}


# ---------------------------------------------------------------------------
# Git-based profile sync (#66)
# ---------------------------------------------------------------------------


@method("sync.status")
def _sync_status(_params: dict[str, Any]) -> dict[str, Any]:
    from wowusky.core import sync as _sync

    return _sync.status()


@method("sync.setRepo")
def _sync_set_repo(params: dict[str, Any]) -> dict[str, Any]:
    from wowusky.core import sync as _sync

    _sync.set_repo_path(str(params.get("path", "")))
    return _sync.status()


@method("sync.push")
def _sync_push(_params: dict[str, Any]) -> dict[str, Any]:
    from wowusky.core import sync as _sync

    return _sync.push(log=_log)


@method("sync.pull")
def _sync_pull(_params: dict[str, Any]) -> dict[str, Any]:
    """Pull the latest bundle and return it plus an apply-preview."""
    from wowusky.core import profile_bundle as _pb
    from wowusky.core import sync as _sync

    result = _sync.pull(log=_log)
    if not result.get("ok"):
        return result
    bundle = result.get("bundle") or {}
    try:
        preview = _pb.import_bundle_preview(bundle)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "bundle": bundle, "preview": preview,
            "pull_message": result.get("pull_message", "")}


# ---------------------------------------------------------------------------
# Change history / audit log (#67)
# ---------------------------------------------------------------------------


@method("history.list")
def _history_list(params: dict[str, Any]) -> dict[str, Any]:
    """Return the persistent change history for a profile, newest-first.

    params: {profile?: str, addon?: str, limit?: int}
    returns: {profile, items: [{ts, action, id, name, from, to}]}
    """
    from wowusky.core import history as _history
    from wowusky.core import state as _state

    profile = params.get("profile") or _state.get_active_profile_id()
    items = _history.list_history(
        profile,
        addon=params.get("addon"),
        limit=int(params.get("limit", 500) or 500),
    )
    return {"profile": profile, "items": items}


@method("history.clear")
def _history_clear(params: dict[str, Any]) -> dict[str, Any]:
    from wowusky.core import history as _history
    from wowusky.core import state as _state

    profile = params.get("profile") or _state.get_active_profile_id()
    return {"ok": _history.clear_history(profile)}


# ---------------------------------------------------------------------------
# Release notes (#53)
# ---------------------------------------------------------------------------


@method("addon.releaseNotes")
def _addon_release_notes(params: dict[str, Any]) -> dict[str, Any]:
    """Return the source's release notes for an installed/catalog addon."""
    from wowusky import orchestrator as _orch
    from wowusky.catalog import load_catalog

    addon_id = params.get("id")
    if not addon_id:
        raise ValueError("id is required")

    addon = None
    for entry in load_catalog():
        if entry.get("id") == addon_id:
            addon = entry
            break
    if addon is None:
        inst = _orch.load_installed().get(addon_id)
        if inst:
            addon = {**inst, "id": addon_id}
    if addon is None:
        return {"version": "", "notes": ""}

    try:
        notes = _orch.update_notes(addon)
    except Exception:  # noqa: BLE001
        notes = None
    if not notes:
        return {"version": "", "notes": ""}
    return {"version": notes.get("version", ""), "notes": notes.get("notes", "")}


# ---------------------------------------------------------------------------
# Storage overview & cleanup (#52)
# ---------------------------------------------------------------------------


@method("storage.summary")
def _storage_summary(_params: dict[str, Any]) -> dict[str, Any]:
    """Report disk usage for the active profile's backups and addons."""
    from wowusky.core import backup as _backup

    return _backup.storage_summary()


@method("storage.cleanup")
def _storage_cleanup(params: dict[str, Any]) -> dict[str, Any]:
    """Prune old backups down to the newest *keep* per addon and full set."""
    from wowusky.core import backup as _backup

    keep = int(params.get("keep", 5) or 5)
    result = _backup.cleanup_old_backups(keep)
    return {"ok": True, **result}


# ---------------------------------------------------------------------------
# Scheduled backups (#51)
# ---------------------------------------------------------------------------


@method("backupSchedule.status")
def _backup_schedule_status(_params: dict[str, Any]) -> dict[str, Any]:
    from wowusky.core import schedule as _schedule

    return _schedule.backup_status()


@method("backupSchedule.enable")
def _backup_schedule_enable(params: dict[str, Any]) -> dict[str, Any]:
    from wowusky.core import schedule as _schedule

    interval = str(params.get("interval", "daily") or "daily")
    keep = int(params.get("keep", 5) or 5)
    return _schedule.backup_enable(interval, keep)


@method("backupSchedule.disable")
def _backup_schedule_disable(_params: dict[str, Any]) -> dict[str, Any]:
    from wowusky.core import schedule as _schedule

    return _schedule.backup_disable()


# ---------------------------------------------------------------------------
# Scheduled companion rebuilds (#63)
# ---------------------------------------------------------------------------


@method("companionSchedule.status")
def _companion_schedule_status(_params: dict[str, Any]) -> dict[str, Any]:
    from wowusky.core import schedule as _schedule

    return _schedule.companion_status()


@method("companionSchedule.enable")
def _companion_schedule_enable(params: dict[str, Any]) -> dict[str, Any]:
    from wowusky.core import schedule as _schedule

    interval = str(params.get("interval", "daily") or "daily")
    return _schedule.companion_enable(interval)


@method("companionSchedule.disable")
def _companion_schedule_disable(_params: dict[str, Any]) -> dict[str, Any]:
    from wowusky.core import schedule as _schedule

    return _schedule.companion_disable()


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------


@method("backups.list")
def _backups_list(_params: dict[str, Any]) -> dict[str, Any]:
    """List full backups and per-addon backups for the active profile."""
    from wowusky.core import backup as _backup
    from wowusky.core import installed as _installed
    from wowusky.core import state as _state

    full = [
        {"path": b["path"], "name": b["name"], "mtime": b["mtime"], "size": b["size"]}
        for b in _backup.list_full_backups()
    ]

    profile = _state.get_active_profile_id()
    addon_backups: list[dict[str, Any]] = []
    for addon_id, entry in _installed.load(profile).items():
        for b in _backup.list_addon_backups(addon_id):
            addon_backups.append(
                {
                    "addon_id": addon_id,
                    "addon_name": entry.get("name", addon_id),
                    "name": b["name"],
                    "path": b["path"],
                    "mtime": b["mtime"],
                    "size": b["size"],
                    "version": b.get("version", "unknown"),
                }
            )
    addon_backups.sort(key=lambda x: x["mtime"], reverse=True)

    return {
        "full": full,
        "addons": addon_backups,
        "full_count": len(full),
        "addon_count": len(addon_backups),
    }


# ---------------------------------------------------------------------------
# Addon actions (install / update / remove)
# ---------------------------------------------------------------------------


def _action_callbacks(
    addon_id: str,
) -> tuple[Callable[..., None], Callable[[int, int], None], list[str]]:
    """Build ``(log, progress, lines)`` for an action handler.

    ``log`` appends to ``lines`` *and* streams each line as an
    ``action.progress`` notification (phase ``"log"``). ``progress`` streams
    download byte counts (phase ``"download"``). Both tag events with
    ``addon_id`` so the UI can correlate them to the in-flight action.
    """
    lines: list[str] = []

    def _log_line(*args: Any) -> None:
        msg = " ".join(str(a) for a in args)
        lines.append(msg)
        _notify("action.progress", {"id": addon_id, "phase": "log", "message": msg})

    def _progress(done: int, total: int) -> None:
        pct = int(done * 100 / total) if total > 0 else 0
        _notify(
            "action.progress",
            {"id": addon_id, "phase": "download", "done": done, "total": total, "pct": pct},
        )

    return _log_line, _progress, lines


def _record_history(profile: str, action: str, addon_id: str, *,
                    name: str = "", from_version: str = "", to_version: str = "") -> None:
    """Best-effort append to the persistent change history (#67)."""
    try:
        from wowusky.core import history as _history
        _history.record(profile, action, addon_id, name=name,
                        from_version=from_version, to_version=to_version)
    except Exception:  # noqa: BLE001 — history must never break an action
        _log("history record failed:", traceback.format_exc())


@method("addon.install")
def _addon_install(params: dict[str, Any]) -> dict[str, Any]:
    """Install (or reinstall) a catalog addon by id for the active profile.

    params: {id: str}
    returns: {ok: bool, log: [str], error?: str, installed?: {...}}
    """
    from wowusky import orchestrator as _orch
    from wowusky.core import state as _state

    addon_id = params.get("id")
    if not addon_id:
        raise ValueError("id is required")

    entry = _orch.find_addon_by_id(addon_id)
    if entry is None:
        return {"ok": False, "error": f"addon not in catalog: {addon_id}"}

    addons_path = _state.get_addons_path()
    from wowusky.core import installed as _installed
    profile = _state.get_active_profile_id()
    prior = _installed.load(profile).get(addon_id, {})
    log_fn, progress_fn, lines = _action_callbacks(addon_id)
    try:
        _orch.install_addon(entry, addons_path, log=log_fn, progress=progress_fn)
    except Exception as exc:  # noqa: BLE001 — report install failure to the UI
        _log("install error:", traceback.format_exc())
        _notify("action.done", {"id": addon_id, "ok": False, "error": str(exc)})
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "log": lines}

    _notify("action.done", {"id": addon_id, "ok": True})
    profile = _state.get_active_profile_id()
    new_entry = _installed.load(profile).get(addon_id, {})
    _record_history(
        profile, "update" if prior else "install", addon_id,
        name=new_entry.get("name") or entry.get("name") or addon_id,
        from_version=prior.get("version", ""),
        to_version=new_entry.get("version", ""),
    )
    return {"ok": True, "log": lines, **_installed_list({"profile": profile})}


# An update is an install of the latest version over the existing folders;
# the core installer backs up the current copy first.
_METHODS["addon.update"] = _addon_install


@method("addon.remove")
def _addon_remove(params: dict[str, Any]) -> dict[str, Any]:
    """Uninstall an addon (folders + DB entry) for the active profile.

    A backup is taken automatically by the core uninstall logic.
    params: {id: str}
    returns: {ok: bool, log: [str], error?: str, installed?: {...}}
    """
    from wowusky import orchestrator as _orch
    from wowusky.core import state as _state

    addon_id = params.get("id")
    if not addon_id:
        raise ValueError("id is required")

    addons_path = _state.get_addons_path()
    from wowusky.core import installed as _installed
    profile = _state.get_active_profile_id()
    prior = _installed.load(profile).get(addon_id, {})
    log_fn, _progress_fn, lines = _action_callbacks(addon_id)
    try:
        _orch.uninstall_addon(addon_id, addons_path, log=log_fn)
    except Exception as exc:  # noqa: BLE001 — report removal failure to the UI
        _log("remove error:", traceback.format_exc())
        _notify("action.done", {"id": addon_id, "ok": False, "error": str(exc)})
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "log": lines}

    _notify("action.done", {"id": addon_id, "ok": True})
    profile = _state.get_active_profile_id()
    _record_history(profile, "remove", addon_id,
                    name=prior.get("name") or addon_id,
                    from_version=prior.get("version", ""))
    return {"ok": True, "log": lines, **_installed_list({"profile": profile})}


def _resolve_addon(addon_id: str) -> dict[str, Any] | None:
    """Find an addon dict by id — prefer the catalog, fall back to the
    installed DB (so orphan/imported addons still resolve)."""
    from wowusky import orchestrator as _orch
    from wowusky.core import installed as _installed
    from wowusky.core import state as _state

    entry = _orch.find_addon_by_id(addon_id)
    if entry is not None:
        return entry
    db = _installed.load(_state.get_active_profile_id())
    inst = db.get(addon_id)
    if inst is not None:
        return {"id": addon_id, **inst}
    return None


@method("addon.versions")
def _addon_versions(params: dict[str, Any]) -> dict[str, Any]:
    """List selectable download versions for an addon (GitHub / CurseForge).

    params: {id: str}
    returns: {id, versions: [{label, url, version, type}], error?}
    """
    from wowusky import orchestrator as _orch

    addon_id = params.get("id")
    if not addon_id:
        raise ValueError("id is required")
    entry = _resolve_addon(addon_id)
    if entry is None:
        return {"id": addon_id, "versions": []}
    try:
        versions = _orch.list_addon_versions(entry)
    except Exception as exc:  # noqa: BLE001 — version lookup must never crash the panel
        _log("versions error:", traceback.format_exc())
        return {"id": addon_id, "versions": [], "error": f"{type(exc).__name__}: {exc}"}
    return {"id": addon_id, "versions": versions}


@method("addon.installVersion")
def _addon_install_version(params: dict[str, Any]) -> dict[str, Any]:
    """Install a specific version of an addon from a direct ZIP url.

    params: {id: str, url: str, label?: str}
    returns: {ok, log, error?, ...installed_list}
    """
    from wowusky import orchestrator as _orch
    from wowusky.core import state as _state

    addon_id = params.get("id")
    url = params.get("url")
    label = params.get("label") or params.get("version") or "manual"
    if not addon_id or not url:
        raise ValueError("id and url are required")

    entry = _resolve_addon(addon_id)
    if entry is None:
        return {"ok": False, "error": f"addon not found: {addon_id}"}

    log_fn, progress_fn, lines = _action_callbacks(addon_id)
    try:
        ok = _orch.install_addon_version(entry, str(url), str(label), log=log_fn, progress=progress_fn)
    except Exception as exc:  # noqa: BLE001 — report failure to the UI
        _log("installVersion error:", traceback.format_exc())
        _notify("action.done", {"id": addon_id, "ok": False, "error": str(exc)})
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "log": lines}

    _notify("action.done", {"id": addon_id, "ok": bool(ok)})
    profile = _state.get_active_profile_id()
    return {"ok": bool(ok), "log": lines, **_installed_list({"profile": profile})}


@method("installed.updateAll")
def _installed_update_all(params: dict[str, Any]) -> dict[str, Any]:
    """Update installed addons that have a newer version available.

    params: {ids?: [str]}  — when omitted, every addon with an available
    update is updated. When given, only those ids are updated.
    returns: {updated: [str], failed: [str], ...installed_list}
    """
    from wowusky import orchestrator as _orch
    from wowusky.core import state as _state

    targets = params.get("ids")
    if not targets:
        targets = list(_installed_updates({}).get("updates", {}).keys())

    from wowusky.core import installed as _installed
    addons_path = _state.get_addons_path()
    profile = _state.get_active_profile_id()
    before = _installed.load(profile)
    updated: list[str] = []
    failed: list[str] = []
    for addon_id in targets:
        entry = _orch.find_addon_by_id(addon_id)
        if entry is None:
            failed.append(addon_id)
            continue
        log_fn, progress_fn, _lines = _action_callbacks(addon_id)
        try:
            _orch.install_addon(entry, addons_path, log=log_fn, progress=progress_fn)
            updated.append(addon_id)
            _notify("action.done", {"id": addon_id, "ok": True})
        except Exception as exc:  # noqa: BLE001 — keep going through the rest
            _log("updateAll error:", traceback.format_exc())
            failed.append(addon_id)
            _notify("action.done", {"id": addon_id, "ok": False, "error": str(exc)})

    profile = _state.get_active_profile_id()
    after = _installed.load(profile)
    for addon_id in updated:
        _record_history(profile, "update", addon_id,
                        name=after.get(addon_id, {}).get("name") or addon_id,
                        from_version=before.get(addon_id, {}).get("version", ""),
                        to_version=after.get(addon_id, {}).get("version", ""))
    return {"updated": updated, "failed": failed, **_installed_list({"profile": profile})}


# ---------------------------------------------------------------------------
# Backup restore
# ---------------------------------------------------------------------------


@method("backups.restore")
def _backups_restore(params: dict[str, Any]) -> dict[str, Any]:
    """Restore a backup ZIP.

    params: {path: str, addon_id?: str}
      - with addon_id  -> restore a per-addon snapshot (rollback)
      - without        -> restore a full-profile backup
    returns: {ok: bool, log: [str], error?: str}
    """
    from wowusky.core import backup as _backup
    from wowusky.core import state as _state

    path = params.get("path")
    if not path:
        raise ValueError("path is required")
    addon_id = params.get("addon_id")
    # The UI correlates restore events by the backup path.
    token = str(path)

    log_fn, _progress_fn, lines = _action_callbacks(token)
    try:
        addons_path = _state.get_addons_path()
        if addon_id:
            ok = _backup.rollback_addon_to_backup(addon_id, path, addons_path, log=log_fn)
        else:
            ok = _backup.restore_full_backup(path, log=log_fn)
    except Exception as exc:  # noqa: BLE001 — report restore failure to the UI
        _log("restore error:", traceback.format_exc())
        _notify("action.done", {"id": token, "ok": False, "error": str(exc)})
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "log": lines}

    _notify("action.done", {"id": token, "ok": bool(ok)})
    return {"ok": bool(ok), "log": lines}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@method("health.check")
def _health_check(params: dict[str, Any]) -> dict[str, Any]:
    """Run the offline catalog health check (no network I/O).

    Verifies every catalog entry has a known provider and resolves to a
    reference. params: {scope?: "all"} (reserved for future installed-only).
    returns: {total, ok, failed, results: [{id, name, provider, status, detail}]}
    """
    from wowusky.catalog import load_catalog
    from wowusky.tools.health_check import check_addon_offline

    catalog = load_catalog()
    by_id = {e.get("id"): e for e in catalog}

    results: list[dict[str, Any]] = []
    ok = 0
    for entry in catalog:
        r = check_addon_offline(entry)
        failed = "error" in r
        if not failed:
            ok += 1
        src_entry = by_id.get(r.get("id"), {})
        results.append(
            {
                "id": r.get("id"),
                "name": src_entry.get("name", r.get("id")),
                "provider": r.get("provider", ""),
                "status": "error" if failed else "ok",
                "detail": r.get("error") if failed else r.get("resolved", ""),
            }
        )

    # Failures first, then alphabetical, so problems surface at the top.
    results.sort(key=lambda r: (r["status"] != "error", str(r["name"]).lower()))
    return {
        "total": len(catalog),
        "ok": ok,
        "failed": len(catalog) - ok,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Installation health & orphan management (#59 / #60)
# ---------------------------------------------------------------------------


def _list_disk_addon_folders(addons_path: str) -> set[str]:
    """Top-level AddOns subfolders that carry a readable .toc."""
    import os

    from wowusky.core.toc import read_addon_toc

    out: set[str] = set()
    if not addons_path or not os.path.isdir(addons_path):
        return out
    for f in os.listdir(addons_path):
        full = os.path.join(addons_path, f)
        if not os.path.isdir(full) or f.startswith("."):
            continue
        if read_addon_toc(full):
            out.add(f)
    return out


def _compute_install_health(profile: str) -> dict[str, Any]:
    """Reconcile the profile's installed DB against what is on disk.

    Returns problems bucketed by kind:
      * ``missing`` — DB entries whose folders are gone from disk
      * ``duplicates`` — a folder claimed by more than one DB entry
      * ``orphans`` — on-disk addon folders not tracked by any DB entry
        (with a catalog-match guess where possible)
    """
    import os

    from wowusky.catalog import load_catalog
    from wowusky.core import installed as _installed
    from wowusky.core import state as _state

    try:
        addons_path = _state.get_addons_path()
    except Exception:  # noqa: BLE001
        addons_path = ""

    db = _installed.load(profile)
    disk = _list_disk_addon_folders(addons_path) if addons_path else set()

    # Missing: every recorded folder absent from disk.
    missing: list[dict[str, Any]] = []
    claimed: dict[str, list[str]] = {}
    for aid, entry in db.items():
        folders = entry.get("folders") or []
        gone = [f for f in folders if not os.path.isdir(os.path.join(addons_path, f))] if addons_path else folders
        if folders and gone and len(gone) == len(folders):
            missing.append({"id": aid, "name": entry.get("name") or aid, "folders": folders})
        for f in folders:
            claimed.setdefault(f, []).append(aid)

    # Duplicates: one folder claimed by 2+ DB entries.
    duplicates = [
        {"folder": f, "ids": ids}
        for f, ids in sorted(claimed.items())
        if len(ids) > 1
    ]

    # Orphans: on-disk addon folders not claimed by any DB entry.
    known = set(claimed.keys())
    catalog = load_catalog()
    by_folder = {}
    by_lower = {}
    for addon in catalog:
        for folder in addon.get("folders", []):
            by_folder[folder] = addon
            by_lower[folder.lower()] = addon
    orphans: list[dict[str, Any]] = []
    for f in sorted(disk - known):
        match = by_folder.get(f) or by_lower.get(f.lower())
        orphans.append({
            "folder": f,
            "match_id": match.get("id") if match else None,
            "match_name": match.get("name") if match else None,
        })

    total = len(missing) + len(duplicates) + len(orphans)
    return {
        "profile": profile,
        "addons_path": addons_path,
        "missing": missing,
        "duplicates": duplicates,
        "orphans": orphans,
        "problem_count": total,
    }


@method("health.installed")
def _health_installed(params: dict[str, Any]) -> dict[str, Any]:
    """Inspect the active (or given) profile's install for problems (#59).

    params: {profile?: str}
    returns: {profile, addons_path, missing, duplicates, orphans, problem_count}
    """
    from wowusky.core import state as _state

    profile = params.get("profile") or _state.get_active_profile_id()
    return _compute_install_health(profile)


@method("health.fixResync")
def _health_fix_resync(_params: dict[str, Any]) -> dict[str, Any]:
    """Reconcile the DB with the filesystem (drop missing, adopt orphans).

    returns: {ok, ...health.installed}
    """
    from wowusky.catalog import load_catalog
    from wowusky.core import scan as _scan
    from wowusky.core import state as _state

    try:
        addons_path = _state.get_addons_path()
        _scan.sync_filesystem_with_db(addons_path, load_catalog())
    except Exception as exc:  # noqa: BLE001
        _log("health resync error:", traceback.format_exc())
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    profile = _state.get_active_profile_id()
    return {"ok": True, **_compute_install_health(profile)}


@method("health.removeEntry")
def _health_remove_entry(params: dict[str, Any]) -> dict[str, Any]:
    """Drop a dangling DB entry (folders already gone) without touching disk.

    params: {id: str}
    returns: {ok, ...health.installed}
    """
    from wowusky.core import installed as _installed
    from wowusky.core import state as _state

    addon_id = params.get("id")
    if not addon_id:
        raise ValueError("id is required")
    profile = _state.get_active_profile_id()
    db = _installed.load(profile)
    if addon_id in db:
        del db[addon_id]
        _installed.save(profile, db)
    return {"ok": True, **_compute_install_health(profile)}


@method("orphans.list")
def _orphans_list(params: dict[str, Any]) -> dict[str, Any]:
    """List on-disk addon folders not tracked in the DB (#60).

    params: {profile?: str}
    returns: {profile, orphans: [{folder, match_id, match_name}]}
    """
    from wowusky.core import state as _state

    profile = params.get("profile") or _state.get_active_profile_id()
    health = _compute_install_health(profile)
    return {"profile": profile, "orphans": health["orphans"]}


@method("orphans.adopt")
def _orphans_adopt(params: dict[str, Any]) -> dict[str, Any]:
    """Register an orphan folder into the installed DB.

    Matches the folder to the catalog where possible (recording the real
    catalog id), otherwise records it as an ``external`` discovery.
    params: {folder: str}
    returns: {ok, adopted_id, ...installed_list}
    """
    import os

    from wowusky.catalog import load_catalog
    from wowusky.core import installed as _installed
    from wowusky.core import state as _state
    from wowusky.core.toc import read_addon_toc

    folder = params.get("folder")
    if not folder:
        raise ValueError("folder is required")
    addons_path = _state.get_addons_path()
    full = os.path.join(addons_path, folder)
    toc = read_addon_toc(full)
    if not toc:
        return {"ok": False, "error": f"no readable .toc in {folder}"}

    catalog = load_catalog()
    by_folder = {}
    by_lower = {}
    for addon in catalog:
        for fol in addon.get("folders", []):
            by_folder[fol] = addon
            by_lower[fol.lower()] = addon
    match = by_folder.get(folder) or by_lower.get(folder.lower())

    profile = _state.get_active_profile_id()
    db = _installed.load(profile)
    if match:
        actual = [f for f in match.get("folders", []) if os.path.isdir(os.path.join(addons_path, f))]
        adopted_id = match["id"]
        db[adopted_id] = {
            "name": match.get("name", folder),
            "version": toc.get("version") or "unknown",
            "folders": actual or [folder],
            "source": match.get("provider") or match.get("source") or "unknown",
            "interface": toc.get("interface"),
            "discovered": True,
        }
    else:
        adopted_id = "fs_" + folder.lower().replace(" ", "_")
        db[adopted_id] = {
            "name": toc.get("title") or folder,
            "version": toc.get("version") or "unknown",
            "folders": [folder],
            "source": "external",
            "interface": toc.get("interface"),
            "discovered": True,
        }
    _installed.save(profile, db)
    return {"ok": True, "adopted_id": adopted_id, **_installed_list({"profile": profile})}


@method("orphans.remove")
def _orphans_remove(params: dict[str, Any]) -> dict[str, Any]:
    """Delete an orphan folder from disk (a backup is taken first).

    params: {folder: str}
    returns: {ok, orphans: [...]}
    """
    import os
    import shutil

    from wowusky.core import state as _state
    from wowusky.core.backup import backup_addon_folders

    folder = params.get("folder")
    if not folder:
        raise ValueError("folder is required")
    addons_path = _state.get_addons_path()
    full = os.path.join(addons_path, folder)
    if not os.path.isdir(full):
        return {"ok": False, "error": f"no such folder: {folder}"}
    try:
        backup_addon_folders("orphan_" + folder, {"folders": [folder]}, addons_path, _log)
        if not _state.is_dry_run():
            shutil.rmtree(full)
    except Exception as exc:  # noqa: BLE001
        _log("orphan remove error:", traceback.format_exc())
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    profile = _state.get_active_profile_id()
    return {"ok": True, "orphans": _compute_install_health(profile)["orphans"]}


@method("addon.updateDiff")
def _addon_update_diff(params: dict[str, Any]) -> dict[str, Any]:
    """Preview what an update would change for an installed addon (#61).

    Compares the installed folder set against the catalog package's folder
    set and reports the version transition.
    params: {id: str}
    returns: {id, name, from_version, to_version, added: [str], removed: [str], same: [str]}
    """
    from wowusky import orchestrator as _orch
    from wowusky.core import installed as _installed
    from wowusky.core import state as _state

    addon_id = params.get("id")
    if not addon_id:
        raise ValueError("id is required")

    profile = _state.get_active_profile_id()
    db = _installed.load(profile)
    inst = db.get(addon_id) or {}
    cat = _orch.find_addon_by_id(addon_id) or {}

    cur_folders = set(inst.get("folders") or [])
    new_folders = set(cat.get("folders") or []) or cur_folders
    from_version = inst.get("version") or "unknown"
    try:
        to_version = _orch.get_latest_version(cat) if cat else None
    except Exception:  # noqa: BLE001
        to_version = None

    return {
        "id": addon_id,
        "name": inst.get("name") or cat.get("name") or addon_id,
        "from_version": from_version,
        "to_version": to_version or from_version,
        "added": sorted(new_folders - cur_folders),
        "removed": sorted(cur_folders - new_folders),
        "same": sorted(cur_folders & new_folders),
    }


# ---------------------------------------------------------------------------
# Addon-set export / import
# ---------------------------------------------------------------------------


@method("addons.exportSet")
def _addons_export_set(params: dict[str, Any]) -> dict[str, Any]:
    """Export the installed addon list for a profile as a portable JSON snapshot.

    params: {profile?: str}
    returns: {data: {...}, filename: str, json: str}
    """
    import json as _json

    from wowusky.core import addonset as _addonset
    from wowusky.core import state as _state

    profile = params.get("profile") or _state.get_active_profile_id()
    data = _addonset.export_addon_set(profile)
    prof_name = data["profile"].get("name", profile).replace(" ", "-").lower()
    filename = f"wowusky-{prof_name}-addons.json"
    return {
        "data": data,
        "filename": filename,
        "json": _json.dumps(data, indent=2, ensure_ascii=False),
    }


@method("addons.importSet")
def _addons_import_set(params: dict[str, Any]) -> dict[str, Any]:
    """Parse an exported addon set and return a per-addon conflict preview.

    params: {data: object, profile?: str}
    returns: {profile_name, profile, preview: [{id, name, version, installed_version, source, status}]}
    """
    from wowusky.core import addonset as _addonset
    from wowusky.core import state as _state

    raw = params.get("data")
    if not isinstance(raw, dict):
        raise ValueError("data must be an object")
    profile = params.get("profile") or _state.get_active_profile_id()
    preview = _addonset.import_addon_set_preview(raw, profile)
    prof_data = _state.load_profiles()
    prof = prof_data.get("profiles", {}).get(profile, {})
    src_prof = raw.get("profile", {})
    return {
        "profile": profile,
        "profile_name": prof.get("name", profile),
        "source_profile": src_prof.get("name", src_prof.get("id", "")),
        "preview": preview,
    }


@method("addons.importSet.apply")
def _addons_import_set_apply(params: dict[str, Any]) -> dict[str, Any]:
    """Apply an addon-set import (writes DB entries, no downloads).

    params: {data: object, profile?: str, skip?: [str]}
    returns: {imported, skipped, ...installed_list}
    """
    from wowusky.core import addonset as _addonset
    from wowusky.core import state as _state

    raw = params.get("data")
    if not isinstance(raw, dict):
        raise ValueError("data must be an object")
    profile = params.get("profile") or _state.get_active_profile_id()
    skip = list(params.get("skip") or [])
    result = _addonset.import_addon_set_apply(raw, profile, skip)
    return {**result, **_installed_list({"profile": profile})}


# ---------------------------------------------------------------------------
# Dependency preview
# ---------------------------------------------------------------------------


@method("addon.deps")
def _addon_deps(params: dict[str, Any]) -> dict[str, Any]:
    """List the catalog dependencies installing an addon would pull in.

    params: {id: str}
    returns: {id, deps: [{id, name, installed}], missing: [str]}
    """
    from wowusky import orchestrator as _orch

    addon_id = params.get("id")
    if not addon_id:
        raise ValueError("id is required")
    entry = _orch.find_addon_by_id(addon_id)
    if entry is None:
        return {"id": addon_id, "deps": [], "missing": []}
    return {"id": addon_id, **_orch.dependency_preview(entry)}


@method("addon.conflicts")
def _addon_conflicts(params: dict[str, Any]) -> dict[str, Any]:
    """List installed addons that conflict with the given catalog addon.

    params: {id: str}
    returns: {id, conflicts: [{id, name}]}
    """
    from wowusky import orchestrator as _orch

    addon_id = params.get("id")
    if not addon_id:
        raise ValueError("id is required")
    entry = _orch.find_addon_by_id(addon_id)
    if entry is None:
        return {"id": addon_id, "conflicts": []}
    return {"id": addon_id, **_orch.conflict_check(entry)}


# ---------------------------------------------------------------------------
# Addon-set export / import (#44) and backup diff (#45)
# ---------------------------------------------------------------------------


@method("set.export")
def _set_export(_params: dict[str, Any]) -> dict[str, Any]:
    """Return a portable addon-set snapshot of the active profile as JSON text.

    returns: {data: str, count: int}
    """
    import json as _json

    from wowusky.core import addonset as _addonset

    snapshot = _addonset.export_addon_set()
    return {"data": _json.dumps(snapshot, indent=2), "count": snapshot.get("count", 0)}


@method("set.importPreview")
def _set_import_preview(params: dict[str, Any]) -> dict[str, Any]:
    """Parse pasted addon-set JSON and report a per-addon conflict preview.

    params: {data: str}
    returns: {ok, items?: [{id, name, version, installed_version, source, status}], error?}
    """
    import json as _json

    from wowusky.core import addonset as _addonset

    raw = params.get("data")
    if not raw:
        raise ValueError("data is required")
    try:
        parsed = _json.loads(raw)
        items = _addonset.import_addon_set_preview(parsed)
    except (ValueError, _json.JSONDecodeError) as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "items": items}


@method("set.importApply")
def _set_import_apply(params: dict[str, Any]) -> dict[str, Any]:
    """Apply a pasted addon-set into the installed DB (no downloads).

    params: {data: str, skip_ids?: [str]}
    returns: {ok, imported?, skipped?, error?}
    """
    import json as _json

    from wowusky.core import addonset as _addonset

    raw = params.get("data")
    if not raw:
        raise ValueError("data is required")
    skip_ids = params.get("skip_ids") or []
    try:
        parsed = _json.loads(raw)
        result = _addonset.import_addon_set_apply(parsed, skip_ids=skip_ids)
    except (ValueError, _json.JSONDecodeError) as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, **result}


@method("backups.diff")
def _backups_diff(params: dict[str, Any]) -> dict[str, Any]:
    """Diff two backup archives by their ZIP indices (no extraction).

    params: {a: str, b: str}  (two backup ZIP paths)
    returns: {added: [str], removed: [str], changed: [{path, size_a, size_b}]}
    """
    from wowusky.core import backup as _backup

    a = params.get("a")
    b = params.get("b")
    if not a or not b:
        raise ValueError("a and b paths are required")
    return _backup.diff_backups(a, b)


# ---------------------------------------------------------------------------
# Bulk remove
# ---------------------------------------------------------------------------


@method("installed.removeMany")
def _installed_remove_many(params: dict[str, Any]) -> dict[str, Any]:
    """Remove several installed addons in one action (backups are taken).

    params: {ids: [str]}
    returns: {removed: [str], failed: [str], ...installed_list}
    """
    from wowusky import orchestrator as _orch
    from wowusky.core import state as _state

    ids = list(params.get("ids") or [])
    if not ids:
        raise ValueError("ids is required")

    from wowusky.core import installed as _installed
    addons_path = _state.get_addons_path()
    profile = _state.get_active_profile_id()
    before = _installed.load(profile)
    removed: list[str] = []
    failed: list[str] = []
    for addon_id in ids:
        log_fn, _progress_fn, _lines = _action_callbacks(addon_id)
        try:
            _orch.uninstall_addon(addon_id, addons_path, log=log_fn)
            removed.append(addon_id)
            _notify("action.done", {"id": addon_id, "ok": True})
        except Exception as exc:  # noqa: BLE001 — keep going through the rest
            _log("removeMany error:", traceback.format_exc())
            failed.append(addon_id)
            _notify("action.done", {"id": addon_id, "ok": False, "error": str(exc)})

    profile = _state.get_active_profile_id()
    for addon_id in removed:
        _record_history(profile, "remove", addon_id,
                        name=before.get(addon_id, {}).get("name") or addon_id,
                        from_version=before.get(addon_id, {}).get("version", ""))
    return {"removed": removed, "failed": failed, **_installed_list({"profile": profile})}


# ---------------------------------------------------------------------------
# Notes & Favorites
# ---------------------------------------------------------------------------


@method("installed.setNote")
def _installed_set_note(params: dict[str, Any]) -> dict[str, Any]:
    """Persist a personal note for an installed addon.

    params: {id: str, note: str}
    returns: {ok: bool}
    """
    from wowusky.core import installed as _installed
    from wowusky.core import state as _state

    addon_id = params.get("id")
    note = str(params.get("note") or "")
    if not addon_id:
        raise ValueError("id is required")
    profile = _state.get_active_profile_id()
    data = _installed.load(profile)
    if addon_id not in data:
        raise ValueError(f"addon {addon_id!r} not installed")
    data[addon_id]["note"] = note
    _installed.save(profile, data)
    return {"ok": True}


@method("favorites.list")
def _favorites_list(_params: dict[str, Any]) -> dict[str, Any]:
    """Return the set of favorited catalog IDs.

    returns: {ids: [str]}
    """
    from wowusky.core import favorites as _fav

    return {"ids": sorted(_fav.load())}


@method("favorites.toggle")
def _favorites_toggle(params: dict[str, Any]) -> dict[str, Any]:
    """Toggle the favorite state for a catalog addon.

    params: {id: str}
    returns: {id: str, favorite: bool}
    """
    from wowusky.core import favorites as _fav

    addon_id = params.get("id")
    if not addon_id:
        raise ValueError("id is required")
    now_fav = _fav.toggle(addon_id)
    return {"id": addon_id, "favorite": now_fav}


# ---------------------------------------------------------------------------
# Import from Downloads
# ---------------------------------------------------------------------------


@method("downloads.scan")
def _downloads_scan(params: dict[str, Any]) -> dict[str, Any]:
    """List ZIPs in the Downloads dir with guessed catalog associations.

    params: {limit?: int}
    returns: {dir, items: [{path, name, mtime, guess: {id, name}|null}]}
    """
    from wowusky import orchestrator as _orch

    limit = int(params.get("limit") or 25)
    return {"dir": _orch.downloads_dir(), "items": _orch.scan_download_zips_annotated(limit)}


@method("downloads.import")
def _downloads_import(params: dict[str, Any]) -> dict[str, Any]:
    """Import a downloaded ZIP into the active profile (manual install).

    params: {path: str, id?: str, name?: str}
      - id/name: optional catalog association (from downloads.scan guess).
    returns: {ok, log, error?, ...installed_list}
    """
    from wowusky import orchestrator as _orch
    from wowusky.core import state as _state

    path = params.get("path")
    if not path:
        raise ValueError("path is required")
    token = str(path)
    addons_path = _state.get_addons_path()
    log_fn, _progress_fn, lines = _action_callbacks(token)
    try:
        addon_id = _orch.import_zip_file(
            path, addons_path, name=params.get("name"), log=log_fn,
        )
    except Exception as exc:  # noqa: BLE001 — report import failure to the UI
        _log("import error:", traceback.format_exc())
        _notify("action.done", {"id": token, "ok": False, "error": str(exc)})
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "log": lines}

    _notify("action.done", {"id": token, "ok": True})
    profile = _state.get_active_profile_id()
    return {"ok": True, "id": addon_id, "log": lines, **_installed_list({"profile": profile})}


# ---------------------------------------------------------------------------
# Scheduled updates (systemd user timer)
# ---------------------------------------------------------------------------


@method("schedule.status")
def _schedule_status(_params: dict[str, Any]) -> dict[str, Any]:
    """Report the systemd update-timer status. returns: see core.schedule.status."""
    from wowusky.core import schedule as _schedule

    return _schedule.status()


@method("schedule.enable")
def _schedule_enable(params: dict[str, Any]) -> dict[str, Any]:
    """Install + enable the update timer. params: {interval?: daily|weekly|hourly}."""
    from wowusky.core import schedule as _schedule

    return _schedule.enable(params.get("interval") or "daily")


@method("schedule.disable")
def _schedule_disable(_params: dict[str, Any]) -> dict[str, Any]:
    """Disable + remove the update timer."""
    from wowusky.core import schedule as _schedule

    return _schedule.disable()


# ---------------------------------------------------------------------------
# Dispatch loop
# ---------------------------------------------------------------------------

# JSON-RPC error codes (subset)
_PARSE_ERROR = -32700
_INVALID_REQUEST = -32600
_METHOD_NOT_FOUND = -32601
_INTERNAL_ERROR = -32603


def _write(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _notify(notify_method: str, params: dict[str, Any]) -> None:
    """Emit a JSON-RPC notification (no ``id``) — a streaming event.

    The Electron main process forwards these to the renderer via
    ``bridge:notify``; the UI uses them to show live install/restore progress.
    """
    _write({"jsonrpc": "2.0", "method": notify_method, "params": params})


def _error(req_id: Any, code: int, message: str) -> None:
    _write({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def _handle_line(line: str) -> None:
    line = line.strip()
    if not line:
        return
    try:
        req = json.loads(line)
    except json.JSONDecodeError as exc:
        _error(None, _PARSE_ERROR, f"parse error: {exc}")
        return

    if not isinstance(req, dict) or req.get("jsonrpc") != "2.0":
        _error(req.get("id") if isinstance(req, dict) else None,
               _INVALID_REQUEST, "invalid request")
        return

    req_id = req.get("id")
    name = req.get("method")
    params = req.get("params") or {}
    if not isinstance(params, dict):
        _error(req_id, _INVALID_REQUEST, "params must be an object")
        return

    fn = _METHODS.get(name)
    if fn is None:
        _error(req_id, _METHOD_NOT_FOUND, f"method not found: {name}")
        return

    try:
        result = fn(params)
    except Exception as exc:  # noqa: BLE001 — report any handler failure as RPC error
        _log("handler error:", traceback.format_exc())
        _error(req_id, _INTERNAL_ERROR, f"{type(exc).__name__}: {exc}")
        return

    # Notifications (no id) get no response.
    if req_id is not None:
        _write({"jsonrpc": "2.0", "id": req_id, "result": result})


def main() -> None:
    _log("ready")
    for line in sys.stdin:
        _handle_line(line)
    _log("stdin closed, exiting")


if __name__ == "__main__":
    main()
