"""Tests for smart_extract: GitHub wrapper detection and plain layouts."""

import os
import zipfile
from pathlib import Path

import pytest

from wowusky.core.zipper import extract_addon_zip, sha256_file, sha256_of_file, smart_extract


def _make_zip(zip_path: Path, files: dict[str, str]) -> None:
    """Helper: build a ZIP from a {arcname: content} dict."""
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)


def test_extract_github_wrapper_with_inner_addon(tmp_path):
    """A typical 'Source code.zip' wraps the addon in <repo>-<branch>/.

    The wrapper itself doesn't contain a .toc — instead it holds one or
    more addon folders. Those inner folders are the real addons.
    """
    zip_path = tmp_path / "release.zip"
    _make_zip(zip_path, {
        "WeakAuras2-5.18.0/WeakAuras/WeakAuras.toc": "## Version: 5.18.0\n",
        "WeakAuras2-5.18.0/WeakAuras/init.lua":      "-- init",
        "WeakAuras2-5.18.0/WeakAurasOptions/WeakAurasOptions.toc":
                                                      "## Version: 5.18.0\n",
    })
    addons = tmp_path / "AddOns"
    addons.mkdir()
    placed = smart_extract(zip_path, addons)
    assert sorted(placed) == ["WeakAuras", "WeakAurasOptions"]
    assert (addons / "WeakAuras" / "WeakAuras.toc").exists()
    # Wrapper directory must NOT end up in AddOns
    assert not (addons / "WeakAuras2-5.18.0").exists()


def test_extract_wrapper_is_the_addon_itself(tmp_path):
    """Some archives have the wrapper *be* the addon — TOC sits directly
    inside the wrapper. We should rename it to the preferred target.
    """
    zip_path = tmp_path / "elvui.zip"
    _make_zip(zip_path, {
        "ElvUI-15.13/ElvUI.toc":     "## Version: 15.13\n",
        "ElvUI-15.13/core/foo.lua":  "-- foo",
    })
    addons = tmp_path / "AddOns"
    addons.mkdir()
    placed = smart_extract(zip_path, addons, preferred_target_name="ElvUI")
    assert placed == ["ElvUI"]
    assert (addons / "ElvUI" / "ElvUI.toc").exists()
    assert (addons / "ElvUI" / "core" / "foo.lua").exists()
    assert not (addons / "ElvUI-15.13").exists()


def test_extract_plain_layout_top_dirs_are_addons(tmp_path):
    """Archive without any wrapper — each top-level dir is an addon."""
    zip_path = tmp_path / "plain.zip"
    _make_zip(zip_path, {
        "AddonA/AddonA.toc": "## Version: 1\n",
        "AddonB/AddonB.toc": "## Version: 1\n",
    })
    addons = tmp_path / "AddOns"
    addons.mkdir()
    placed = smart_extract(zip_path, addons)
    assert sorted(placed) == ["AddonA", "AddonB"]


def test_extract_overwrites_existing_folder(tmp_path):
    """Existing addon directory should be replaced cleanly."""
    addons = tmp_path / "AddOns"
    addons.mkdir()
    old = addons / "Foo"
    old.mkdir()
    (old / "stale.lua").write_text("old content")

    zip_path = tmp_path / "new.zip"
    _make_zip(zip_path, {"Foo/Foo.toc": "## Version: 2\n"})

    placed = smart_extract(zip_path, addons)
    assert placed == ["Foo"]
    assert (addons / "Foo" / "Foo.toc").exists()
    assert not (addons / "Foo" / "stale.lua").exists()


def test_sha256_of_file_matches_known_hash(tmp_path):
    p = tmp_path / "x.bin"
    p.write_bytes(b"hello")
    # echo -n "hello" | sha256sum  →  2cf24dba...
    assert sha256_of_file(p) == \
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_sha256_file_alias_matches(tmp_path):
    """sha256_file is the GUI-facing alias and must behave identically."""
    p = tmp_path / "x.bin"
    p.write_bytes(b"hello")
    assert sha256_file(p) == sha256_of_file(p)


# --- extract_addon_zip: canonical recursive extractor (GUI install path) ---


def test_extract_addon_zip_recurses_release_subdir(tmp_path):
    """CurseForge-style packages bury the addon under a release/ subdir.

    The recursive extractor must still find the TOC folder and place it
    directly under AddOns — not the wrapper or the release/ dir.
    """
    zip_path = tmp_path / "cf.zip"
    _make_zip(zip_path, {
        "MyAddon-1.0/release/MyAddon/MyAddon.toc": "## Version: 1.0\n",
        "MyAddon-1.0/release/MyAddon/core.lua":    "-- core",
    })
    addons = tmp_path / "AddOns"
    addons.mkdir()
    placed = extract_addon_zip(zip_path, addons)
    assert placed == ["MyAddon"]
    assert (addons / "MyAddon" / "MyAddon.toc").exists()
    assert not (addons / "MyAddon-1.0").exists()


def test_extract_addon_zip_drops_nested_library_folders(tmp_path):
    """A library folder nested inside an addon that already has a TOC
    must not be copied out as its own addon."""
    zip_path = tmp_path / "nested.zip"
    _make_zip(zip_path, {
        "Big/Big.toc":              "## Version: 1\n",
        "Big/Libs/LibStub/LibStub.toc": "## Version: 1\n",
    })
    addons = tmp_path / "AddOns"
    addons.mkdir()
    placed = extract_addon_zip(zip_path, addons)
    assert placed == ["Big"]
    assert not (addons / "LibStub").exists()


def test_extract_addon_zip_raises_when_no_addon(tmp_path):
    zip_path = tmp_path / "empty.zip"
    _make_zip(zip_path, {"readme.txt": "nothing here"})
    addons = tmp_path / "AddOns"
    addons.mkdir()
    with pytest.raises(RuntimeError):
        extract_addon_zip(zip_path, addons)
