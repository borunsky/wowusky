"""Tests for the backup / rollback system."""

import importlib
import os
import sys
import zipfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    for name in ("wowusky.core.paths", "wowusky.core.backup"):
        if name in sys.modules:
            importlib.reload(sys.modules[name])
    yield


def _populate_addon(addons: Path, name: str, marker: str) -> None:
    folder = addons / name
    folder.mkdir(parents=True)
    (folder / f"{name}.toc").write_text(f"## Version: {marker}\n")
    (folder / "core.lua").write_text(f"-- {marker}")


def test_make_backup_returns_none_when_no_folders_on_disk(tmp_path):
    from wowusky.core import backup
    addons = tmp_path / "AddOns"
    addons.mkdir()
    assert backup.make_backup("p1", "ghost", str(addons), ["NonExistent"]) is None


def test_make_backup_creates_archive_with_addon_contents(tmp_path):
    from wowusky.core import backup
    addons = tmp_path / "AddOns"
    addons.mkdir()
    _populate_addon(addons, "ElvUI", "15.13")
    _populate_addon(addons, "ElvUI_Options", "15.13")

    b = backup.make_backup("p1", "elvui", str(addons),
                           ["ElvUI", "ElvUI_Options"], version_tag="15.13")
    assert b is not None
    assert b.path.exists()

    with zipfile.ZipFile(b.path) as zf:
        names = zf.namelist()
    assert any("ElvUI/ElvUI.toc" in n for n in names)
    assert any("ElvUI_Options/ElvUI_Options.toc" in n for n in names)


def test_pruning_keeps_only_max_backups(tmp_path, monkeypatch):
    from wowusky.core import backup
    monkeypatch.setattr(backup, "MAX_BACKUPS_PER_ADDON", 3)
    addons = tmp_path / "AddOns"
    addons.mkdir()
    _populate_addon(addons, "Foo", "1")

    # create 5 backups with strictly increasing mtimes so the prune step
    # has a deterministic "newest 3 to keep" ordering.
    import time
    created = []
    for i in range(5):
        b = backup.make_backup("p1", "foo", str(addons), ["Foo"], version_tag=f"v{i}")
        assert b is not None
        # bump mtime so the next call's archive is strictly newer
        os.utime(b.path, (1000 + i, 1000 + i))
        created.append(b.path)

    backups = backup.list_backups("p1", "foo")
    assert len(backups) == 3, f"expected 3 after pruning, got {len(backups)}"


def test_list_backups_newest_first(tmp_path):
    import shutil

    from wowusky.core import backup
    addons = tmp_path / "AddOns"
    addons.mkdir()
    _populate_addon(addons, "Foo", "v1")

    b1 = backup.make_backup("p1", "foo", str(addons), ["Foo"], version_tag="v1")
    os.utime(b1.path, (1000, 1000))

    # replace addon content (don't recreate the folder)
    shutil.rmtree(addons / "Foo")
    _populate_addon(addons, "Foo", "v2")
    b2 = backup.make_backup("p1", "foo", str(addons), ["Foo"], version_tag="v2")
    os.utime(b2.path, (2000, 2000))

    backups = backup.list_backups("p1", "foo")
    assert backups[0].timestamp >= backups[-1].timestamp


def test_restore_replaces_current_addon_with_archived_one(tmp_path):
    from wowusky.core import backup
    addons = tmp_path / "AddOns"
    addons.mkdir()

    # Original content (will be backed up)
    _populate_addon(addons, "Foo", "v1")
    b = backup.make_backup("p1", "foo", str(addons), ["Foo"], version_tag="v1")
    assert b is not None

    # Simulate a bad update
    (addons / "Foo" / "core.lua").write_text("-- BROKEN")
    assert "BROKEN" in (addons / "Foo" / "core.lua").read_text()

    # Rollback
    placed = backup.restore(b, str(addons), ["Foo"])
    assert "Foo" in placed
    assert (addons / "Foo" / "core.lua").read_text() == "-- v1"


def test_list_backups_returns_empty_for_unknown_addon():
    from wowusky.core import backup
    assert backup.list_backups("p1", "never-installed") == []
