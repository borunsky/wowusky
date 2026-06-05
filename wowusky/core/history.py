"""Persistent change history / audit log (#67).

Records every install / update / remove as an append-only JSONL file per
profile under ``$DATA_DIR/history/<profile_id>.jsonl``. Unlike the rotating
activity log (session-scoped), this survives restarts and is queryable by
addon and time range.
"""

from __future__ import annotations

import json
import os
import time

VALID_ACTIONS = frozenset({"install", "update", "remove"})


def _history_dir() -> str:
    from wowusky.core import paths as _paths

    return os.path.join(str(_paths.DATA_DIR), "history")


def _history_file(profile_id: str) -> str:
    return os.path.join(_history_dir(), f"{profile_id}.jsonl")


def record(profile_id: str, action: str, addon_id: str, *,
           name: str = "", from_version: str = "", to_version: str = "") -> dict:
    """Append one history entry. Unknown actions are recorded verbatim."""
    rec = {
        "ts": int(time.time()),
        "action": action,
        "id": addon_id,
        "name": name or addon_id,
        "from": from_version or "",
        "to": to_version or "",
    }
    os.makedirs(_history_dir(), exist_ok=True)
    with open(_history_file(profile_id), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def list_history(profile_id: str, *, addon: str | None = None,
                 since: int | None = None, limit: int = 500) -> list[dict]:
    """Return history entries newest-first, optionally filtered."""
    path = _history_file(profile_id)
    out: list[dict] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if addon and rec.get("id") != addon:
                    continue
                if since is not None and rec.get("ts", 0) < since:
                    continue
                out.append(rec)
    except OSError:
        return []
    out.reverse()
    return out[:limit]


def clear_history(profile_id: str) -> bool:
    """Delete a profile's history file. Returns True if one existed."""
    path = _history_file(profile_id)
    try:
        os.remove(path)
        return True
    except OSError:
        return False
