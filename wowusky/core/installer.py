"""Addon-install helpers — the I/O-light core of the install path.

The GUI orchestration (download, backup/rollback, profile-aware
``installed.json`` writes, dry-run guards) lives here via the
injectable :func:`install_addon` function. Callers supply a thin
set of service callbacks so the core logic can be unit-tested without
a Tk app or a live profile.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import time
import zipfile
from collections.abc import Callable
from pathlib import Path

from .toc import read_addon_toc, strip_color_codes
from .zipper import extract_addon_zip, sha256_file


def guess_addon_name_from_zip(zip_path: str | Path) -> str:
    """Best-effort display name for a ZIP with no caller-supplied name.

    Strips a trailing version suffix from the filename, then prefers the
    shortest TOC-folder name found inside the archive (color codes
    removed). Falls back to the cleaned filename.
    """
    base = os.path.splitext(os.path.basename(str(zip_path)))[0]
    base = re.sub(r'[-_]?v?\d+(\.\d+)*.*$', '', base).strip("-_ ") or base
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            toc_dirs = [
                n.split("/")[-2]
                for n in zf.namelist()
                if n.lower().endswith(".toc") and "/" in n
            ]
            if toc_dirs:
                toc_dirs.sort(key=len)
                return strip_color_codes(toc_dirs[0]) or base
    except Exception:
        pass
    return base


def build_import_entry(
    zip_path: str | Path,
    addons_path: str | Path,
    name: str | None = None,
    source: str = "manual",
    curseforge_slug: str | None = None,
    curseforge_url: str | None = None,
    log=print,
) -> tuple[str, dict]:
    """Extract *zip_path* into *addons_path* and build an ``installed`` entry.

    Returns ``(addon_id, entry)``. The caller is responsible for merging
    the entry into the profile's installed database and persisting it —
    this keeps profile/config I/O out of the core.

    Raises ``RuntimeError`` if the ZIP is missing or ``addons_path`` is
    not a configured directory.
    """
    zip_path = str(zip_path)
    addons_path = str(addons_path)
    if not zip_path or not os.path.isfile(zip_path):
        raise RuntimeError("ZIP file not found")
    if not addons_path or not os.path.isdir(addons_path):
        raise RuntimeError("WoW AddOns path not configured")

    display_name = (name or guess_addon_name_from_zip(zip_path)).strip() or "Imported Addon"
    addon_id = source + "_" + re.sub(r'[^a-z0-9]+', '_', display_name.lower()).strip("_")

    log(f"⟩ importing {display_name}")
    folders = extract_addon_zip(zip_path, addons_path)

    version = "imported"
    interface = None
    title = display_name
    if folders:
        toc = read_addon_toc(os.path.join(addons_path, folders[0]))
        if toc:
            version = toc.get("version") or version
            interface = toc.get("interface")
            title = toc.get("title") or title

    entry = {
        "name": title,
        "version": version,
        "folders": folders,
        "source": source,
        "interface": interface,
        "imported_from": zip_path,
    }
    if curseforge_slug:
        entry["curseforge_slug"] = curseforge_slug
        entry["url"] = curseforge_url or ("https://www.curseforge.com/wow/addons/" + curseforge_slug)
        entry["source"] = "curseforge_manual"
    elif curseforge_url:
        entry["url"] = curseforge_url

    log(f"  ✓ {title} ({version})\n")
    return addon_id, entry


# ---------------------------------------------------------------------------
# Version history (pure)
# ---------------------------------------------------------------------------

def append_version_history(
    new_entry: dict,
    previous_entry: dict | None = None,
    backup_path: str | None = None,
    action: str = "install",
) -> dict:
    """Prepend the previous entry to ``new_entry["history"]`` and return it.

    History is bounded to 50 entries so the installed DB doesn't grow
    unbounded over many update cycles.
    """
    history = []
    if previous_entry:
        history.extend(previous_entry.get("history", []))
        history.append({
            "version": previous_entry.get("version", "unknown"),
            "source":  previous_entry.get("source",  "unknown"),
            "folders": previous_entry.get("folders", []),
            "sha256":  previous_entry.get("sha256"),
            "backup":  backup_path,
            "action":  action,
            "time":    time.strftime("%Y-%m-%d %H:%M:%S"),
        })
    new_entry["history"] = history[-50:]
    return new_entry


# ---------------------------------------------------------------------------
# install_addon — full orchestration with injectable service callbacks
# ---------------------------------------------------------------------------

def install_addon(
    addon: dict,
    addons_path: str | Path,
    *,
    profile_id: str,
    get_latest_version: Callable[[dict], str | None],
    get_download_url: Callable[[dict], str | None],
    load_installed: Callable[[], dict],
    save_installed: Callable[[dict], None],
    backup_addon_folders: Callable[..., str | None],
    http_download: Callable[..., None],
    is_dry_run: Callable[[], bool] = lambda: False,
    app_log: Callable[[str], None] = lambda m: None,
    addon_provider_page: Callable[[dict], str | None] = lambda a: None,
    open_in_browser: Callable[[str], None] = lambda u: None,
    generate_wac_companion: Callable[[str], bool] = lambda p: False,
    log: Callable[[str], None] = print,
    progress=None,
) -> bool:
    """Download and install (or update) a single addon.

    All side-effectful operations are injected via keyword arguments so
    the function can be exercised in tests without a running GUI or live
    profile. Returns ``True`` on success, ``False`` on failure.
    """
    addons_path = str(addons_path)
    if not addons_path or not os.path.exists(addons_path):
        log(f"  path invalid: {addons_path}")
        return False

    # WeakAuras Companion is generated locally — no download needed.
    if addon.get("source") == "internal_wac":
        log(f"⟩ generating {addon['name']}")
        ok = generate_wac_companion(addons_path)
        if ok:
            log("  ✓ generated\n")
        return ok

    log(f"⟩ {addon['name']}")
    app_log(f"install requested: {addon.get('id')} {addon.get('name')} profile={profile_id}")

    latest = get_latest_version(addon)
    if not latest:
        latest = "manual"
        log("  latest: manual / provider page")
    else:
        log(f"  latest: {latest}")

    if is_dry_run():
        log("  dry-run: would download and install — no network or disk access")
        return True

    try:
        url = get_download_url(addon)
        if not url:
            page = addon_provider_page(addon)
            if page:
                log("  ↗ provider does not expose a direct ZIP; opening manual download page")
                open_in_browser(page)
                return False
            log("  ✗ no download url")
            return False
    except Exception as e:
        page = addon_provider_page(addon)
        if page:
            log(f"  ↗ direct download failed ({e}); opening provider page")
            open_in_browser(page)
            return False
        log(f"  ✗ url: {e}")
        return False

    log("  ↓ downloading")
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        http_download(url, tmp_path, progress=progress)
        file_hash = sha256_file(tmp_path)
        log(f"  done ({os.path.getsize(tmp_path) // 1024} KB)")

        installed_before = load_installed().get(addon["id"])
        backup_path = None
        if installed_before:
            backup_path = backup_addon_folders(addon["id"], installed_before, addons_path, log)

        log("  ◌ removing old")
        for folder in addon.get("folders", []):
            p = os.path.join(addons_path, folder)
            if os.path.exists(p):
                if is_dry_run():
                    log(f"  dry-run: would remove {folder}")
                else:
                    shutil.rmtree(p)

        log("  ▣ extracting")
        if is_dry_run():
            folders = addon.get("folders", [])
        else:
            folders = extract_addon_zip(tmp_path, addons_path)

        interface = None
        if folders:
            toc = read_addon_toc(os.path.join(addons_path, folders[0]))
            if toc:
                interface = toc.get("interface")

        installed = load_installed()
        new_entry = {
            "name":      addon["name"],
            "version":   latest,
            "folders":   folders or addon.get("folders", []),
            "source":    addon["source"],
            "interface": interface,
            "sha256":    file_hash,
            "profile":   profile_id,
        }
        installed[addon["id"]] = append_version_history(
            new_entry, installed_before, backup_path=backup_path, action="install"
        )
        if not is_dry_run():
            save_installed(installed)
        log(f"  ✓ {addon['name']} {latest}\n")
        app_log(f"install finished: {addon.get('id')} version={latest} sha256={file_hash[:12]}")
        return True
    except Exception as e:
        log(f"  ✗ {e}\n")
        return False
    finally:
        import contextlib
        with contextlib.suppress(Exception):
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# uninstall_addon — full orchestration with injectable service callbacks
# ---------------------------------------------------------------------------

def uninstall_addon(
    addon_id: str,
    addons_path: str | Path,
    *,
    load_installed: Callable[[], dict],
    save_installed: Callable[[dict], None],
    backup_addon_folders: Callable[..., str | None],
    is_dry_run: Callable[[], bool] = lambda: False,
    app_log: Callable[[str], None] = lambda m: None,
    profile_id: str = "",
    log: Callable[[str], None] = print,
) -> bool:
    """Remove an addon's folders and drop it from the installed database."""
    addons_path = str(addons_path)
    installed = load_installed()
    if addon_id not in installed:
        return False
    entry = installed[addon_id]
    log(f"⟩ removing {entry['name']}")
    backup_addon_folders(addon_id, entry, addons_path, log)
    for folder in entry.get("folders", []):
        p = os.path.join(addons_path, folder)
        if os.path.exists(p):
            if is_dry_run():
                log(f"  dry-run: would remove {folder}")
            else:
                shutil.rmtree(p)
    if not is_dry_run():
        del installed[addon_id]
        save_installed(installed)
    log("  ✓ removed\n")
    app_log(f"removed: {addon_id} profile={profile_id}")
    return True
