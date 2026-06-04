"""Tests for wowusky.core.search — fuzzy search + tag support."""

from __future__ import annotations

from wowusky.core.search import search

_CATALOG = [
    {"id": "elvui", "name": "ElvUI", "description": "Full UI replacement", "category": "Interface", "tags": ["ui", "healer", "tank"]},
    {"id": "weakauras", "name": "WeakAuras 2", "description": "Aura framework", "category": "Buffs", "tags": ["aura", "healer"]},
    {"id": "bigwigs", "name": "BigWigs", "description": "Boss timers", "category": "Raid", "tags": ["raid", "tank"]},
    {"id": "details", "name": "Details!", "description": "Damage meter", "category": "Combat", "tags": ["dps", "damage-meter"]},
    {"id": "bagnon", "name": "Bagnon", "description": "Bag management", "category": "Bags", "tags": ["bags", "ui"]},
]


def ids(results):
    return [r["id"] for r in results]


# ── basic match ──────────────────────────────────────────────────────────

def test_empty_query_returns_all():
    assert len(search(_CATALOG, "")) == 5


def test_exact_name_match():
    r = search(_CATALOG, "ElvUI")
    assert r[0]["id"] == "elvui"


def test_case_insensitive():
    r = search(_CATALOG, "elvui")
    assert r[0]["id"] == "elvui"


def test_fuzzy_typo():
    # "elvi" is a prefix of the normalized token "elvui"
    r = search(_CATALOG, "elv")
    assert "elvui" in ids(r)


def test_substring_description():
    r = search(_CATALOG, "damage")
    assert "details" in ids(r)


def test_no_match_returns_empty():
    r = search(_CATALOG, "xyznonexistent")
    assert r == []


# ── category filter ──────────────────────────────────────────────────────

def test_category_filter():
    r = search(_CATALOG, "", category="Bags")
    assert ids(r) == ["bagnon"]


def test_category_all_returns_everything():
    r = search(_CATALOG, "", category="All")
    assert len(r) == 5


# ── tag filter ───────────────────────────────────────────────────────────

def test_tag_filter_single():
    r = search(_CATALOG, "tag:healer")
    assert set(ids(r)) == {"elvui", "weakauras"}


def test_tag_filter_combined_with_freetext():
    r = search(_CATALOG, "tag:healer elv")
    assert ids(r) == ["elvui"]


def test_tag_filter_no_match():
    r = search(_CATALOG, "tag:nonexistenttag")
    assert r == []


def test_tag_filter_multi():
    r = search(_CATALOG, "tag:ui tag:healer")
    assert ids(r) == ["elvui"]


# ── favorites filter ─────────────────────────────────────────────────────

def test_only_favorites():
    favs = {"bigwigs", "bagnon"}
    r = search(_CATALOG, "", only_favorites=True, favorites=favs)
    assert set(ids(r)) == {"bigwigs", "bagnon"}


def test_only_favorites_empty_set():
    r = search(_CATALOG, "", only_favorites=True, favorites=set())
    assert r == []


# ── ranking ──────────────────────────────────────────────────────────────

def test_exact_match_ranks_first():
    r = search(_CATALOG, "bagnon")
    assert r[0]["id"] == "bagnon"
