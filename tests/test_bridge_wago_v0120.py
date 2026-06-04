"""Tests for the v0.12.0 Wago bridge methods (#48/#49/#50).

These exercise the JSON-RPC handlers directly, with all on-disk state in a
tmp dir and network/provider calls mocked, so the suite stays offline.
"""

from __future__ import annotations

import pytest

import wowusky.bridge.server as server
import wowusky.core.state as state
import wowusky.core.wago as wago


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


# ── wago.search (#48) ───────────────────────────────────────────────

def test_search_empty_query_returns_no_items():
    assert _call("wago.search", {"query": "  "}) == {"items": []}


def test_search_normalises_dict_response(monkeypatch):
    monkeypatch.setattr(wago, "wago_search", lambda q, limit=20: {
        "data": [
            {"slug": "abc", "name": "Cool Aura", "username": "Bob", "type": "WeakAura"},
            {"_id": "def", "name": "Other"},
            {"name": "no-slug-skipped"},
            "garbage",
        ]
    })
    out = _call("wago.search", {"query": "cool"})
    assert out["items"] == [
        {"slug": "abc", "name": "Cool Aura", "author": "Bob", "type": "WeakAura"},
        {"slug": "def", "name": "Other", "author": "", "type": "WeakAura"},
    ]


def test_search_handles_list_and_none(monkeypatch):
    monkeypatch.setattr(wago, "wago_search", lambda q, limit=20: None)
    assert _call("wago.search", {"query": "x"}) == {"items": []}


# ── wago.add (#48) ──────────────────────────────────────────────────

def test_add_requires_slug():
    with pytest.raises(ValueError):
        _call("wago.add", {})


def test_add_tracks_aura(monkeypatch):
    monkeypatch.setattr(wago, "wago_fetch_info", lambda slug: {"name": "Tracked", "version": 2})
    out = _call("wago.add", {"slug": "abc"})
    assert out["ok"] is True
    assert out["slug"] == "abc"
    assert "abc" in wago.load_wago().get("auras", {})


# ── wago.importFromSavedVariables (#49) ─────────────────────────────

def test_import_from_savedvariables(monkeypatch):
    monkeypatch.setattr(
        wago, "import_existing_weakauras_from_savedvariables",
        lambda log=None: {"added": 3, "existing": 1, "failed": 0, "slugs": ["a", "b", "c"]},
    )
    out = _call("wago.importFromSavedVariables", {})
    assert out == {"ok": True, "added": 3, "existing": 1, "failed": 0, "slugs": ["a", "b", "c"]}


def test_import_reports_error(monkeypatch):
    def _boom(log=None):
        raise RuntimeError("no WTF path")
    monkeypatch.setattr(wago, "import_existing_weakauras_from_savedvariables", _boom)
    out = _call("wago.importFromSavedVariables", {})
    assert out["ok"] is False
    assert "no WTF path" in out["error"]


# ── wago.generateCompanion (#50) ────────────────────────────────────

def test_generate_companion(monkeypatch):
    wago.save_wago({"auras": {"a": {"name": "A"}, "b": {"name": "B"}}})
    import wowusky.orchestrator as orch
    monkeypatch.setattr(orch, "generate_wac_companion", lambda ap: True)
    out = _call("wago.generateCompanion", {})
    assert out["ok"] is True
    assert out["count"] == 2


def test_generate_companion_failure(monkeypatch):
    import wowusky.orchestrator as orch
    monkeypatch.setattr(orch, "generate_wac_companion", lambda ap: False)
    out = _call("wago.generateCompanion", {})
    assert out["ok"] is False
