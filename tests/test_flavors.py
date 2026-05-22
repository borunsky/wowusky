"""Tests for flavor detection and addon compatibility logic."""

from wowusky.core.flavors import (
    FLAVOR_COMPATIBILITY,
    WOW_FLAVORS,
    flavor_display_name,
    flavor_for_directory,
    flavor_interface,
    is_compatible,
)

# ── is_compatible ────────────────────────────────────────────────────

def test_tbc_anniversary_accepts_tbc_and_classic():
    assert is_compatible(['classic'], 'anniversary')
    assert is_compatible(['tbc'],     'anniversary')
    assert is_compatible(['vanilla'], 'anniversary')


def test_tbc_anniversary_rejects_retail_only():
    assert not is_compatible(['mainline'], 'anniversary')
    assert not is_compatible(['retail'],   'anniversary')


def test_retail_only_accepts_mainline():
    assert is_compatible(['retail'],   'retail')
    assert is_compatible(['mainline'], 'retail')
    assert not is_compatible(['classic'],     'retail')
    assert not is_compatible(['anniversary'], 'retail')


def test_all_flavor_tag_matches_every_client():
    for client in ('anniversary', 'vanilla', 'mop_classic', 'retail', 'ptr'):
        assert is_compatible(['all'], client), f"'all' should match {client}"


def test_no_client_returns_true_so_browse_shows_everything():
    assert is_compatible(['retail'], None)
    assert is_compatible(['classic'], '')


def test_mop_classic_accepts_classic_addons():
    assert is_compatible(['classic'], 'mop_classic')
    assert is_compatible(['mop'],     'mop_classic')


# ── flavor_for_directory ─────────────────────────────────────────────

def test_flavor_for_directory_recognises_anniversary():
    p = "/home/u/.local/share/Steam/.../Program Files (x86)/World of Warcraft/_anniversary_/Interface/AddOns"
    assert flavor_for_directory(p) == "anniversary"


def test_flavor_for_directory_recognises_all_known_markers():
    cases = {
        "_retail_":      "retail",
        "_classic_era_": "vanilla",
        "_classic_":     "mop_classic",
        "_ptr_":         "ptr",
    }
    for marker, expected in cases.items():
        p = f"/games/WoW/{marker}/Interface/AddOns"
        assert flavor_for_directory(p) == expected


def test_flavor_for_directory_returns_none_for_unknown_path():
    assert flavor_for_directory("/no/wow/here") is None


# ── flavor_display_name / interface ──────────────────────────────────

def test_flavor_display_name_returns_human_string():
    assert "Anniversary" in flavor_display_name("anniversary")
    assert flavor_display_name("retail") == "Retail"


def test_flavor_interface_returns_known_numbers():
    assert flavor_interface("anniversary") == 20505
    assert flavor_interface("vanilla") == 11508
    assert flavor_interface("retail") >= 100000


def test_flavor_interface_unknown_key_returns_zero():
    assert flavor_interface("klingon") == 0
