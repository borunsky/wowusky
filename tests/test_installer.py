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


# --- append_version_history ---


def test_append_version_history_no_previous():
    from wowusky.core.installer import append_version_history
    entry = {"name": "Foo", "version": "1.0"}
    result = append_version_history(entry)
    assert result["history"] == []


def test_append_version_history_records_previous():
    from wowusky.core.installer import append_version_history
    prev = {"version": "1.0", "source": "github", "folders": ["Foo"], "sha256": "abc"}
    new_entry = {"name": "Foo", "version": "2.0"}
    result = append_version_history(new_entry, prev, backup_path="/some/backup.zip", action="install")
    assert len(result["history"]) == 1
    h = result["history"][0]
    assert h["version"] == "1.0"
    assert h["backup"] == "/some/backup.zip"
    assert h["action"] == "install"


def test_append_version_history_bounded_at_50():
    from wowusky.core.installer import append_version_history
    prev = {"version": "old", "source": "x", "folders": [], "sha256": None,
            "history": [{"version": str(i)} for i in range(55)]}
    new_entry = {"name": "Foo", "version": "new"}
    result = append_version_history(new_entry, prev)
    assert len(result["history"]) == 50


# --- install_addon (core) ---


def test_core_install_addon_invalid_path():
    from wowusky.core.installer import install_addon
    logs = []
    ok = install_addon(
        {"name": "Foo", "source": "github", "id": "foo", "folders": []},
        "/nonexistent/path",
        profile_id="p1",
        get_latest_version=lambda a: "1.0",
        get_download_url=lambda a: "http://x",
        load_installed=lambda: {},
        save_installed=lambda d: None,
        backup_addon_folders=lambda *a, **kw: None,
        http_download=lambda *a, **kw: None,
        log=logs.append,
    )
    assert ok is False
    assert any("invalid" in m for m in logs)


def test_core_install_addon_dry_run(tmp_path):
    from wowusky.core.installer import install_addon
    addons = tmp_path / "AddOns"
    addons.mkdir()
    logs = []
    ok = install_addon(
        {"name": "Foo", "source": "github", "id": "foo", "folders": []},
        addons,
        profile_id="p1",
        get_latest_version=lambda a: "2.0",
        get_download_url=lambda a: "http://x",
        load_installed=lambda: {},
        save_installed=lambda d: (_ for _ in ()).throw(AssertionError("must not save in dry-run")),
        backup_addon_folders=lambda *a, **kw: None,
        http_download=lambda *a, **kw: (_ for _ in ()).throw(AssertionError("must not download in dry-run")),
        is_dry_run=lambda: True,
        log=logs.append,
    )
    assert ok is True
    assert any("dry-run" in m for m in logs)


def test_core_install_addon_no_url_no_page(tmp_path):
    from wowusky.core.installer import install_addon
    addons = tmp_path / "AddOns"
    addons.mkdir()
    logs = []
    ok = install_addon(
        {"name": "Foo", "source": "github", "id": "foo", "folders": []},
        addons,
        profile_id="p1",
        get_latest_version=lambda a: "2.0",
        get_download_url=lambda a: None,
        load_installed=lambda: {},
        save_installed=lambda d: None,
        backup_addon_folders=lambda *a, **kw: None,
        http_download=lambda *a, **kw: None,
        addon_provider_page=lambda a: None,
        log=logs.append,
    )
    assert ok is False
    assert any("no download url" in m for m in logs)


def test_core_install_addon_success(tmp_path):
    """Happy path: fake download writes a real ZIP, entry ends up in installed."""
    import zipfile as _zf

    from wowusky.core.installer import install_addon

    addons = tmp_path / "AddOns"
    addons.mkdir()

    # pre-build the ZIP the fake downloader will "place"
    real_zip = tmp_path / "fake.zip"
    with _zf.ZipFile(real_zip, "w") as z:
        z.writestr("Cool/Cool.toc", "## Title: Cool\n## Version: 3.0\n")

    saved: dict = {}

    def fake_download(url, dest, **_kw):
        import shutil
        shutil.copy(real_zip, dest)

    ok = install_addon(
        {"name": "Cool", "source": "github", "id": "cool", "folders": []},
        addons,
        profile_id="p1",
        get_latest_version=lambda a: "3.0",
        get_download_url=lambda a: "http://fake/cool.zip",
        load_installed=lambda: dict(saved),
        save_installed=saved.update,
        backup_addon_folders=lambda *a, **kw: None,
        http_download=fake_download,
        log=lambda m: None,
    )
    assert ok is True
    assert "cool" in saved
    assert saved["cool"]["version"] == "3.0"
    assert (addons / "Cool" / "Cool.toc").exists()


# --- uninstall_addon (core) ---


def test_core_uninstall_addon_not_installed(tmp_path):
    from wowusky.core.installer import uninstall_addon
    ok = uninstall_addon(
        "missing_id", tmp_path,
        load_installed=lambda: {},
        save_installed=lambda d: None,
        backup_addon_folders=lambda *a, **kw: None,
    )
    assert ok is False


def test_core_uninstall_addon_removes_folders(tmp_path):
    from wowusky.core.installer import uninstall_addon

    addons = tmp_path / "AddOns"
    addons.mkdir()
    (addons / "MyAddon").mkdir()
    (addons / "MyAddon" / "MyAddon.toc").write_text("## Version: 1\n")

    db = {"my_addon": {"name": "MyAddon", "version": "1.0", "folders": ["MyAddon"]}}
    saved: dict = {}

    ok = uninstall_addon(
        "my_addon", addons,
        load_installed=lambda: dict(db),
        save_installed=saved.update,
        backup_addon_folders=lambda *a, **kw: None,
        log=lambda m: None,
    )
    assert ok is True
    assert "my_addon" not in saved
    assert not (addons / "MyAddon").exists()
