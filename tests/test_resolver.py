"""Tests for wowusky.core.resolver — provider URL/page/label dispatch."""

from __future__ import annotations

import urllib.parse

import wowusky.core.resolver as resolver

# ── cf_web_version_type ─────────────────────────────────────────────

def test_cf_web_version_type_known_flavor():
    assert resolver.cf_web_version_type("anniversary") == 67408
    assert resolver.cf_web_version_type("retail") == 517


def test_cf_web_version_type_unknown_falls_back_to_retail():
    assert resolver.cf_web_version_type(None) == 517
    assert resolver.cf_web_version_type("nonsense") is None


# ── curseforge_search_url ───────────────────────────────────────────

def test_search_url_plain_query_seeds_flavor_hint():
    url = resolver.curseforge_search_url("details", "anniversary")
    assert url.startswith("https://www.curseforge.com/wow/search?")
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert qs["gameVersionTypeId"] == ["67408"]
    assert "tbc classic anniversary" in qs["search"][0]
    assert "details" in qs["search"][0]


def test_search_url_direct_slug_ref_returns_addon_page():
    url = resolver.curseforge_search_url("https://www.curseforge.com/wow/addons/weakauras-2", "retail")
    assert url == "https://www.curseforge.com/wow/addons/weakauras-2"


def test_search_url_retail_has_no_search_hint():
    url = resolver.curseforge_search_url("", "retail")
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert "search" not in qs


# ── curseforge_files_url ────────────────────────────────────────────

def test_files_url_for_slug():
    url = resolver.curseforge_files_url("weakauras-2", "retail")
    assert url == "https://www.curseforge.com/wow/addons/weakauras-2/files/all"


def test_files_url_without_slug_falls_back_to_search():
    url = resolver.curseforge_files_url("", "retail")
    assert url.startswith("https://www.curseforge.com/wow/search?")


# ── addon_provider_page ─────────────────────────────────────────────

def test_provider_page_curseforge_web():
    addon = {"source": "curseforge_web", "curseforge_slug": "details"}
    assert resolver.addon_provider_page(addon, "retail") == \
        "https://www.curseforge.com/wow/addons/details/files/all"


def test_provider_page_tukui_prefers_download_url():
    addon = {"source": "tukui", "download_url": "https://x/dl", "api_url": "https://x/api"}
    assert resolver.addon_provider_page(addon, "retail") == "https://x/dl"


def test_provider_page_unknown_source_uses_url_field():
    addon = {"source": "mystery", "url": "https://example.com"}
    assert resolver.addon_provider_page(addon, "retail") == "https://example.com"


def test_provider_page_github_builds_repo_url():
    addon = {"source": "github", "repo": "owner/repo"}
    assert resolver.addon_provider_page(addon, "retail") == "https://github.com/owner/repo"


# ── provider_action_label ───────────────────────────────────────────

def test_action_label_curseforge_web():
    assert resolver.provider_action_label({"source": "curseforge_web"}) == "Open CF"


def test_action_label_curseforge_manual():
    assert resolver.provider_action_label({"source": "curseforge_manual"}) == "Open update"


def test_action_label_github_install_vs_update():
    assert resolver.provider_action_label({"source": "github"}, installed=False) == "Install"
    assert resolver.provider_action_label({"source": "github"}, installed=True) == "Update"


# ── SEMI_MANAGED_SOURCES ────────────────────────────────────────────

def test_semi_managed_sources_membership():
    assert "curseforge_web" in resolver.SEMI_MANAGED_SOURCES
    assert "wowi" in resolver.SEMI_MANAGED_SOURCES
    assert "github" not in resolver.SEMI_MANAGED_SOURCES
