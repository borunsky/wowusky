"""Tests for the bridge action methods (install / remove / restore).

These exercise the JSON-RPC handlers in :mod:`wowusky.bridge.server` directly,
with all on-disk state redirected into a tmp dir so nothing touches the real
profile. Network-touching install is covered only for its error path (unknown
id) to keep the suite offline and deterministic.
"""

from __future__ import annotations

import pytest

import wowusky.bridge.server as server
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
    addons = tmp_path / "AddOns"
    addons.mkdir()
    state.add_or_update_profile("Test", str(addons))
    return data


def _call(method: str, params: dict | None = None):
    return server._METHODS[method](params or {})


# ── install ─────────────────────────────────────────────────────────

def test_install_unknown_id_reports_error():
    r = _call("addon.install", {"id": "__does_not_exist__"})
    assert r["ok"] is False
    assert "not in catalog" in r["error"]


def test_install_requires_id():
    with pytest.raises(ValueError):
        _call("addon.install", {})


def test_update_is_aliased_to_install():
    assert server._METHODS["addon.update"] is server._METHODS["addon.install"]


# ── remove ──────────────────────────────────────────────────────────

def test_remove_existing_addon():
    state.save_installed({"elvui": {"name": "ElvUI", "version": "1",
                                    "folders": [], "source": "tukui"}})
    r = _call("addon.remove", {"id": "elvui"})
    assert r["ok"] is True
    assert "elvui" not in state.load_installed()


def test_remove_requires_id():
    with pytest.raises(ValueError):
        _call("addon.remove", {})


# ── restore ─────────────────────────────────────────────────────────

def test_restore_missing_full_backup_errors():
    r = _call("backups.restore", {"path": "/no/such/backup.zip"})
    assert r["ok"] is False
    assert r["error"]


def test_restore_requires_path():
    with pytest.raises(ValueError):
        _call("backups.restore", {})
