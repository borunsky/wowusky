"""Tests for v0.17.0 features (#62/#63/#64):
- aura update notes (#62)
- companion-rebuild systemd timer (#63)
- bulk untrack + collection import (#64)
"""

from __future__ import annotations

import pytest

import wowusky.bridge.server as server
import wowusky.core.schedule as schedule
import wowusky.core.state as state
import wowusky.core.wago as wago


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    from wowusky.core import paths as _paths

    data = tmp_path / "wowusky"
    data.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(_paths, "DATA_DIR", data)
    monkeypatch.setattr(_paths, "CONFIG_FILE", data / "config.json")
    monkeypatch.setattr(_paths, "PROFILES_FILE", data / "profiles.json")
    monkeypatch.setattr(_paths, "WAGO_FILE", data / "wago.json")
    monkeypatch.setattr(_paths, "INSTALLED_DIR", data / "installed")
    monkeypatch.setattr(_paths, "CONFIG_DIR", data)
    monkeypatch.setattr(state, "CONFIG_FILE", str(data / "config.json"))
    monkeypatch.setattr(state, "PROFILES_FILE", str(data / "profiles.json"))
    monkeypatch.setattr(state, "WAGO_FILE", str(data / "wago.json"))
    monkeypatch.setattr(state, "INSTALLED_DIR", str(data / "installed"))
    monkeypatch.setattr(state, "CONFIG_DIR", str(data))
    return data


def _call(method: str, params: dict | None = None):
    return server._METHODS[method](params or {})


# ── #62 aura update notes ────────────────────────────────────────────

def test_wago_update_notes(monkeypatch):
    wago.save_wago({"auras": {"abc": {"name": "Cooldowns", "slug": "abc", "version": 3}}})
    monkeypatch.setattr(wago, "wago_fetch_info",
                        lambda slug: {"version": 5, "changelog": "Fixed timers"})
    out = wago.wago_update_notes("abc")
    assert out["current_version"] == 3
    assert out["latest_version"] == 5
    assert out["changelog"] == "Fixed timers"


def test_wago_update_notes_untracked():
    wago.save_wago({"auras": {}})
    assert wago.wago_update_notes("nope") is None


def test_wago_update_notes_bridge_requires_slug():
    with pytest.raises(ValueError):
        _call("wago.updateNotes", {})


def test_wago_update_notes_bridge_untracked():
    wago.save_wago({"auras": {}})
    out = _call("wago.updateNotes", {"slug": "ghost"})
    assert out == {"error": "not tracked"}


# ── #63 companion timer ──────────────────────────────────────────────

def test_write_companion_units(monkeypatch, tmp_path):
    monkeypatch.setattr(schedule, "_unit_dir", lambda: str(tmp_path / "units"))
    schedule._write_companion_units("weekly")
    with open(schedule.companion_service_path()) as fh:
        svc = fh.read()
    assert "weakauras companion -q" in svc
    with open(schedule.companion_timer_path()) as fh:
        tmr = fh.read()
    assert "OnCalendar=weekly" in tmr


def test_companion_status_not_available(monkeypatch):
    monkeypatch.setattr(schedule, "available", lambda: False)
    out = _call("companionSchedule.status")
    assert out == {"available": False, "installed": False}


# ── #64 bulk untrack + collections ───────────────────────────────────

def test_wago_untrack_many():
    wago.save_wago({"auras": {
        "a": {"slug": "a", "name": "A"},
        "b": {"slug": "b", "name": "B"},
        "c": {"slug": "c", "name": "C"},
    }})
    out = _call("wago.untrackMany", {"slugs": ["a", "c", "missing"]})
    assert out["ok"] is True
    assert out["removed"] == 2
    assert set(wago.load_wago()["auras"].keys()) == {"b"}


def test_wago_untrack_many_requires_slugs():
    with pytest.raises(ValueError):
        _call("wago.untrackMany", {})


def test_wago_fetch_collection_parses_members(monkeypatch):
    monkeypatch.setattr(wago, "http_get_json",
                        lambda url: {"auras": [{"slug": "x"}, {"slug": "y"}, "z"]})
    assert wago.wago_fetch_collection("col1") == ["x", "y", "z"]


def test_wago_add_collection(monkeypatch):
    wago.save_wago({"auras": {"x": {"slug": "x", "name": "X"}}})
    monkeypatch.setattr(wago, "wago_fetch_collection", lambda cid: ["x", "y", "z"])
    monkeypatch.setattr(wago, "wago_fetch_info", lambda slug: {"name": slug, "version": 1})
    out = _call("wago.addCollection", {"url": "https://wago.io/collections/col1"})
    assert out["ok"] is True
    assert set(out["added"]) == {"y", "z"}
    assert out["already"] == ["x"]


def test_wago_add_collection_empty(monkeypatch):
    monkeypatch.setattr(wago, "wago_fetch_collection", lambda cid: [])
    out = _call("wago.addCollection", {"url": "col-empty"})
    assert out["ok"] is False
