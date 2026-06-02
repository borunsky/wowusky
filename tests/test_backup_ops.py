"""Tests for the profile-aware backup helpers in wowusky.core.backup."""

from __future__ import annotations

import os
import zipfile

import pytest

import wowusky.core.backup as backup
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
    monkeypatch.setattr(backup, "BACKUP_DIR", str(data / "backups"))
    monkeypatch.setattr(state, "LOG_DIR", str(data / "logs"))
    monkeypatch.setattr(state, "MANIFEST_DIR", str(data / "manifests"))
    state.add_or_update_profile("Test", "/wow/_retail_/Interface/AddOns")
    return data


def _make_addon_dir(addons_path, folder_name, *, files=("readme.txt",)):
    d = os.path.join(str(addons_path), folder_name)
    os.makedirs(d, exist_ok=True)
    for fname in files:
        with open(os.path.join(d, fname), "w") as f:
            f.write("data")
    return d


# ── backup_addon_folders ────────────────────────────────────────────

def test_backup_addon_folders_creates_zip(tmp_path):
    addons = tmp_path / "AddOns"
    addons.mkdir()
    _make_addon_dir(addons, "ElvUI", files=("ElvUI.lua",))
    entry = {"folders": ["ElvUI"], "version": "13.5", "source": "tukui"}
    zip_path = backup.backup_addon_folders("elvui", entry, str(addons))
    assert zip_path and os.path.isfile(zip_path)


def test_backup_addon_folders_returns_none_when_folder_missing(tmp_path):
    addons = tmp_path / "AddOns"
    addons.mkdir()
    entry = {"folders": ["Ghost"], "version": "1.0", "source": "github"}
    result = backup.backup_addon_folders("ghost", entry, str(addons))
    assert result is None


def test_backup_addon_folders_dry_run_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "CONFIG_FILE", str(tmp_path / "wowusky" / "config.json"))
    state.set_dry_run(True)
    addons = tmp_path / "AddOns"
    addons.mkdir()
    _make_addon_dir(addons, "X")
    entry = {"folders": ["X"], "version": "1", "source": "github"}
    path = backup.backup_addon_folders("x_addon", entry, str(addons))
    assert path is not None
    assert not os.path.isfile(path)
    state.set_dry_run(False)


# ── list_addon_backups + latest_backup_for_addon ────────────────────

def test_list_addon_backups_empty_initially():
    assert backup.list_addon_backups("nonexistent") == []


def test_list_addon_backups_returns_created_backup(tmp_path):
    addons = tmp_path / "AddOns"
    addons.mkdir()
    _make_addon_dir(addons, "ElvUI")
    entry = {"folders": ["ElvUI"], "version": "13.5", "source": "tukui"}
    backup.backup_addon_folders("elvui", entry, str(addons))
    items = backup.list_addon_backups("elvui")
    assert len(items) == 1
    assert items[0]["version"] == "13.5"


def test_latest_backup_for_addon_returns_path(tmp_path):
    addons = tmp_path / "AddOns"
    addons.mkdir()
    _make_addon_dir(addons, "ElvUI")
    entry = {"folders": ["ElvUI"], "version": "13.5", "source": "tukui"}
    backup.backup_addon_folders("elvui", entry, str(addons))
    path = backup.latest_backup_for_addon("elvui")
    assert path and os.path.isfile(path)


def test_latest_backup_for_addon_none_when_empty():
    assert backup.latest_backup_for_addon("ghost") is None


# ── rollback_addon_to_backup ────────────────────────────────────────

def test_rollback_addon_to_backup_restores_files(tmp_path):
    addons = tmp_path / "AddOns"
    addons.mkdir()
    _make_addon_dir(addons, "ElvUI", files=("ElvUI.lua",))
    entry = {"folders": ["ElvUI"], "version": "13.5", "source": "tukui"}
    zip_path = backup.backup_addon_folders("elvui", entry, str(addons))
    # Remove the folder to simulate an update gone wrong
    import shutil
    shutil.rmtree(os.path.join(str(addons), "ElvUI"))
    assert not os.path.isdir(os.path.join(str(addons), "ElvUI"))

    state.save_installed({"elvui": entry})
    ok = backup.rollback_addon_to_backup("elvui", zip_path, str(addons))
    assert ok
    assert os.path.isfile(os.path.join(str(addons), "ElvUI", "ElvUI.lua"))


def test_rollback_addon_to_backup_missing_zip(tmp_path):
    logs = []
    ok = backup.rollback_addon_to_backup("elvui", "/nonexistent.zip", str(tmp_path), log=logs.append)
    assert not ok
    assert any("not found" in m for m in logs)


def test_rollback_addon_delegates_to_latest(tmp_path):
    addons = tmp_path / "AddOns"
    addons.mkdir()
    _make_addon_dir(addons, "ElvUI", files=("ElvUI.lua",))
    entry = {"folders": ["ElvUI"], "version": "13.5", "source": "tukui"}
    backup.backup_addon_folders("elvui", entry, str(addons))
    state.save_installed({"elvui": entry})
    import shutil
    shutil.rmtree(os.path.join(str(addons), "ElvUI"))
    ok = backup.rollback_addon("elvui", str(addons))
    assert ok


# ── full_backup_dir + list_full_backups ────────────────────────────

def test_full_backup_dir_creates_and_returns_path():
    d = backup.full_backup_dir()
    assert os.path.isdir(d)


def test_list_full_backups_empty_initially():
    assert backup.list_full_backups() == []


# ── create_full_backup + restore_full_backup ────────────────────────

def test_create_full_backup_creates_zip(tmp_path):
    addons = tmp_path / "AddOns"
    addons.mkdir()
    _make_addon_dir(addons, "ElvUI", files=("ElvUI.lua",))
    state.set_addons_path(str(addons))
    path = backup.create_full_backup()
    assert os.path.isfile(path)
    with zipfile.ZipFile(path, "r") as zf:
        names = zf.namelist()
    assert any("wowusky-backup.json" in n for n in names)


def test_create_full_backup_raises_when_no_addons_path():
    with pytest.raises(RuntimeError, match="AddOns path"):
        backup.create_full_backup()


def test_restore_full_backup_restores_addons(tmp_path):
    addons = tmp_path / "AddOns"
    addons.mkdir()
    _make_addon_dir(addons, "ElvUI", files=("ElvUI.lua",))
    state.set_addons_path(str(addons))
    zip_path = backup.create_full_backup()

    # Wipe the ElvUI folder
    import shutil
    shutil.rmtree(os.path.join(str(addons), "ElvUI"))

    ok = backup.restore_full_backup(zip_path)
    assert ok
    assert os.path.isfile(os.path.join(str(addons), "ElvUI", "ElvUI.lua"))


def test_restore_full_backup_raises_on_missing_zip():
    state.set_addons_path("/tmp")
    with pytest.raises(RuntimeError, match="not found"):
        backup.restore_full_backup("/no/such/file.zip")
