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


def _entry_to_addon(entry: dict[str, Any]) -> dict[str, Any]:
    """Project a catalog manifest entry onto the shape the UI expects."""
    name = entry.get("name", entry.get("id", "?"))
    provider = entry.get("provider", "")
    return {
        "id": entry.get("id"),
        "name": name,
        "author": entry.get("author", "Unknown"),
        "category": entry.get("category", "Other"),
        "description": entry.get("description", ""),
        "source": _PROVIDER_SOURCE.get(provider, "local"),
        "glyph": (name[:1] or "?").upper(),
        "flavors": entry.get("flavors", []),
        "folders": entry.get("folders", []),
        "depends": entry.get("depends", []),
    }


@method("catalog.search")
def _catalog_search(params: dict[str, Any]) -> dict[str, Any]:
    """Filter the bundled manifest catalog by query + category.

    params: {query?: str, category?: str, limit?: int}
    returns: {total: int, count: int, categories: [str], items: [addon]}
    """
    from wowusky.catalog import load_catalog
    from wowusky.core import installed as _installed
    from wowusky.core import state as _state

    catalog = load_catalog()
    query = str(params.get("query", "")).strip().lower()
    category = params.get("category") or "All"
    limit = int(params.get("limit", 200))

    try:
        installed_ids = set(_installed.load(_state.get_active_profile_id()).keys())
    except Exception:  # noqa: BLE001 — search must work even without a profile
        installed_ids = set()

    categories = sorted({e.get("category", "Other") for e in catalog})

    items: list[dict[str, Any]] = []
    for entry in catalog:
        if category != "All" and entry.get("category") != category:
            continue
        if query:
            hay = f"{entry.get('name', '')} {entry.get('description', '')}".lower()
            if query not in hay:
                continue
        addon = _entry_to_addon(entry)
        addon["installed"] = addon["id"] in installed_ids
        items.append(addon)

    total = len(items)
    items.sort(key=lambda a: a["name"].lower())
    return {
        "total": len(catalog),
        "count": total,
        "categories": ["All", *categories],
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

    cf_key = _state.get_curseforge_api_key() or ""
    return {
        "addons_path": addons_path,
        "wtf_path": wtf_path,
        "dry_run": bool(_state.is_dry_run()),
        "curseforge_api_key_set": bool(cf_key),
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
            "type": a.get("type", "WeakAura"),
            "note": a.get("note", ""),
            "url": a.get("url", f"https://wago.io/{slug}"),
        }
        for slug, a in auras.items()
    ]
    items.sort(key=lambda x: str(x["name"]).lower())
    return {"count": len(items), "items": items}


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
    log_fn, progress_fn, lines = _action_callbacks(addon_id)
    try:
        _orch.install_addon(entry, addons_path, log=log_fn, progress=progress_fn)
    except Exception as exc:  # noqa: BLE001 — report install failure to the UI
        _log("install error:", traceback.format_exc())
        _notify("action.done", {"id": addon_id, "ok": False, "error": str(exc)})
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "log": lines}

    _notify("action.done", {"id": addon_id, "ok": True})
    profile = _state.get_active_profile_id()
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
    log_fn, _progress_fn, lines = _action_callbacks(addon_id)
    try:
        _orch.uninstall_addon(addon_id, addons_path, log=log_fn)
    except Exception as exc:  # noqa: BLE001 — report removal failure to the UI
        _log("remove error:", traceback.format_exc())
        _notify("action.done", {"id": addon_id, "ok": False, "error": str(exc)})
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "log": lines}

    _notify("action.done", {"id": addon_id, "ok": True})
    profile = _state.get_active_profile_id()
    return {"ok": True, "log": lines, **_installed_list({"profile": profile})}


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
