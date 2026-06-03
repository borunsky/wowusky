"""JSON-RPC bridge between the Electron desktop shell and the Python core.

The Electron main process spawns ``python -m wowusky.bridge`` and talks to it
over newline-delimited JSON-RPC 2.0 on stdin/stdout. This keeps the entire
addon-management logic (``core``, ``orchestrator``, ``providers``, ``catalog``)
in Python while the redesigned UI lives in the web frontend.

The protocol is deliberately tiny:

  * Request:  ``{"jsonrpc": "2.0", "id": <n>, "method": "<name>", "params": {…}}``
  * Response: ``{"jsonrpc": "2.0", "id": <n>, "result": <any>}``
              ``{"jsonrpc": "2.0", "id": <n>, "error": {"code": …, "message": …}}``
  * Notify:   ``{"jsonrpc": "2.0", "method": "<event>", "params": {…}}`` (no id)

Notifications (no ``id``) are used for streaming progress in later phases.
"""

from __future__ import annotations
