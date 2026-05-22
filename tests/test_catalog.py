"""Tests for the manifest-based catalog loader.

We isolate the user-manifest directory via ``XDG_DATA_HOME`` so that
the built-in manifests (shipped with the package) are still loaded but
user overrides come from a controlled location.
"""

import importlib
import json
import sys
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    for name in ("wowusky.core.paths", "wowusky.catalog"):
        if name in sys.modules:
            importlib.reload(sys.modules[name])
    yield


def test_builtin_catalog_loads_more_than_one_addon():
    from wowusky.catalog import load_catalog
    catalog = load_catalog()
    assert len(catalog) > 10, f"expected substantial builtin catalog, got {len(catalog)}"


def test_every_catalog_entry_has_required_fields():
    from wowusky.catalog import load_catalog
    for addon in load_catalog():
        for key in ("id", "name", "provider", "flavors", "folders"):
            assert key in addon, f"{addon.get('id')} missing key '{key}'"


def test_user_manifest_overrides_builtin(tmp_path):
    """A user manifest entry with the same id as a builtin should win."""
    from wowusky.core.paths import MANIFEST_DIR, ensure_dirs
    ensure_dirs()
    user_file = MANIFEST_DIR / "override.json"
    user_file.write_text(json.dumps({
        "name": "user-override",
        "addons": [
            {
                "id":          "elvui",            # same id as builtin
                "name":        "ElvUI (custom)",
                "provider":    "github",
                "repo":        "tukui-org/ElvUI",
                "folders":     ["ElvUI"],
                "description": "user override",
            }
        ]
    }))
    from wowusky.catalog import find_addon, load_catalog
    cat = load_catalog()
    entry = find_addon("elvui", cat)
    assert entry is not None
    assert entry["name"] == "ElvUI (custom)"
    assert entry["provider"] == "github"


def test_user_manifest_can_add_new_addons():
    from wowusky.core.paths import MANIFEST_DIR, ensure_dirs
    ensure_dirs()
    (MANIFEST_DIR / "extra.json").write_text(json.dumps({
        "addons": [{
            "id":       "totally-new-thing",
            "name":     "Totally New",
            "provider": "github",
            "repo":     "x/y",
            "folders":  ["TotallyNew"],
        }]
    }))
    from wowusky.catalog import find_addon, load_catalog
    assert find_addon("totally-new-thing", load_catalog()) is not None


def test_malformed_manifest_is_skipped_not_fatal():
    from wowusky.core.paths import MANIFEST_DIR, ensure_dirs
    ensure_dirs()
    (MANIFEST_DIR / "broken.json").write_text("{not valid json")
    # Must not raise — broken file logged, others still load
    from wowusky.catalog import load_catalog
    catalog = load_catalog()
    assert len(catalog) > 0


def test_categories_are_sorted_and_unique():
    from wowusky.catalog import categories, load_catalog
    cat = load_catalog()
    cats = categories(cat)
    assert cats == sorted(cats)
    assert len(cats) == len(set(cats))


def test_normalisation_fills_defaults():
    from wowusky.core.paths import MANIFEST_DIR, ensure_dirs
    ensure_dirs()
    (MANIFEST_DIR / "minimal.json").write_text(json.dumps({
        "addons": [{"id": "min", "name": "Min", "provider": "github", "repo": "a/b"}]
    }))
    from wowusky.catalog import find_addon, load_catalog
    entry = find_addon("min", load_catalog())
    assert entry["flavors"] == ["all"]
    assert entry["folders"] == []
    assert entry["category"] == "Other"
