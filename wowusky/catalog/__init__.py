"""Catalog loader: builtin + community + user manifests.

wowusky's addon catalog is built at startup from three sources:

  1. ``wowusky/catalog/manifests/builtin.json`` — the curated default
     list that ships with the application.
  2. ``wowusky/catalog/manifests/*.json`` (other files) — community
     seed manifests included in the package.
  3. ``~/.local/share/wowusky/manifests/*.json`` — user-supplied
     manifests that override or extend everything else.

Entries are keyed by ``id``. Later sources overwrite earlier ones so
users can fix broken entries without forking the app.

A manifest file looks like::

    {
      "name": "my-manifest",
      "version": "1.0",
      "addons": [
        {
          "id": "weakauras",
          "name": "WeakAuras 2",
          "provider": "github",
          "repo": "WeakAuras/WeakAuras2",
          "category": "Buffs",
          "flavors": ["all"],
          "folders": ["WeakAuras", "WeakAurasOptions"],
          "description": "...",
          "depends": ["other-addon-id"]
        }
      ]
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wowusky.core.logging_setup import get as _get_logger
from wowusky.core.paths import MANIFEST_DIR, ensure_dirs

_log = _get_logger(__name__)

_BUNDLED_DIR = Path(__file__).parent / "manifests"


def _normalise_addon(raw: dict) -> dict:
    """Fill in defaults so the rest of the app can rely on the same shape."""
    out = dict(raw)
    out.setdefault("flavors", ["all"])
    out.setdefault("folders", [])
    out.setdefault("category", "Other")
    out.setdefault("author", "")
    out.setdefault("description", "")
    out.setdefault("depends", [])
    out.setdefault("tags", [])
    out.setdefault("conflicts", [])
    if "provider" not in out and "source" in out:
        out["provider"] = out["source"]
    return out


def _load_manifest(path: Path) -> list[dict]:
    """Read one manifest file, returning the (normalised) addon list."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        _log.warning("skipping malformed manifest %s: %s", path, e)
        return []
    addons = data.get("addons") or []
    return [_normalise_addon(a) for a in addons
            if isinstance(a, dict) and a.get("id")]


def manifest_files() -> list[Path]:
    """Return all manifest paths in load order (builtin first, user last)."""
    ensure_dirs()
    paths: list[Path] = []
    builtin = _BUNDLED_DIR / "builtin.json"
    if builtin.exists():
        paths.append(builtin)
    if _BUNDLED_DIR.is_dir():
        for p in sorted(_BUNDLED_DIR.glob("*.json")):
            if p.name != "builtin.json":
                paths.append(p)
    if MANIFEST_DIR.is_dir():
        for p in sorted(MANIFEST_DIR.glob("*.json")):
            paths.append(p)
    return paths


def load_catalog() -> list[dict]:
    """Build the merged catalog. Later sources overwrite earlier ones by id."""
    by_id: dict[str, dict] = {}
    for path in manifest_files():
        for addon in _load_manifest(path):
            by_id[addon["id"]] = addon
    return list(by_id.values())


def find_addon(addon_id: str, catalog: list[dict] | None = None) -> dict | None:
    """Look up an addon by id (loads the catalog if you don't pass one)."""
    cat = catalog if catalog is not None else load_catalog()
    return next((a for a in cat if a["id"] == addon_id), None)


def categories(catalog: list[dict] | None = None) -> list[str]:
    """Return all category names present in the catalog, sorted."""
    cat = catalog if catalog is not None else load_catalog()
    return sorted({a.get("category", "Other") for a in cat})


def write_example_user_manifest() -> Path:
    """Drop a documented example manifest in the user manifest dir."""
    ensure_dirs()
    path = MANIFEST_DIR / "example.json"
    if path.exists():
        return path
    example: dict[str, Any] = {
        "name":        "example",
        "version":     "0.1",
        "description": "Example user manifest. Copy this file and edit it.",
        "addons": [
            {
                "id":          "example-addon",
                "name":        "Example Addon",
                "provider":    "github",
                "repo":        "owner/repo",
                "category":    "Interface",
                "flavors":     ["retail", "mainline"],
                "folders":     ["ExampleAddon"],
                "description": "Short description shown in Browse.",
            }
        ],
    }
    path.write_text(json.dumps(example, indent=2), encoding="utf-8")
    return path
