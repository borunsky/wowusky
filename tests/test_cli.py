"""Tests for wowusky.cli — CLI surface."""

from __future__ import annotations

from unittest.mock import ANY, MagicMock, call, patch

import pytest

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
# cmd_help
# ---------------------------------------------------------------------------

def test_help_lists_all_commands(capsys):
    run_cli(["help"])
    out = capsys.readouterr().out
    for cmd in ("install", "uninstall", "update", "status", "search",
                "orphans", "import", "profile", "set", "version"):
        assert cmd in out


def test_help_topic_install(capsys):
    run_cli(["help", "install"])
    out = capsys.readouterr().out
    assert "Usage:" in out
    assert "--dry-run" in out
    assert "Examples:" in out


def test_help_topic_set(capsys):
    run_cli(["help", "set"])
    out = capsys.readouterr().out
    assert "curseforge-key" in out
    assert "Examples:" in out


def test_help_unknown_topic(capsys):
    run_cli(["help", "doesnotexist"])
    out = capsys.readouterr().out
    assert "Unknown command" in out
    assert "install" in out  # still shows full help


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


# ---------------------------------------------------------------------------
# backup
# ---------------------------------------------------------------------------

def test_backup_parses_subcommands():
    p = build_parser()
    assert p.parse_args(["backup", "create"]).backup_cmd == "create"
    assert p.parse_args(["backup", "list"]).backup_cmd == "list"
    args = p.parse_args(["backup", "restore", "0"])
    assert args.backup_cmd == "restore"
    assert args.backup == "0"


def test_backup_list_empty(capsys):
    with patch("wowusky.core.backup.list_full_backups", return_value=[]):
        run_cli(["backup", "list", "--no-backup"])
    out = capsys.readouterr().out
    assert "No full backups" in out


def test_backup_list_shows_index(capsys):
    fake = [{"path": "/b/x.zip", "name": "x.zip", "mtime": 1_700_000_000, "size": 2048}]
    with patch("wowusky.core.backup.list_full_backups", return_value=fake):
        run_cli(["backup", "list", "--no-backup"])
    out = capsys.readouterr().out
    assert "[0]" in out and "x.zip" in out


def test_backup_create_calls_core(capsys):
    with patch("wowusky.cli._addons_path", return_value="/fake/AddOns"), \
         patch("wowusky.core.backup.create_full_backup", return_value="/b/new.zip") as mock_create:
        run_cli(["backup", "create", "--no-backup"])
    mock_create.assert_called_once()
    assert "new.zip" in capsys.readouterr().out


def test_backup_restore_resolves_index(capsys):
    fake = [{"path": "/b/new.zip", "name": "new.zip", "mtime": 1, "size": 1}]
    with patch("wowusky.cli._addons_path", return_value="/fake/AddOns"), \
         patch("wowusky.core.backup.list_full_backups", return_value=fake), \
         patch("wowusky.core.backup.restore_full_backup", return_value=True) as mock_restore:
        run_cli(["backup", "restore", "0", "--no-backup"])
    mock_restore.assert_called_once_with("/b/new.zip", log=ANY)


def test_backup_restore_unknown_selector_exits():
    with patch("wowusky.cli._addons_path", return_value="/fake/AddOns"), \
         patch("wowusky.core.backup.list_full_backups", return_value=[]):
        with pytest.raises(SystemExit):
            run_cli(["backup", "restore", "99", "--no-backup"])


# ---------------------------------------------------------------------------
# rollback
# ---------------------------------------------------------------------------

def test_rollback_list_flag_lists(capsys):
    fake = [{"path": "/b/elvui-1.zip", "name": "elvui-1.zip", "mtime": 1, "size": 10, "version": "13.0"}]
    with patch("wowusky.core.backup.list_addon_backups", return_value=fake):
        run_cli(["rollback", "elvui", "--list", "--no-backup"])
    out = capsys.readouterr().out
    assert "elvui-1.zip" in out and "[0]" in out


def test_rollback_default_restores_latest():
    with patch("wowusky.cli._addons_path", return_value="/fake/AddOns"), \
         patch("wowusky.core.backup.rollback_addon", return_value=True) as mock_rb:
        run_cli(["rollback", "elvui", "--no-backup"])
    mock_rb.assert_called_once()
    assert mock_rb.call_args[0][0] == "elvui"


def test_rollback_specific_backup():
    fake = [{"path": "/b/a.zip", "name": "a.zip", "mtime": 1, "size": 1, "version": "1"},
            {"path": "/b/b.zip", "name": "b.zip", "mtime": 0, "size": 1, "version": "1"}]
    with patch("wowusky.cli._addons_path", return_value="/fake/AddOns"), \
         patch("wowusky.core.backup.list_addon_backups", return_value=fake), \
         patch("wowusky.core.backup.rollback_addon_to_backup", return_value=True) as mock_rb:
        run_cli(["rollback", "elvui", "1", "--no-backup"])
    mock_rb.assert_called_once_with("elvui", "/b/b.zip", "/fake/AddOns", log=ANY)


# ---------------------------------------------------------------------------
# weakauras
# ---------------------------------------------------------------------------

def test_weakauras_list_empty(capsys):
    with patch("wowusky.core.state.load_wago", return_value={"auras": {}}):
        run_cli(["weakauras", "list", "--no-backup"])
    assert "No tracked WeakAuras" in capsys.readouterr().out


def test_weakauras_list_shows_auras(capsys):
    auras = {"auras": {"abc": {"name": "MyAura", "version": 3, "latest_version": 4}}}
    with patch("wowusky.core.state.load_wago", return_value=auras):
        run_cli(["weakauras", "list", "--no-backup"])
    out = capsys.readouterr().out
    assert "MyAura" in out and "↑" in out


def test_weakauras_add_calls_core(capsys):
    with patch("wowusky.core.wago.wago_add", return_value={"name": "X", "version": 1}) as mock_add:
        run_cli(["weakauras", "add", "abc123", "--no-backup"])
    mock_add.assert_called_once()
    assert "tracking" in capsys.readouterr().out


def test_weakauras_remove_not_tracked(capsys):
    with patch("wowusky.core.wago.wago_remove", return_value=False):
        run_cli(["weakauras", "remove", "nope", "--no-backup"])
    assert "not tracked" in capsys.readouterr().out


def test_wa_alias_normalises_to_weakauras():
    p = build_parser()
    args = p.parse_args(["wa", "list"])
    assert args.command == "wa"  # raw
    # run_cli normalises; verify dispatch works without error
    with patch("wowusky.core.state.load_wago", return_value={"auras": {}}):
        run_cli(["wa", "list", "--no-backup"])


# ---------------------------------------------------------------------------
# auto-backup
# ---------------------------------------------------------------------------

def test_no_backup_flag_skips_autobackup():
    with patch("wowusky.cli._addons_path", return_value="/fake/AddOns"), \
         patch("wowusky.orchestrator.find_addon_by_id", return_value=None), \
         patch("wowusky.core.backup.create_full_backup") as mock_bk:
        run_cli(["install", "x", "--no-backup"])
    mock_bk.assert_not_called()


def test_autobackup_runs_before_install():
    with patch("wowusky.cli._addons_path", return_value="/fake/AddOns"), \
         patch("wowusky.core.state.get_addons_path", return_value="/fake/AddOns"), \
         patch("wowusky.orchestrator.find_addon_by_id", return_value=None), \
         patch("wowusky.core.backup.create_full_backup", return_value="/b/x.zip") as mock_bk:
        run_cli(["install", "x"])
    mock_bk.assert_called_once()


def test_autobackup_skipped_for_search():
    with patch("wowusky.cli._catalog", return_value=[]), \
         patch("wowusky.core.backup.create_full_backup") as mock_bk:
        run_cli(["search", "raid"])
    mock_bk.assert_not_called()


def test_autobackup_skipped_for_status():
    with patch("wowusky.cli._installed", return_value={}), \
         patch("wowusky.core.backup.create_full_backup") as mock_bk:
        run_cli(["status"])
    mock_bk.assert_not_called()
