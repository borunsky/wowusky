"""Tests for v0.13.0 features (#51/#52/#53):
- backup retention + storage summary/cleanup
- scheduled-backup timer unit generation
- release-notes provider + orchestrator + bridge
"""

from __future__ import annotations

import os
import zipfile

import pytest

import wowusky.bridge.server as server
import wowusky.core.backup as backup
import wowusky.core.schedule as schedule
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
    addons = tmp_path / "AddOns"
    addons.mkdir()
    state.add_or_update_profile("Test", str(addons))
    return data


def _call(method: str, params: dict | None = None):
    return server._METHODS[method](params or {})


def _make_full_backup(name: str):
    d = backup.full_backup_dir()
    p = os.path.join(d, name)
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("AddOns/x.lua", b"data")
    return p


# ── #51 retention ────────────────────────────────────────────────────

def test_prune_full_backups_keeps_newest(monkeypatch):
    import time
    for i in range(5):
        p = _make_full_backup(f"wowusky-full-test-2026010{i}.zip")
        os.utime(p, (1000 + i, 1000 + i))
    removed = backup.prune_full_backups(keep=2)
    assert removed == 3
    assert len(backup.list_full_backups()) == 2


def test_prune_full_backups_keep_at_least_one():
    _make_full_backup("wowusky-full-test-20260101.zip")
    removed = backup.prune_full_backups(keep=0)
    # keep<=0 is clamped to 1, so a single backup survives.
    assert removed == 0
    assert len(backup.list_full_backups()) == 1


# ── #51 scheduled-backup units ───────────────────────────────────────

def test_write_backup_units_encodes_keep(monkeypatch, tmp_path):
    monkeypatch.setattr(schedule, "_unit_dir", lambda: str(tmp_path / "units"))
    schedule._write_backup_units("weekly", keep=7)
    with open(schedule.backup_service_path()) as fh:
        svc = fh.read()
    assert "backup auto --keep 7" in svc
    with open(schedule.backup_timer_path()) as fh:
        tmr = fh.read()
    assert "OnCalendar=weekly" in tmr
    assert schedule._read_backup_keep() == 7


# ── #52 storage summary + cleanup ────────────────────────────────────

def test_storage_summary_counts_backups():
    _make_full_backup("wowusky-full-test-20260101.zip")
    _make_full_backup("wowusky-full-test-20260102.zip")
    out = _call("storage.summary")
    assert out["backups_count"] == 2
    assert out["backups_bytes"] > 0
    assert isinstance(out["by_addon"], list)


def test_storage_cleanup_prunes_full(monkeypatch):
    for i in range(4):
        p = _make_full_backup(f"wowusky-full-test-2026010{i}.zip")
        os.utime(p, (2000 + i, 2000 + i))
    out = _call("storage.cleanup", {"keep": 1})
    assert out["ok"] is True
    assert out["removed"] == 3
    assert out["freed_bytes"] > 0
    assert len(backup.list_full_backups()) == 1


# ── #53 release notes ────────────────────────────────────────────────

def test_release_notes_github(monkeypatch):
    from wowusky.providers import github_fns
    monkeypatch.setattr(github_fns, "github_repo_for_addon", lambda a: "owner/repo")
    monkeypatch.setattr(github_fns, "github_releases",
                        lambda repo: [{"tag_name": "v2.1", "body": "## Fixed\n- bug"}])
    out = github_fns.github_release_notes({"source": "github", "repo": "owner/repo"})
    assert out == {"version": "2.1", "notes": "## Fixed\n- bug"}


def test_release_notes_non_github_returns_none():
    from wowusky import orchestrator as orch
    assert orch.update_notes({"source": "tukui"}) is None


def test_release_notes_bridge_unknown_addon():
    out = _call("addon.releaseNotes", {"id": "__nope__"})
    assert out == {"version": "", "notes": ""}


def test_release_notes_bridge_requires_id():
    with pytest.raises(ValueError):
        _call("addon.releaseNotes", {})
