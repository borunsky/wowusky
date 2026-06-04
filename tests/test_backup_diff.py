"""Tests for backup diff (#45) — wowusky.core.backup.diff_backups."""

from __future__ import annotations

import zipfile

import pytest

from wowusky.core import backup


def _make_zip(path, files: dict[str, bytes], meta: bool = False):
    with zipfile.ZipFile(path, "w") as zf:
        if meta:
            zf.writestr("wowusky-addon-backup.json", b"{}")
        for name, content in files.items():
            zf.writestr(name, content)


def test_diff_identical_is_empty(tmp_path):
    a = tmp_path / "a.zip"
    b = tmp_path / "b.zip"
    _make_zip(a, {"ElvUI/core.lua": b"hello"})
    _make_zip(b, {"ElvUI/core.lua": b"hello"})
    d = backup.diff_backups(str(a), str(b))
    assert d == {"added": [], "removed": [], "changed": []}


def test_diff_added_file(tmp_path):
    a = tmp_path / "a.zip"
    b = tmp_path / "b.zip"
    _make_zip(a, {"ElvUI/core.lua": b"x"})
    _make_zip(b, {"ElvUI/core.lua": b"x", "ElvUI/new.lua": b"y"})
    d = backup.diff_backups(str(a), str(b))
    assert d["added"] == ["ElvUI/new.lua"]
    assert d["removed"] == []
    assert d["changed"] == []


def test_diff_removed_file(tmp_path):
    a = tmp_path / "a.zip"
    b = tmp_path / "b.zip"
    _make_zip(a, {"ElvUI/core.lua": b"x", "ElvUI/old.lua": b"z"})
    _make_zip(b, {"ElvUI/core.lua": b"x"})
    d = backup.diff_backups(str(a), str(b))
    assert d["removed"] == ["ElvUI/old.lua"]
    assert d["added"] == []


def test_diff_changed_size(tmp_path):
    a = tmp_path / "a.zip"
    b = tmp_path / "b.zip"
    _make_zip(a, {"ElvUI/core.lua": b"short"})
    _make_zip(b, {"ElvUI/core.lua": b"a much longer content here"})
    d = backup.diff_backups(str(a), str(b))
    assert d["changed"] == [{"path": "ElvUI/core.lua", "size_a": 5, "size_b": 26}]


def test_diff_skips_meta_files(tmp_path):
    a = tmp_path / "a.zip"
    b = tmp_path / "b.zip"
    _make_zip(a, {"ElvUI/core.lua": b"x"}, meta=True)
    _make_zip(b, {"ElvUI/core.lua": b"x"}, meta=True)
    d = backup.diff_backups(str(a), str(b))
    assert d == {"added": [], "removed": [], "changed": []}


def test_diff_missing_file_raises(tmp_path):
    a = tmp_path / "a.zip"
    _make_zip(a, {"x": b"1"})
    with pytest.raises(RuntimeError):
        backup.diff_backups(str(a), str(tmp_path / "missing.zip"))
