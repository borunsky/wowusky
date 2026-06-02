"""Tests for wowusky.core.state — the manager-state persistence layer.

Each test isolates the on-disk state into a tmp directory by patching the
module-level path constants.
"""

from __future__ import annotations

import os

import pytest

import wowusky.core.state as state


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    data = tmp_path / "wowusky"
    inst = data / "installed"
    monkeypatch.setattr(state, "CONFIG_DIR", str(data))
    monkeypatch.setattr(state, "CONFIG_FILE", str(data / "config.json"))
    monkeypatch.setattr(state, "PROFILES_FILE", str(data / "profiles.json"))
    monkeypatch.setattr(state, "WAGO_FILE", str(data / "wago.json"))
    monkeypatch.setattr(state, "INSTALLED_DIR", str(inst))
    monkeypatch.setattr(state, "INSTALLED_FILE", str(data / "installed.json"))
    monkeypatch.setattr(state, "BACKUP_DIR", str(data / "backups"))
    monkeypatch.setattr(state, "LOG_DIR", str(data / "logs"))
    monkeypatch.setattr(state, "MANIFEST_DIR", str(data / "manifests"))
    return data


# ── config ──────────────────────────────────────────────────────────

def test_config_roundtrip():
    state.save_config({"theme": "dark"})
    assert state.load_config() == {"theme": "dark"}


def test_load_config_missing_returns_empty():
    assert state.load_config() == {}


def test_dry_run_toggle():
    assert state.is_dry_run() is False
    state.set_dry_run(True)
    assert state.is_dry_run() is True


def test_cf_api_key_env_fallback(monkeypatch):
    monkeypatch.setenv("CURSEFORGE_API_KEY", "from-env")
    assert state.get_curseforge_api_key() == "from-env"


def test_cf_api_key_config_wins_over_env(monkeypatch):
    monkeypatch.setenv("CURSEFORGE_API_KEY", "from-env")
    state.set_curseforge_api_key("from-config")
    assert state.get_curseforge_api_key() == "from-config"


def test_cf_api_key_empty_pops_key():
    state.set_curseforge_api_key("abc")
    state.set_curseforge_api_key("")
    assert "curseforge_api_key" not in state.load_config()


# ── profiles ────────────────────────────────────────────────────────

def test_unconfigured_is_empty():
    assert state.load_profiles() == {"active": None, "profiles": {}}
    assert state.get_addons_path() is None


def test_add_and_get_active_profile():
    path = "/games/wow/_retail_/Interface/AddOns"
    pid = state.add_or_update_profile("Main", path)
    prof = state.get_active_profile()
    assert prof["name"] == "Main"
    assert prof["addons_path"] == path
    assert state.get_active_profile_id() == pid
    assert state.get_addons_path() == path


def test_set_addons_path_creates_profile_when_none():
    path = "/games/wow/_classic_era_/Interface/AddOns"
    state.set_addons_path(path)
    assert state.get_addons_path() == path
    assert state.get_active_profile().get("flavor") == "vanilla"


def test_legacy_config_migrates_to_profile():
    state.save_config({"addons_path": "/legacy/wow/_retail_/Interface/AddOns"})
    data = state.load_profiles()
    assert data["profiles"], "legacy single-profile config should migrate"
    assert state.get_addons_path() == "/legacy/wow/_retail_/Interface/AddOns"


def test_set_active_profile_only_if_exists():
    state.add_or_update_profile("A", "/wow/_retail_/Interface/AddOns")
    state.set_active_profile("does-not-exist")
    # Active unchanged — still the real profile.
    assert state.get_active_profile().get("name") == "A"


# ── installed DB ────────────────────────────────────────────────────

def test_installed_roundtrip_per_profile():
    state.add_or_update_profile("Main", "/wow/_retail_/Interface/AddOns")
    state.save_installed({"elvui": {"version": "13.5"}})
    assert state.load_installed() == {"elvui": {"version": "13.5"}}


def test_installed_file_path_uses_profile_id():
    p = state.installed_file_for_profile("retail")
    assert p.endswith(os.path.join("installed", "retail.json"))


# ── normalisation ───────────────────────────────────────────────────

def test_normalize_installations_dedups_by_realpath():
    items = [
        {"addons_path": "/wow/_retail_/Interface/AddOns"},
        {"addons_path": "/wow/_retail_/Interface/AddOns"},
        {"addons_path": "/wow/_classic_/Interface/AddOns"},
    ]
    out = state.normalize_installations(items)
    assert len(out) == 2


def test_infer_profile_from_path_detects_flavor():
    prof = state.infer_profile_from_path("/wow/_retail_/Interface/AddOns")
    assert prof["flavor"] == "retail"
    assert prof["addons_path"] == "/wow/_retail_/Interface/AddOns"


def test_slugify_profile_name():
    assert state.slugify_profile_name("My Cool Profile!") == "my_cool_profile"
    assert state.slugify_profile_name("") == "profile"
