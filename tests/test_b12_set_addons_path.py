"""Regression tests for B12 — set_addons_path must create a profile
when none exists.

B11 (v0.4.6) made a fresh data directory correctly unconfigured:
get_active_profile() returns {}. set_addons_path() had an `if prof:`
guard that then skipped profile creation entirely — the path was
"set" but no profile carried it, so get_current_flavor() returned
None and the catalog was shown unfiltered. set_addons_path() must
create a profile in that case, not silently do nothing.
"""

from __future__ import annotations

import wowusky.app as app
import wowusky.core.state as state


def _isolate(monkeypatch, tmp_path):
    """Point the manager-state path constants at a fresh tmp directory.

    The persistence logic now lives in wowusky.core.state, so the
    constants it reads must be patched there.
    """
    data = tmp_path / "wowusky"
    data.mkdir(parents=True)
    for mod in (app, state):
        monkeypatch.setattr(mod, "CONFIG_DIR",     str(data), raising=False)
        monkeypatch.setattr(mod, "CONFIG_FILE",    str(data / "config.json"), raising=False)
        monkeypatch.setattr(mod, "PROFILES_FILE",  str(data / "profiles.json"), raising=False)
        monkeypatch.setattr(mod, "INSTALLED_DIR",  str(data / "installed"), raising=False)
    # Autodetection must never interfere with these tests.
    monkeypatch.setattr(app, "scan_wow_installations", lambda: [])
    return data


def test_b12_set_addons_path_creates_profile_when_none_exists(
        monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    # Precondition: genuinely unconfigured (the B11 state).
    assert app.get_active_profile() == {}
    assert app.get_addons_path() is None

    app.set_addons_path("/games/wow/_retail_/Interface/AddOns")

    prof = app.get_active_profile()
    assert prof, "set_addons_path created no profile (B12)"
    assert prof.get("addons_path") == "/games/wow/_retail_/Interface/AddOns"
    assert app.get_addons_path() == "/games/wow/_retail_/Interface/AddOns"


def test_b12_flavor_detected_after_set_addons_path(monkeypatch, tmp_path):
    """The whole point of B12: flavor must resolve, not stay None."""
    _isolate(monkeypatch, tmp_path)
    app.set_addons_path("/games/wow/_retail_/Interface/AddOns")
    assert app.get_current_flavor() == "retail"


def test_b12_flavor_detected_for_each_marker(monkeypatch, tmp_path):
    """Every flavor directory marker must resolve to its key."""
    cases = {
        "_retail_":      "retail",
        "_anniversary_": "anniversary",
        "_classic_era_": "vanilla",
    }
    for marker, expected in cases.items():
        _isolate(monkeypatch, tmp_path / marker)
        app.set_addons_path(f"/games/wow/{marker}/Interface/AddOns")
        assert app.get_current_flavor() == expected, (
            f"{marker} resolved to {app.get_current_flavor()}, "
            f"expected {expected}"
        )


def test_b12_set_addons_path_updates_existing_profile(monkeypatch, tmp_path):
    """When a profile already exists, the path is updated in place —
    no duplicate profile is spawned."""
    _isolate(monkeypatch, tmp_path)

    app.set_addons_path("/games/wow/_retail_/Interface/AddOns")
    first = app.load_profiles()
    assert len(first["profiles"]) == 1

    # Same active profile, new path.
    app.set_addons_path("/games/wow2/_retail_/Interface/AddOns")
    second = app.load_profiles()
    assert len(second["profiles"]) == 1, (
        "set_addons_path spawned a second profile instead of updating"
    )
    assert app.get_addons_path() == "/games/wow2/_retail_/Interface/AddOns"
