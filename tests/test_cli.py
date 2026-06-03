"""Tests for wowusky.cli — CLI surface."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, call

from wowusky.cli import build_parser, run_cli


# ---------------------------------------------------------------------------
# Parser smoke tests
# ---------------------------------------------------------------------------

def test_install_parses_ids():
    p = build_parser()
    args = p.parse_args(["install", "elvui", "bigwigs"])
    assert args.command == "install"
    assert args.addon_id == ["elvui", "bigwigs"]
    assert not args.dry_run
    assert not args.no_deps


def test_install_dry_run_flag():
    p = build_parser()
    args = p.parse_args(["install", "-n", "elvui"])
    assert args.dry_run


def test_install_no_deps_flag():
    p = build_parser()
    args = p.parse_args(["install", "--no-deps", "elvui"])
    assert args.no_deps


def test_update_no_ids_means_all():
    p = build_parser()
    args = p.parse_args(["update"])
    assert args.addon_id == []


def test_update_dry_run():
    p = build_parser()
    args = p.parse_args(["update", "-n", "elvui"])
    assert args.dry_run
    assert args.addon_id == ["elvui"]


def test_search_parses_query():
    p = build_parser()
    args = p.parse_args(["search", "raid"])
    assert args.query == "raid"


def test_set_curseforge_key():
    p = build_parser()
    args = p.parse_args(["set", "curseforge-key", "abc123"])
    assert args.setting == "curseforge-key"
    assert args.value == "abc123"


def test_set_curseforge_key_no_value_defaults_empty():
    p = build_parser()
    args = p.parse_args(["set", "curseforge-key"])
    assert args.value == ""


def test_profile_list_subcommand():
    p = build_parser()
    args = p.parse_args(["profile", "list"])
    assert args.command == "profile"
    assert args.profile_cmd == "list"


def test_profile_switch_subcommand():
    p = build_parser()
    args = p.parse_args(["profile", "switch", "retail"])
    assert args.name == "retail"


# ---------------------------------------------------------------------------
# cmd_version
# ---------------------------------------------------------------------------

def test_cmd_version(capsys):
    run_cli(["version"])
    out = capsys.readouterr().out
    assert "wowusky" in out


# ---------------------------------------------------------------------------
# cmd_search
# ---------------------------------------------------------------------------

FAKE_CATALOG = [
    {"id": "bigwigs", "name": "BigWigs", "provider": "github", "description": "Raid boss timers", "flavors": ["all"], "folders": [], "category": "Raid", "author": "", "depends": []},
    {"id": "elvui", "name": "ElvUI", "provider": "tukui", "description": "Full UI replacement", "flavors": ["all"], "folders": [], "category": "Interface", "author": "", "depends": []},
]


def test_search_matches_name(capsys):
    with patch("wowusky.cli._catalog", return_value=FAKE_CATALOG):
        run_cli(["search", "bigwigs"])
    out = capsys.readouterr().out
    assert "bigwigs" in out
    assert "elvui" not in out


def test_search_no_results(capsys):
    with patch("wowusky.cli._catalog", return_value=FAKE_CATALOG):
        run_cli(["search", "xyznotfound"])
    out = capsys.readouterr().out
    assert "No results" in out


# ---------------------------------------------------------------------------
# cmd_install
# ---------------------------------------------------------------------------

def test_install_not_in_catalog(capsys):
    with patch("wowusky.cli._addons_path", return_value="/fake/AddOns"), \
         patch("wowusky.orchestrator.find_addon_by_id", return_value=None):
        run_cli(["install", "doesnotexist"])
    out = capsys.readouterr().out
    assert "not found in catalog" in out


def test_install_dry_run_does_not_call_install(capsys):
    fake_addon = FAKE_CATALOG[0]
    with patch("wowusky.cli._addons_path", return_value="/fake/AddOns"), \
         patch("wowusky.orchestrator.find_addon_by_id", return_value=fake_addon), \
         patch("wowusky.orchestrator.install_addon") as mock_install:
        run_cli(["install", "-n", "bigwigs"])
    mock_install.assert_not_called()
    out = capsys.readouterr().out
    assert "dry-run" in out


# ---------------------------------------------------------------------------
# cmd_orphans
# ---------------------------------------------------------------------------

def test_orphans_none(capsys):
    with patch("wowusky.cli._installed", return_value={"bigwigs": {"name": "BigWigs"}}), \
         patch("wowusky.orchestrator.find_addon_by_id", return_value=FAKE_CATALOG[0]):
        run_cli(["orphans"])
    out = capsys.readouterr().out
    assert "No orphaned" in out


def test_orphans_found(capsys):
    with patch("wowusky.cli._installed", return_value={"mystery-addon": {"name": "Mystery"}}), \
         patch("wowusky.orchestrator.find_addon_by_id", return_value=None):
        run_cli(["orphans"])
    out = capsys.readouterr().out
    assert "mystery-addon" in out


# ---------------------------------------------------------------------------
# cmd_set
# ---------------------------------------------------------------------------

def test_set_curseforge_key_saves(capsys):
    with patch("wowusky.core.state.set_curseforge_api_key") as mock_set:
        run_cli(["set", "curseforge-key", "MYKEY"])
    mock_set.assert_called_once_with("MYKEY")
    out = capsys.readouterr().out
    assert "saved" in out


def test_set_curseforge_key_empty_clears(capsys):
    with patch("wowusky.core.state.set_curseforge_api_key") as mock_set:
        run_cli(["set", "curseforge-key"])
    mock_set.assert_called_once_with("")
    out = capsys.readouterr().out
    assert "removed" in out
