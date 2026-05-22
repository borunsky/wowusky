"""Tests for the multi-profile management system.

Each test runs in its own temporary ``XDG_DATA_HOME`` so we never touch
the user's real profiles. We force-reimport the modules that cache
paths after switching the env var.
"""

import importlib
import os
import sys

import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Point XDG_DATA_HOME at a fresh tmp dir for every test."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    # Reload the modules whose constants captured the old path
    for name in ("wowusky.core.paths",
                 "wowusky.core.config",
                 "wowusky.core.profiles",
                 "wowusky.core.installed",
                 "wowusky.core.backup"):
        if name in sys.modules:
            importlib.reload(sys.modules[name])
    yield


def test_first_profile_becomes_active():
    from wowusky.core import profiles
    p = profiles.create_from_path("TBC", "/games/wow/_anniversary_/Interface/AddOns")
    assert profiles.get_active().id == p.id


def test_profile_id_is_unique_when_names_collide():
    from wowusky.core import profiles
    a = profiles.create_from_path("TBC", "/games/A/_anniversary_/Interface/AddOns")
    b = profiles.create_from_path("TBC", "/games/B/_anniversary_/Interface/AddOns")
    assert a.id != b.id


def test_flavor_inferred_from_path():
    from wowusky.core import profiles
    p = profiles.create_from_path("Classic", "/games/wow/_classic_era_/Interface/AddOns")
    assert p.flavor == "vanilla"
    assert p.interface == 11508


def test_remove_active_profile_switches_active_to_remaining():
    from wowusky.core import profiles
    a = profiles.create_from_path("TBC",     "/g/wow/_anniversary_/Interface/AddOns")
    b = profiles.create_from_path("Classic", "/g/wow/_classic_era_/Interface/AddOns")
    assert profiles.get_active().id == a.id
    profiles.set_active(b.id)
    assert profiles.get_active().id == b.id
    profiles.remove(b.id)
    # Active must fall back to the remaining profile
    assert profiles.get_active().id == a.id


def test_remove_last_profile_clears_active():
    from wowusky.core import profiles
    a = profiles.create_from_path("Only", "/g/_retail_/Interface/AddOns")
    profiles.remove(a.id)
    assert profiles.get_active() is None


def test_per_profile_installed_database_is_isolated():
    from wowusky.core import installed, profiles
    a = profiles.create_from_path("A", "/g/A/_retail_/Interface/AddOns")
    b = profiles.create_from_path("B", "/g/B/_classic_era_/Interface/AddOns")
    installed.upsert(a.id, "weakauras",
                     {"name": "WeakAuras", "version": "5.18", "folders": ["WeakAuras"]})
    installed.upsert(b.id, "questie",
                     {"name": "Questie", "version": "10.0", "folders": ["Questie"]})
    assert installed.count(a.id) == 1
    assert installed.count(b.id) == 1
    assert installed.get_entry(a.id, "weakauras")["version"] == "5.18"
    assert installed.get_entry(b.id, "weakauras") is None


def test_slugify_handles_unusual_names():
    from wowusky.core.profiles import slugify
    assert slugify("TBC Anniversary") == "tbc_anniversary"
    assert slugify("My WoW! 2024")    == "my_wow_2024"
    assert slugify("___")             == "profile"
    assert slugify("")                == "profile"


def test_legacy_installed_json_is_migrated():
    """A pre-0.4 installed.json at the data root should be moved into
    the per-profile location and the old file renamed."""
    from wowusky.core import config, paths
    paths.ensure_dirs()
    paths.LEGACY_INSTALLED_FILE.write_text('{"elvui":{"name":"ElvUI","version":"15.13","folders":["ElvUI"]}}')
    assert config.migrate_legacy_installed("tbc_anniversary") is True
    migrated = paths.installed_file_for("tbc_anniversary")
    assert migrated.exists()
    # Old file should now be renamed
    assert paths.LEGACY_INSTALLED_FILE.with_suffix(".json.migrated").exists()
    assert not paths.LEGACY_INSTALLED_FILE.exists()


def test_migrate_is_idempotent():
    """Calling migrate twice must not overwrite existing data."""
    from wowusky.core import config, installed, paths
    paths.ensure_dirs()
    installed.upsert("retail", "tukui",
                     {"name": "Tukui", "version": "1.0", "folders": ["Tukui"]})
    paths.LEGACY_INSTALLED_FILE.write_text('{"elvui":{"name":"ElvUI","version":"x","folders":["ElvUI"]}}')
    # target already exists → no migration
    assert config.migrate_legacy_installed("retail") is False
    # tukui entry intact
    assert installed.get_entry("retail", "tukui") is not None
