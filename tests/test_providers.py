"""Tests for provider resolve / page_url logic that doesn't hit the network."""

import pytest

from wowusky.providers import (
    AddonRef,
    CurseForgeProvider,
    CurseForgeWebProvider,
    GitHubProvider,
    TukuiProvider,
    WagoProvider,
    WoWInterfaceProvider,
    get_provider,
    list_providers,
    pick_asset,
    slug_from_ref,
)

# ── registry ─────────────────────────────────────────────────────────

def test_registry_lists_all_providers():
    names = list_providers()
    for required in ("github", "tukui", "wowi",
                     "curseforge", "curseforge_web", "wago"):
        assert required in names


def test_registry_returns_provider_with_correct_name():
    assert get_provider("github").name == "github"
    assert get_provider("tukui").name == "tukui"


def test_registry_raises_keyerror_for_unknown():
    with pytest.raises(KeyError):
        get_provider("does-not-exist")


# ── GitHub ───────────────────────────────────────────────────────────

def test_github_resolves_owner_slash_repo():
    ref = GitHubProvider().resolve("WeakAuras/WeakAuras2")
    assert ref.ref == "WeakAuras/WeakAuras2"
    assert ref.page_url.endswith("WeakAuras/WeakAuras2")


def test_github_resolves_full_url():
    ref = GitHubProvider().resolve("https://github.com/Stanzilla/BugSack")
    assert ref.ref == "Stanzilla/BugSack"


def test_github_rejects_single_word():
    assert GitHubProvider().resolve("notavalidrepo") is None
    assert GitHubProvider().resolve("") is None


def test_pick_asset_prefers_flavor_keyword():
    assets = [
        {"name": "MyAddon-classic.zip",  "size": 100, "browser_download_url": "a"},
        {"name": "MyAddon-mainline.zip", "size": 100, "browser_download_url": "b"},
    ]
    assert pick_asset(assets, "vanilla")["browser_download_url"] == "a"
    assert pick_asset(assets, "retail")["browser_download_url"] == "b"


def test_pick_asset_skips_nolib_packages():
    assets = [
        {"name": "MyAddon-nolib.zip", "size": 100, "browser_download_url": "x"},
        {"name": "MyAddon.zip",       "size":  50, "browser_download_url": "y"},
    ]
    chosen = pick_asset(assets, "")
    assert chosen["browser_download_url"] == "y"


def test_pick_asset_returns_none_when_no_zips():
    assert pick_asset([{"name": "release.tar.gz"}], "") is None


# ── Tukui ────────────────────────────────────────────────────────────

def test_tukui_accepts_known_slugs():
    assert TukuiProvider().resolve("elvui").ref == "elvui"
    assert TukuiProvider().resolve("tukui").ref == "tukui"


def test_tukui_rejects_unknown_slug():
    assert TukuiProvider().resolve("randomthing") is None


def test_tukui_handles_legacy_url():
    ref = TukuiProvider().resolve("https://www.tukui.org/addons.php?id=elvui")
    assert ref is not None
    assert ref.ref == "elvui"


# ── WoWInterface ─────────────────────────────────────────────────────

def test_wowi_extracts_numeric_id_from_string():
    ref = WoWInterfaceProvider().resolve("9018")
    assert ref.ref == "9018"
    assert "info9018" in ref.page_url


def test_wowi_extracts_id_from_url():
    ref = WoWInterfaceProvider().resolve(
        "https://www.wowinterface.com/downloads/info10855")
    assert ref.ref == "10855"


def test_wowi_rejects_empty():
    assert WoWInterfaceProvider().resolve("") is None
    assert WoWInterfaceProvider().resolve("not-a-number") is None


# ── CurseForge ───────────────────────────────────────────────────────

def test_cf_web_resolves_full_url():
    ref = CurseForgeWebProvider().resolve(
        "https://www.curseforge.com/wow/addons/details")
    assert ref.ref == "details"
    assert ref.page_url.endswith("/details")


def test_cf_web_resolves_bare_slug():
    ref = CurseForgeWebProvider().resolve("weakauras-2")
    assert ref.ref == "weakauras-2"


def test_cf_api_resolves_numeric_id():
    ref = CurseForgeProvider().resolve("314409")
    assert ref.ref == "314409"
    assert ref.page_url.endswith("/314409")


def test_cf_api_resolves_slug_when_no_key():
    ref = CurseForgeProvider(api_key="").resolve("weakauras-2")
    assert ref.ref == "weakauras-2"


def test_cf_api_returns_none_for_empty():
    assert CurseForgeProvider().resolve("") is None


def test_slug_from_ref_normalises_inputs():
    assert slug_from_ref("https://www.curseforge.com/wow/addons/details/") == "details"
    assert slug_from_ref("plain-slug") == "plain-slug"
    assert slug_from_ref("") == ""


# ── Wago ─────────────────────────────────────────────────────────────

def test_wago_extracts_slug_from_url():
    ref = WagoProvider().resolve("https://wago.io/abc-123")
    assert ref.ref == "abc-123"


def test_wago_treats_bare_text_as_slug():
    ref = WagoProvider().resolve("XYZ_789")
    assert ref.ref == "XYZ_789"
