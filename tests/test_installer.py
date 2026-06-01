"""Tests for wowusky.core.installer — ZIP-import entry building."""

import zipfile
from pathlib import Path

import pytest

from wowusky.core.installer import build_import_entry, guess_addon_name_from_zip


def _make_zip(zip_path: Path, files: dict[str, str]) -> None:
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)


def test_guess_name_prefers_shortest_toc_dir(tmp_path):
    zip_path = tmp_path / "WeakAuras-5.18.0.zip"
    _make_zip(zip_path, {
        "WeakAuras/WeakAuras.toc": "## Version: 5.18.0\n",
        "WeakAurasOptions/WeakAurasOptions.toc": "## Version: 5.18.0\n",
    })
    assert guess_addon_name_from_zip(zip_path) == "WeakAuras"


def test_guess_name_falls_back_to_filename(tmp_path):
    zip_path = tmp_path / "SomeAddon-v1.2.3.zip"
    _make_zip(zip_path, {"readme.txt": "no toc here"})
    assert guess_addon_name_from_zip(zip_path) == "SomeAddon"


def test_build_import_entry_reads_toc(tmp_path):
    zip_path = tmp_path / "addon.zip"
    _make_zip(zip_path, {
        "Cool/Cool.toc": "## Title: Cool Addon\n## Version: 2.4\n## Interface: 110000\n",
    })
    addons = tmp_path / "AddOns"
    addons.mkdir()
    addon_id, entry = build_import_entry(zip_path, addons, log=lambda *_: None)
    # id derives from the guessed folder name ("Cool"); title comes from the TOC.
    assert addon_id == "manual_cool"
    assert entry["name"] == "Cool Addon"
    assert entry["version"] == "2.4"
    assert entry["interface"] == 110000
    assert entry["folders"] == ["Cool"]
    assert entry["source"] == "manual"
    assert (addons / "Cool" / "Cool.toc").exists()


def test_build_import_entry_curseforge_slug_sets_source_and_url(tmp_path):
    zip_path = tmp_path / "addon.zip"
    _make_zip(zip_path, {"Foo/Foo.toc": "## Version: 1\n"})
    addons = tmp_path / "AddOns"
    addons.mkdir()
    _id, entry = build_import_entry(
        zip_path, addons, name="Foo", curseforge_slug="foo-addon", log=lambda *_: None,
    )
    assert entry["source"] == "curseforge_manual"
    assert entry["curseforge_slug"] == "foo-addon"
    assert entry["url"] == "https://www.curseforge.com/wow/addons/foo-addon"


def test_build_import_entry_missing_zip_raises(tmp_path):
    addons = tmp_path / "AddOns"
    addons.mkdir()
    with pytest.raises(RuntimeError, match="ZIP file not found"):
        build_import_entry(tmp_path / "nope.zip", addons, log=lambda *_: None)


def test_build_import_entry_bad_addons_path_raises(tmp_path):
    zip_path = tmp_path / "addon.zip"
    _make_zip(zip_path, {"Foo/Foo.toc": "## Version: 1\n"})
    with pytest.raises(RuntimeError, match="AddOns path not configured"):
        build_import_entry(zip_path, tmp_path / "missing", log=lambda *_: None)
