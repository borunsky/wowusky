"""Tests for wowusky.core.wago — tracking list + WeakAuras helpers."""

from __future__ import annotations

import os

import pytest

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
    state.add_or_update_profile("Test", "/wow/_retail_/Interface/AddOns")
    return data


# ── extract_wago_slugs_from_text (pure) ─────────────────────────────

def test_extract_slugs_from_url():
    text = "see https://wago.io/abcDEF123 for details"
    assert "abcDEF123" in wago.extract_wago_slugs_from_text(text)


def test_extract_slugs_from_wagoid_key():
    text = '["wagoID"] = "myAura01"'
    assert "myAura01" in wago.extract_wago_slugs_from_text(text)


def test_extract_slugs_dedupes_and_sorts():
    text = 'wago.io/aaa ["wago"] = "bbb" wagoId = "aaa"'
    out = wago.extract_wago_slugs_from_text(text)
    assert out == ["aaa", "bbb"]


def test_extract_slugs_empty_text():
    assert wago.extract_wago_slugs_from_text("nothing here") == []


# ── tracking list (wago.json) ───────────────────────────────────────

def test_wago_add_records_entry(monkeypatch):
    monkeypatch.setattr(wago, "wago_fetch_info", lambda slug: {"name": "Cool Aura", "version": 3})
    entry = wago.wago_add("cool")
    assert entry["name"] == "Cool Aura"
    assert entry["version"] == 3
    assert "cool" in state.load_wago()["auras"]


def test_wago_add_uses_slug_when_no_name(monkeypatch):
    monkeypatch.setattr(wago, "wago_fetch_info", lambda slug: None)
    entry = wago.wago_add("xyz")
    assert entry["name"] == "xyz"
    assert entry["version"] == 1


def test_wago_remove(monkeypatch):
    monkeypatch.setattr(wago, "wago_fetch_info", lambda slug: None)
    wago.wago_add("gone")
    assert wago.wago_remove("gone") is True
    assert "gone" not in state.load_wago().get("auras", {})


def test_wago_remove_missing_returns_false():
    assert wago.wago_remove("never") is False


def test_wago_check_updates_detects_newer(monkeypatch):
    monkeypatch.setattr(wago, "wago_fetch_info", lambda slug: {"version": 1})
    wago.wago_add("aura")
    # Now pretend the remote bumped to v5
    monkeypatch.setattr(wago, "wago_fetch_info", lambda slug: {"version": 5})
    updates = wago.wago_check_updates()
    assert "aura" in updates
    assert state.load_wago()["auras"]["aura"]["latest_version"] == 5


# ── find_weakauras_savedvariables ───────────────────────────────────

def test_find_savedvariables_none_for_missing_path():
    assert wago.find_weakauras_savedvariables("/no/such/wtf") == []


def test_find_savedvariables_locates_file(tmp_path):
    sv = tmp_path / "Account" / "12345" / "SavedVariables"
    sv.mkdir(parents=True)
    f = sv / "WeakAuras.lua"
    f.write_text("wago.io/abc")
    found = wago.find_weakauras_savedvariables(str(tmp_path))
    assert str(f) in found


# ── import_existing_weakauras_from_savedvariables ───────────────────

def test_import_existing_no_files():
    result = wago.import_existing_weakauras_from_savedvariables()
    assert result == {"added": 0, "existing": 0, "failed": 0, "files": [], "slugs": []}


def test_import_existing_adds_slugs(tmp_path, monkeypatch):
    sv = tmp_path / "Account" / "1" / "SavedVariables"
    sv.mkdir(parents=True)
    (sv / "WeakAuras.lua").write_text('["wagoID"] = "auraOne"')
    monkeypatch.setattr(wago, "get_wtf_path", lambda: str(tmp_path))
    monkeypatch.setattr(wago, "wago_fetch_info", lambda slug: {"name": slug, "version": 1})
    result = wago.import_existing_weakauras_from_savedvariables()
    assert result["added"] == 1
    assert "auraOne" in result["slugs"]


# ── generate_wac_companion ──────────────────────────────────────────

def test_generate_wac_companion_writes_files(tmp_path, monkeypatch):
    monkeypatch.setattr(wago, "wago_fetch_info", lambda slug: {"name": "A", "version": 1})
    wago.wago_add("aura1")
    monkeypatch.setattr(wago, "wago_fetch_encoded", lambda slug: "ENCODED")
    addons = tmp_path / "AddOns"
    addons.mkdir()
    ok = wago.generate_wac_companion(str(addons), interface=110000, app_version="0.6.3")
    assert ok
    comp = addons / "WeakAurasCompanion"
    assert (comp / "WeakAurasCompanion.toc").is_file()
    assert (comp / "data.lua").is_file()
    assert (comp / "init.lua").is_file()
    toc = (comp / "WeakAurasCompanion.toc").read_text()
    assert "110000" in toc
    assert "0.6.3" in toc
    assert "wac" in state.load_installed()


def test_generate_wac_companion_false_for_empty_path():
    assert wago.generate_wac_companion("") is False
