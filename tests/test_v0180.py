"""Tests for v0.18.0 features (#65/#66/#67):
- full profile bundle export/import (#65)
- git-based sync (#66)
- change history / audit log (#67)
"""

from __future__ import annotations

import json
import os
import subprocess

import pytest

import wowusky.bridge.server as server
import wowusky.core.config as config
import wowusky.core.history as history
import wowusky.core.installed as installed
import wowusky.core.state as state
import wowusky.core.sync as sync


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    from wowusky.core import paths as _paths

    data = tmp_path / "wowusky"
    data.mkdir(parents=True, exist_ok=True)
    for name, val in {
        "DATA_DIR": data,
        "CONFIG_FILE": data / "config.json",
        "PROFILES_FILE": data / "profiles.json",
        "WAGO_FILE": data / "wago.json",
        "INSTALLED_DIR": data / "installed",
        "CONFIG_DIR": data,
    }.items():
        monkeypatch.setattr(_paths, name, val)
    monkeypatch.setattr(config, "CONFIG_FILE", data / "config.json")
    monkeypatch.setattr(state, "CONFIG_FILE", str(data / "config.json"))
    monkeypatch.setattr(state, "PROFILES_FILE", str(data / "profiles.json"))
    monkeypatch.setattr(state, "WAGO_FILE", str(data / "wago.json"))
    monkeypatch.setattr(state, "INSTALLED_DIR", str(data / "installed"))
    monkeypatch.setattr(state, "CONFIG_DIR", str(data))
    addons = tmp_path / "AddOns"
    addons.mkdir()
    state.add_or_update_profile("Test", str(addons))
    return tmp_path


def _call(method: str, params: dict | None = None):
    return server._METHODS[method](params or {})


# ── #65 full profile bundle ──────────────────────────────────────────

def _seed_profile():
    pid = state.get_active_profile_id()
    installed.save(pid, {"details": {"name": "Details!", "version": "1.0", "source": "github", "folders": ["Details"]}})
    state.save_wago({"auras": {"abc": {"slug": "abc", "name": "Cooldowns", "version": 2}}})
    config.set_desktop_notifications(False)
    return pid


def test_export_bundle_contains_everything():
    _seed_profile()
    out = _call("profile.exportBundle")
    b = out["bundle"]
    assert b["wowusky_profile_bundle"] == "1"
    assert [a["id"] for a in b["addons"]] == ["details"]
    assert "abc" in b["auras"]
    assert b["settings"]["desktop_notifications"] is False
    # API key must never be exported.
    assert "curseforge_api_key" not in b["settings"]


def test_import_bundle_apply_merges(monkeypatch):
    _seed_profile()
    bundle = _call("profile.exportBundle")["bundle"]
    # Wipe local state, then re-apply the bundle.
    pid = state.get_active_profile_id()
    installed.save(pid, {})
    state.save_wago({"auras": {}})
    out = _call("profile.importBundleApply", {"bundle": bundle})
    assert out["ok"] is True
    assert out["imported"] == 1
    assert out["auras_added"] == 1
    assert "details" in installed.load(pid)
    assert "abc" in state.load_wago()["auras"]


def test_import_bundle_preview_counts():
    _seed_profile()
    bundle = _call("profile.exportBundle")["bundle"]
    out = _call("profile.importBundlePreview", {"bundle": bundle})
    assert out["ok"] is True
    # Same versions already installed → all "same".
    assert out["addons_same"] == 1
    assert out["auras_new"] == 0


def test_import_bundle_rejects_garbage():
    out = _call("profile.importBundlePreview", {"bundle": {"nope": 1}})
    assert out["ok"] is False


# ── #66 git-based sync ───────────────────────────────────────────────

def _git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True,
                   capture_output=True, text=True)


@pytest.mark.skipif(not sync._git_available(), reason="git not installed")
def test_sync_push_and_pull_roundtrip(tmp_path):
    _seed_profile()
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
    repo = tmp_path / "syncrepo"
    subprocess.run(["git", "clone", str(bare), str(repo)], check=True, capture_output=True)
    _git(str(repo), "config", "user.email", "t@e.st")
    _git(str(repo), "config", "user.name", "Tester")
    # Establish an initial commit + upstream so `git push` has a target.
    (repo / "README").write_text("seed\n")
    _git(str(repo), "add", "README")
    _git(str(repo), "commit", "-m", "seed")
    _git(str(repo), "push", "-u", "origin", "HEAD")
    sync.set_repo_path(str(repo))

    res = _call("sync.push")
    assert res["ok"] is True
    assert os.path.isfile(repo / sync.BUNDLE_FILENAME)

    # Wipe and pull back.
    pid = state.get_active_profile_id()
    installed.save(pid, {})
    pulled = _call("sync.pull")
    assert pulled["ok"] is True
    assert pulled["bundle"]["addons"][0]["id"] == "details"


def test_sync_status_unconfigured():
    out = _call("sync.status")
    # No repo configured yet (fresh data dir).
    assert out["configured"] is False


def test_sync_push_no_repo():
    out = _call("sync.push")
    assert out["ok"] is False


# ── #67 change history ───────────────────────────────────────────────

def test_history_record_and_list():
    pid = state.get_active_profile_id()
    history.record(pid, "install", "details", name="Details!", to_version="1.0")
    history.record(pid, "update", "details", name="Details!", from_version="1.0", to_version="2.0")
    items = history.list_history(pid)
    # Newest first.
    assert items[0]["action"] == "update"
    assert items[0]["to"] == "2.0"
    assert len(items) == 2


def test_history_filter_by_addon():
    pid = state.get_active_profile_id()
    history.record(pid, "install", "a", name="A")
    history.record(pid, "install", "b", name="B")
    items = history.list_history(pid, addon="b")
    assert len(items) == 1
    assert items[0]["id"] == "b"


def test_history_bridge_list():
    pid = state.get_active_profile_id()
    history.record(pid, "remove", "x", name="X")
    out = _call("history.list")
    assert out["items"][0]["id"] == "x"


def test_history_recorded_on_install(monkeypatch):
    """An addon.install records an install entry in history."""
    pid = state.get_active_profile_id()
    from wowusky import orchestrator as _orch

    monkeypatch.setattr(_orch, "find_addon_by_id", lambda aid: {"id": aid, "name": "X"})

    def _fake_install(entry, addons_path, log=print, progress=None):
        db = installed.load(pid)
        db[entry["id"]] = {"name": "X", "version": "3.0", "folders": ["X"]}
        installed.save(pid, db)

    monkeypatch.setattr(_orch, "install_addon", _fake_install)
    _call("addon.install", {"id": "x"})
    items = history.list_history(pid)
    assert items[0]["action"] == "install"
    assert items[0]["to"] == "3.0"
