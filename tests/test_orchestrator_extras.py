"""Tests for the v0.9.5 orchestrator additions: dependency preview and
download-ZIP catalog matching. Network/provider calls are not involved.
"""

from __future__ import annotations

from wowusky import orchestrator as orch

_CATALOG = [
    {"id": "elvui", "name": "ElvUI", "depends": ["ace3"], "conflicts": ["tukui"]},
    {"id": "ace3", "name": "Ace3"},
    {"id": "bigwigs", "name": "BigWigs", "depends": ["ace3", "littlewigs"]},
    {"id": "littlewigs", "name": "LittleWigs"},
    {"id": "tukui", "name": "TukUI"},
    {"id": "deadlybossmods", "name": "DBM", "conflicts": ["bigwigs"]},
]


def _use_catalog(monkeypatch, installed=None):
    monkeypatch.setattr(orch, "ADDON_CATALOG", _CATALOG, raising=False)
    monkeypatch.setattr(orch, "load_installed", lambda: dict(installed or {}))


# ── dependency_preview ───────────────────────────────────────────────

def test_dependency_preview_lists_full_transitive_set(monkeypatch):
    _use_catalog(monkeypatch)
    out = orch.dependency_preview(_CATALOG[2])  # bigwigs
    ids = [d["id"] for d in out["deps"]]
    assert set(ids) == {"ace3", "littlewigs"}
    assert out["missing"] == []
    assert all(d["installed"] is False for d in out["deps"])


def test_dependency_preview_flags_installed(monkeypatch):
    _use_catalog(monkeypatch, installed={"ace3": {"version": "1.0"}})
    out = orch.dependency_preview(_CATALOG[0])  # elvui → ace3
    assert out["deps"] == [{"id": "ace3", "name": "Ace3", "installed": True}]


def test_dependency_preview_reports_missing(monkeypatch):
    _use_catalog(monkeypatch)
    out = orch.dependency_preview({"id": "x", "name": "X", "depends": ["nope"]})
    assert out["deps"] == []
    assert out["missing"] == ["nope"]


# ── conflict_check ───────────────────────────────────────────────────

def test_conflict_check_forward(monkeypatch):
    # elvui declares conflict with tukui; tukui is installed.
    _use_catalog(monkeypatch, installed={"tukui": {"name": "TukUI"}})
    out = orch.conflict_check(_CATALOG[0])  # elvui
    assert out["conflicts"] == [{"id": "tukui", "name": "TukUI"}]


def test_conflict_check_reverse(monkeypatch):
    # bigwigs does not declare DBM, but DBM declares bigwigs → reverse match.
    _use_catalog(monkeypatch, installed={"deadlybossmods": {"name": "DBM"}})
    out = orch.conflict_check(_CATALOG[2])  # bigwigs
    assert out["conflicts"] == [{"id": "deadlybossmods", "name": "DBM"}]


def test_conflict_check_none_when_not_installed(monkeypatch):
    _use_catalog(monkeypatch, installed={})
    out = orch.conflict_check(_CATALOG[0])  # elvui, nothing installed
    assert out["conflicts"] == []


def test_conflict_check_ignores_non_conflicting(monkeypatch):
    _use_catalog(monkeypatch, installed={"ace3": {"name": "Ace3"}})
    out = orch.conflict_check(_CATALOG[0])  # elvui ← ace3 is a dep, not a conflict
    assert out["conflicts"] == []


def test_conflict_check_no_self_conflict(monkeypatch):
    _use_catalog(monkeypatch, installed={"elvui": {"name": "ElvUI"}})
    out = orch.conflict_check(_CATALOG[0])  # elvui installed, checking elvui
    assert out["conflicts"] == []


# ── guess_catalog_match ──────────────────────────────────────────────

def test_guess_catalog_match_by_name(monkeypatch):
    _use_catalog(monkeypatch)
    g = orch.guess_catalog_match("/home/u/Downloads/ElvUI-13.5.zip")
    assert g == {"id": "elvui", "name": "ElvUI"}


def test_guess_catalog_match_prefers_longest(monkeypatch):
    _use_catalog(monkeypatch)
    # "littlewigs" contains "wigs"/"bigwigs"? ensure exact longest wins.
    g = orch.guess_catalog_match("LittleWigs_v90.zip")
    assert g["id"] == "littlewigs"


def test_guess_catalog_match_none_when_no_match(monkeypatch):
    _use_catalog(monkeypatch)
    assert orch.guess_catalog_match("totally-unrelated-file.zip") is None


def test_scan_download_zips_annotated_shape(monkeypatch):
    _use_catalog(monkeypatch)
    monkeypatch.setattr(orch, "scan_download_zips", lambda limit=25: ["/d/ElvUI.zip"])
    monkeypatch.setattr(orch.os.path, "getmtime", lambda p: 123.0)
    items = orch.scan_download_zips_annotated()
    assert items == [{
        "path": "/d/ElvUI.zip", "name": "ElvUI.zip", "mtime": 123.0,
        "guess": {"id": "elvui", "name": "ElvUI"},
    }]
