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

    catalog = load_catalog()
    query = str(params.get("query", "")).strip().lower()
    category = params.get("category") or "All"
    limit = int(params.get("limit", 200))

    categories = sorted({e.get("category", "Other") for e in catalog})

    items: list[dict[str, Any]] = []
    for entry in catalog:
        if category != "All" and entry.get("category") != category:
            continue
        if query:
            hay = f"{entry.get('name', '')} {entry.get('description', '')}".lower()
            if query not in hay:
                continue
        items.append(_entry_to_addon(entry))

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
