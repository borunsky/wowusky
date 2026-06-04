"""Tests for v0.14.0 features (#54/#55):
- desktop_notifications config + settings bridge
- cross-profile sync preview + apply
"""

from __future__ import annotations

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
    # paths.* drives installed_file_for / ensure_dirs.
    monkeypatch.setattr(_paths, "DATA_DIR", data)
    monkeypatch.setattr(_paths, "CONFIG_FILE", data / "config.json")
    monkeypatch.setattr(_paths, "PROFILES_FILE", data / "profiles.json")
    monkeypatch.setattr(_paths, "INSTALLED_DIR", data / "installed")
    monkeypatch.setattr(_paths, "BACKUP_DIR", data / "backups")
    monkeypatch.setattr(_paths, "MANIFEST_DIR", data / "manifests")
    monkeypatch.setattr(_paths, "LOG_DIR", data / "logs")
    monkeypatch.setattr(_paths, "CONFIG_DIR", data)
    # config.py imported CONFIG_FILE into its own namespace.
    monkeypatch.setattr(config, "CONFIG_FILE", data / "config.json")
    # state.py keeps its own string copies.
    monkeypatch.setattr(state, "CONFIG_FILE", str(data / "config.json"))
    monkeypatch.setattr(state, "PROFILES_FILE", str(data / "profiles.json"))
    monkeypatch.setattr(state, "INSTALLED_DIR", str(data / "installed"))
    monkeypatch.setattr(state, "CONFIG_DIR", str(data))
    return data


def _call(method: str, params: dict | None = None):
    return server._METHODS[method](params or {})


# ── #54 desktop notifications config ─────────────────────────────────

def test_desktop_notifications_default_true():
    assert config.get_desktop_notifications() is True


def test_desktop_notifications_roundtrip():
    config.set_desktop_notifications(False)
    assert config.get_desktop_notifications() is False
    config.set_desktop_notifications(True)
    assert config.get_desktop_notifications() is True


def test_settings_get_exposes_desktop_notifications():
    out = _call("settings.get")
    assert "desktop_notifications" in out
    assert out["desktop_notifications"] is True


def test_settings_update_sets_desktop_notifications():
    out = _call("settings.update", {"desktop_notifications": False})
    assert out["desktop_notifications"] is False
    assert config.get_desktop_notifications() is False


# ── #55 cross-profile sync ───────────────────────────────────────────

def _setup_two_profiles(tmp_path):
    a = tmp_path / "AddOnsA"
    b = tmp_path / "AddOnsB"
    a.mkdir()
    b.mkdir()
    src = state.add_or_update_profile("Source", str(a))
    tgt = state.add_or_update_profile("Target", str(b))
    return src, tgt


def test_sync_preview_buckets(monkeypatch, tmp_path):
    src, tgt = _setup_two_profiles(tmp_path)
    installed.save(src, {
        "details": {"name": "Details!", "version": "1.0"},
        "weakauras": {"name": "WeakAuras", "version": "2.0"},
        "orphan": {"name": "Orphan", "version": "9.0"},
    })
    installed.save(tgt, {
        "weakauras": {"name": "WeakAuras", "version": "1.0"},
    })

    from wowusky import orchestrator as _orch
    catalog = {"details", "weakauras"}
    monkeypatch.setattr(_orch, "find_addon_by_id",
                        lambda aid: {"id": aid, "name": aid} if aid in catalog else None)

    out = _call("profile.syncPreview", {"source": src, "target": tgt})
    assert out["source"] == src
    assert {r["id"] for r in out["new"]} == {"details"}
    assert {r["id"] for r in out["conflict"]} == {"weakauras"}
    assert {r["id"] for r in out["skipped"]} == {"orphan"}


def test_sync_preview_requires_distinct():
    with pytest.raises(ValueError):
        _call("profile.syncPreview", {"source": "x", "target": "x"})


def test_sync_apply_installs_new(monkeypatch, tmp_path):
    src, tgt = _setup_two_profiles(tmp_path)
    installed.save(src, {
        "details": {"name": "Details!", "version": "1.0"},
        "weakauras": {"name": "WeakAuras", "version": "2.0"},
    })
    installed.save(tgt, {
        "weakauras": {"name": "WeakAuras", "version": "1.0"},
    })

    from wowusky import orchestrator as _orch
    monkeypatch.setattr(_orch, "find_addon_by_id", lambda aid: {"id": aid, "name": aid})

    calls: list[str] = []

    def _fake_install(entry, addons_path, log=print):
        calls.append(entry["id"])

    monkeypatch.setattr(_orch, "install_addon", _fake_install)

    out = _call("profile.syncApply", {"source": src, "target": tgt, "skip_ids": ["weakauras"]})
    assert out["ok"] is True
    assert out["installed"] == ["details"]
    assert calls == ["details"]
    # Active profile restored.
    assert state.get_active_profile_id() == tgt


def test_sync_apply_requires_source():
    with pytest.raises(ValueError):
        _call("profile.syncApply", {})
