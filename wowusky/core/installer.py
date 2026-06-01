"""Addon-install helpers — the I/O-light core of the install path.

The GUI orchestration (download, backup/rollback, profile-aware
``installed.json`` writes, dry-run guards) still lives in ``app.py``,
but the pure pieces — guessing a display name from a ZIP and turning an
extracted archive into a normalised ``installed`` entry — live here so
they can be reused and unit-tested without a Tk app or a configured
profile.
"""

from __future__ import annotations

import os
import re
import zipfile
from pathlib import Path

from .toc import read_addon_toc, strip_color_codes
from .zipper import extract_addon_zip


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
