"""Per-profile installed-addon database.

Each profile keeps its own JSON file at
``~/.local/share/wowusky/installed/<profile_id>.json``::

    {
      "<addon_id>": {
        "name":         "ElvUI",
        "version":      "15.13",
        "folders":      ["ElvUI", "ElvUI_Options", "ElvUI_Libraries"],
        "source":       "tukui",
        "interface":    20505,
        "sha256":       "abc123…",     # of the downloaded ZIP
        "installed_at": 1716200000,
        "discovered":   false          # true = found on disk, not installed by app
      }
    }
"""

from __future__ import annotations

import time
from typing import Any

from wowusky.core.config import read_json, write_json
from wowusky.core.paths import ensure_dirs, installed_file_for


def load(profile_id: str) -> dict[str, dict]:
    ensure_dirs()
    return read_json(installed_file_for(profile_id), {})


def save(profile_id: str, data: dict[str, dict]) -> None:
    write_json(installed_file_for(profile_id), data)


def get_entry(profile_id: str, addon_id: str) -> dict | None:
    return load(profile_id).get(addon_id)


def upsert(profile_id: str, addon_id: str, entry: dict[str, Any]) -> None:
    """Record an addon as installed for the given profile.

    ``installed_at`` is auto-filled when missing.
    """
    data = load(profile_id)
    entry = dict(entry)
    entry.setdefault("installed_at", time.time())
    data[addon_id] = entry
    save(profile_id, data)


def remove(profile_id: str, addon_id: str) -> bool:
    data = load(profile_id)
    if addon_id not in data:
        return False
    del data[addon_id]
    save(profile_id, data)
    return True


def addon_ids(profile_id: str) -> list[str]:
    return list(load(profile_id).keys())


def count(profile_id: str) -> int:
    return len(load(profile_id))
