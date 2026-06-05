"""Tests for v0.16.0 features (#59/#60/#61):
- installation health (missing / duplicates / orphans)
- orphan adopt / remove
- update diff + config flag
"""

from __future__ import annotations

import os

import pytest

import wowusky.bridge.server as server
import wowusky.core.config as config
import wowusky.core.installed as installed
import wowusky.core.state as state


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    from wowusky.core import paths as _paths

    data = tmp_path / "wowusky"
    data.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(_paths, "DATA_DIR", data)
    monkeypatch.setattr(_paths, "CONFIG_FILE", data / "config.json")
    monkeypatch.setattr(_paths, "PROFILES_FILE", data / "profiles.json")
    monkeypatch.setattr(_paths, "INSTALLED_DIR", data / "installed")
    monkeypatch.setattr(_paths, "BACKUP_DIR", data / "backups")
    monkeypatch.setattr(_paths, "MANIFEST_DIR", data / "manifests")
    monkeypatch.setattr(_paths, "LOG_DIR", data / "logs")
    monkeypatch.setattr(_paths, "CONFIG_DIR", data)
    monkeypatch.setattr(config, "CONFIG_FILE", data / "config.json")
    monkeypatch.setattr(state, "CONFIG_FILE", str(data / "config.json"))
    monkeypatch.setattr(state, "PROFILES_FILE", str(data / "profiles.json"))
    monkeypatch.setattr(state, "INSTALLED_DIR", str(data / "installed"))
    monkeypatch.setattr(state, "CONFIG_DIR", str(data))
    # backup.py keeps its own BACKUP_DIR copy.
    import wowusky.core.backup as backup
    monkeypatch.setattr(backup, "BACKUP_DIR", str(data / "backups"))

    addons = tmp_path / "AddOns"
    addons.mkdir()
    state.add_or_update_profile("Test", str(addons))
    return tmp_path


def _call(method: str, params: dict | None = None):
    return server._METHODS[method](params or {})


def _make_addon_folder(tmp_path, name: str, version: str = "1.0"):
    d = tmp_path / "AddOns" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.toc").write_text(
        f"## Title: {name}\n## Version: {version}\n## Interface: 110000\n",
        encoding="utf-8",
    )
    return d


# ── #59 installation health ──────────────────────────────────────────

def test_health_missing_folder(tmp_path):
    profile = state.get_active_profile_id()
    installed.save(profile, {"gone": {"name": "Gone", "version": "1", "folders": ["Gone"]}})
    out = _call("health.installed")
    assert [m["id"] for m in out["missing"]] == ["gone"]
    assert out["problem_count"] >= 1


def test_health_duplicate_claims(tmp_path):
    profile = state.get_active_profile_id()
    _make_addon_folder(tmp_path, "Shared")
    installed.save(profile, {
        "a": {"name": "A", "version": "1", "folders": ["Shared"]},
        "b": {"name": "B", "version": "1", "folders": ["Shared"]},
    })
    out = _call("health.installed")
    dups = {d["folder"] for d in out["duplicates"]}
    assert "Shared" in dups


def test_health_orphans_detected(tmp_path):
    _make_addon_folder(tmp_path, "Untracked")
    out = _call("health.installed")
    assert "Untracked" in {o["folder"] for o in out["orphans"]}


def test_health_remove_entry(tmp_path):
    profile = state.get_active_profile_id()
    installed.save(profile, {"gone": {"name": "Gone", "version": "1", "folders": ["Gone"]}})
    out = _call("health.removeEntry", {"id": "gone"})
    assert out["ok"] is True
    assert installed.load(profile) == {}


# ── #60 orphan management ────────────────────────────────────────────

def test_orphans_list(tmp_path):
    _make_addon_folder(tmp_path, "Loose")
    out = _call("orphans.list")
    assert "Loose" in {o["folder"] for o in out["orphans"]}


def test_orphans_adopt_external(tmp_path):
    _make_addon_folder(tmp_path, "Loose", version="2.3")
    out = _call("orphans.adopt", {"folder": "Loose"})
    assert out["ok"] is True
    db = installed.load(state.get_active_profile_id())
    assert out["adopted_id"] in db
    assert db[out["adopted_id"]]["version"] == "2.3"
    # No longer an orphan.
    assert "Loose" not in {o["folder"] for o in _call("orphans.list")["orphans"]}


def test_orphans_remove_deletes_folder(tmp_path):
    _make_addon_folder(tmp_path, "Trash")
    out = _call("orphans.remove", {"folder": "Trash"})
    assert out["ok"] is True
    assert not os.path.isdir(tmp_path / "AddOns" / "Trash")


def test_orphans_adopt_requires_folder():
    with pytest.raises(ValueError):
        _call("orphans.adopt", {})


# ── #61 update diff + config ─────────────────────────────────────────

def test_update_diff_folders(monkeypatch, tmp_path):
    profile = state.get_active_profile_id()
    installed.save(profile, {"x": {"name": "X", "version": "1.0", "folders": ["X", "X_Old"]}})
    from wowusky import orchestrator as _orch
    monkeypatch.setattr(_orch, "find_addon_by_id",
                        lambda aid: {"id": "x", "name": "X", "folders": ["X", "X_New"]})
    monkeypatch.setattr(_orch, "get_latest_version", lambda a: "2.0")
    out = _call("addon.updateDiff", {"id": "x"})
    assert out["from_version"] == "1.0"
    assert out["to_version"] == "2.0"
    assert out["added"] == ["X_New"]
    assert out["removed"] == ["X_Old"]
    assert out["same"] == ["X"]


def test_update_diff_requires_id():
    with pytest.raises(ValueError):
        _call("addon.updateDiff", {})


def test_update_diff_config_roundtrip():
    assert config.get_update_diff_before_install() is False
    out = _call("settings.update", {"update_diff_before_install": True})
    assert out["update_diff_before_install"] is True
    assert config.get_update_diff_before_install() is True
