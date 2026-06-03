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
