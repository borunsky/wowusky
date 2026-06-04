"""Catalog-wide favorites (independent of profiles).

Stored as a JSON array of addon IDs in FAVORITES_FILE.
"""

from __future__ import annotations

from wowusky.core.config import read_json, write_json
from wowusky.core.paths import FAVORITES_FILE, ensure_dirs


def load() -> set[str]:
    ensure_dirs()
    data = read_json(FAVORITES_FILE, [])
    return set(data) if isinstance(data, list) else set()


def save(ids: set[str]) -> None:
    write_json(FAVORITES_FILE, sorted(ids))


def toggle(addon_id: str) -> bool:
    """Toggle favorite state. Returns True if now favorited."""
    ids = load()
    if addon_id in ids:
        ids.discard(addon_id)
        result = False
    else:
        ids.add(addon_id)
        result = True
    save(ids)
    return result


def is_favorite(addon_id: str) -> bool:
    return addon_id in load()
