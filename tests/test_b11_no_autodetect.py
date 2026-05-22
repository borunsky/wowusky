"""Regression tests for B11 — autodetection must not silently
materialise a profile.

A fresh data directory must stay unconfigured: load_profiles() must
not run scan_wow_installations() and write the first WoW install it
finds into profiles.json. The user picks the path explicitly (GUI
dialog / terminal prompt). Pre-0.4 single-profile config migration is
still allowed, because that path was chosen by the user before.
"""

from __future__ import annotations

import json

import wowusky.app as app


def _isolate(monkeypatch, tmp_path):
    """Point app.py's path constants at a fresh tmp directory."""
    data = tmp_path / "wowusky"
    data.mkdir()
    monkeypatch.setattr(app, "CONFIG_DIR",    str(data))
    monkeypatch.setattr(app, "CONFIG_FILE",   str(data / "config.json"))
    monkeypatch.setattr(app, "PROFILES_FILE", str(data / "profiles.json"))
    return data


# ── B11: empty data dir stays unconfigured ──────────────────────────

def test_b11_empty_dir_does_not_autodetect(monkeypatch, tmp_path):
    data = _isolate(monkeypatch, tmp_path)

    # Pretend autodetection *would* find a real install.
    monkeypatch.setattr(app, "scan_wow_installations", lambda: [
        {"addons_path": "/real/wow/_anniversary_/Interface/AddOns",
         "flavor_key": "anniversary", "flavor_name": "TBC Anniversary"},
    ])

    result = app.load_profiles()

    assert result == {"active": None, "profiles": {}}, (
        "load_profiles() materialised a profile from autodetection (B11)"
    )
    assert not (data / "profiles.json").exists(), (
        "load_profiles() wrote profiles.json for an unconfigured dir (B11)"
    )


def test_b11_unconfigured_addons_path_is_none(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(app, "scan_wow_installations", lambda: [
        {"addons_path": "/real/wow/_retail_/Interface/AddOns",
         "flavor_key": "retail", "flavor_name": "Retail"},
    ])
    # get_addons_path() must be None so the GUI/terminal path picker
    # is triggered instead of a silent autodetected path.
    assert app.get_addons_path() is None


def test_b11_scan_not_called_when_profiles_exist(monkeypatch, tmp_path):
    """If profiles.json already exists, autodetection must not run."""
    data = _isolate(monkeypatch, tmp_path)
    (data / "profiles.json").write_text(json.dumps({
        "active": "retail",
        "profiles": {"retail": {
            "id": "retail", "name": "Retail", "flavor": "retail",
            "addons_path": "/chosen/path/_retail_/Interface/AddOns",
        }},
    }), encoding="utf-8")

    def boom():
        raise AssertionError("scan_wow_installations ran despite "
                             "existing profiles.json")

    monkeypatch.setattr(app, "scan_wow_installations", boom)
    result = app.load_profiles()
    assert result["active"] == "retail"


# ── migration of a pre-0.4 config is still allowed ──────────────────

def test_b11_legacy_config_is_still_migrated(monkeypatch, tmp_path):
    """A pre-0.4 config.json with addons_path was a deliberate user
    choice — adopting it is expected, not a surprise."""
    data = _isolate(monkeypatch, tmp_path)
    (data / "config.json").write_text(json.dumps({
        "addons_path": "/legacy/wow/_classic_era_/Interface/AddOns",
    }), encoding="utf-8")

    # Autodetection must NOT be consulted for the migration path.
    monkeypatch.setattr(app, "scan_wow_installations", lambda: [
        {"addons_path": "/some/other/_retail_/Interface/AddOns",
         "flavor_key": "retail", "flavor_name": "Retail"},
    ])

    result = app.load_profiles()
    paths = [p["addons_path"] for p in result["profiles"].values()]
    assert paths == ["/legacy/wow/_classic_era_/Interface/AddOns"], (
        "legacy config.json addons_path was not migrated correctly"
    )
    assert (data / "profiles.json").exists()
