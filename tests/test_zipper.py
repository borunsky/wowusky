"""Tests for smart_extract: GitHub wrapper detection and plain layouts."""

import os
import zipfile
from pathlib import Path

import pytest

from wowusky.core.zipper import sha256_of_file, smart_extract


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
