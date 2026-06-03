"""Tests for wowusky.core.scan — install discovery + DB reconciliation."""

from __future__ import annotations

import os

import pytest

import wowusky.core.scan as scan
import wowusky.core.state as state


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    data = tmp_path / "wowusky"
    monkeypatch.setattr(state, "CONFIG_DIR", str(data))
    monkeypatch.setattr(state, "CONFIG_FILE", str(data / "config.json"))
    monkeypatch.setattr(state, "PROFILES_FILE", str(data / "profiles.json"))
    monkeypatch.setattr(state, "WAGO_FILE", str(data / "wago.json"))
    monkeypatch.setattr(state, "INSTALLED_DIR", str(data / "installed"))
    monkeypatch.setattr(state, "INSTALLED_FILE", str(data / "installed.json"))
    monkeypatch.setattr(state, "BACKUP_DIR", str(data / "backups"))
    monkeypatch.setattr(state, "LOG_DIR", str(data / "logs"))
    monkeypatch.setattr(state, "MANIFEST_DIR", str(data / "manifests"))
    # An active profile so installed DB has a deterministic file.
    state.add_or_update_profile("Test", "/wow/_retail_/Interface/AddOns")
    return data


def _make_addon_folder(addons_path, folder, *, title="X", version="1.0",
                       interface="110000"):
    d = os.path.join(addons_path, folder)
    os.makedirs(d, exist_ok=True)
    toc = (f"## Title: {title}\n## Version: {version}\n"
           f"## Interface: {interface}\n")
    with open(os.path.join(d, f"{folder}.toc"), "w") as f:
        f.write(toc)


# ── scan_wow_installations ──────────────────────────────────────────

def test_scan_empty(monkeypatch):
    monkeypatch.setattr(scan, "WOW_SEARCH_PATHS", [])
    assert scan.scan_wow_installations() == []


def test_scan_finds_flavor(monkeypatch, tmp_path):
    base = tmp_path / "WoW"
    retail = base / "_retail_" / "Interface" / "AddOns"
    retail.mkdir(parents=True)
    monkeypatch.setattr(scan, "WOW_SEARCH_PATHS", [str(base)])
    out = scan.scan_wow_installations()
    assert len(out) == 1
    assert out[0]["flavor"] == "_retail_"
    assert out[0]["addons_path"] == str(retail)


# ── sync_filesystem_with_db ─────────────────────────────────────────

def test_sync_noop_on_missing_path():
    # Should not raise.
    scan.sync_filesystem_with_db("/does/not/exist", [])


def test_sync_drops_stale_entries(tmp_path):
    addons = tmp_path / "AddOns"
    addons.mkdir()
    state.save_installed({"gone": {"name": "Gone", "version": "1",
                                   "folders": ["Gone"], "source": "external"}})
    scan.sync_filesystem_with_db(str(addons), [])
    assert "gone" not in state.load_installed()


def test_sync_adopts_external_folder(tmp_path):
    addons = tmp_path / "AddOns"
    addons.mkdir()
    _make_addon_folder(str(addons), "CoolAddon", title="Cool Addon",
                       version="2.3")
    scan.sync_filesystem_with_db(str(addons), [])
    installed = state.load_installed()
    assert "fs_cooladdon" in installed
    assert installed["fs_cooladdon"]["name"] == "Cool Addon"
    assert installed["fs_cooladdon"]["version"] == "2.3"
    assert installed["fs_cooladdon"]["source"] == "external"


def test_sync_matches_catalog(tmp_path):
    addons = tmp_path / "AddOns"
    addons.mkdir()
    _make_addon_folder(str(addons), "ElvUI", version="13.5")
    catalog = [{"id": "elvui", "name": "ElvUI", "source": "tukui",
                "folders": ["ElvUI"]}]
    scan.sync_filesystem_with_db(str(addons), catalog)
    installed = state.load_installed()
    assert "elvui" in installed
    assert installed["elvui"]["source"] == "tukui"
    assert installed["elvui"]["version"] == "13.5"
    assert "fs_elvui" not in installed


def test_sync_matches_catalog_with_provider_field(tmp_path):
    # The real bundled catalog uses ``provider`` (not ``source``); a discovered
    # folder matching such an entry must not raise KeyError. Regression test.
    addons = tmp_path / "AddOns"
    addons.mkdir()
    _make_addon_folder(str(addons), "Details", version="11.1")
    catalog = [{"id": "details", "name": "Details!", "provider": "curseforge_web",
                "folders": ["Details"]}]
    scan.sync_filesystem_with_db(str(addons), catalog)
    installed = state.load_installed()
    assert installed["details"]["source"] == "curseforge_web"
    assert "fs_details" not in installed
