"""WoW installation discovery + filesystem/DB reconciliation.

Two concerns live here, both previously inline in ``app.py``:

* :func:`scan_wow_installations` — glob the common Steam/Wine/Lutris
  locations for WoW client trees and return one dict per detected flavor,
  hiding duplicate Steam aliases.
* :func:`sync_filesystem_with_db` — reconcile a profile's installed
  database against what is actually on disk: drop entries whose folders
  vanished, and adopt addon folders found on disk (matched against the
  catalog, or recorded as ``external``).

The persistence (installed DB) and TOC parsing are reused from
:mod:`wowusky.core.state` and :mod:`wowusky.core.toc`; the catalog is passed
in by the caller so this module stays decoupled from how ``app.py`` loads
it.
"""

from __future__ import annotations

import glob
import os

from wowusky.core.flavors import WOW_FLAVORS
from wowusky.core.state import load_installed, normalize_installations, save_installed
from wowusky.core.toc import read_addon_toc

WOW_SEARCH_PATHS = [
    "~/.local/share/Steam/steamapps/compatdata/*/pfx/drive_c/Program Files (x86)/World of Warcraft",
    "~/.local/share/Steam/steamapps/compatdata/*/pfx/drive_c/Program Files/World of Warcraft",
    "~/.steam/steam/steamapps/compatdata/*/pfx/drive_c/Program Files (x86)/World of Warcraft",
    "~/.steam/steam/steamapps/compatdata/*/pfx/drive_c/Program Files/World of Warcraft",
    "~/Games/world-of-warcraft/drive_c/Program Files (x86)/World of Warcraft",
    "~/Games/battlenet/drive_c/Program Files (x86)/World of Warcraft",
    "~/.wine/drive_c/Program Files (x86)/World of Warcraft",
    "~/.wine/drive_c/Program Files/World of Warcraft",
]


def _display_path_preference(path):
    """Prefer the canonical Steam path under ~/.local over ~/.steam duplicates."""
    p = os.path.expanduser(path)
    local = os.path.expanduser("~/.local/share/Steam")
    steam = os.path.expanduser("~/.steam/steam")
    if p.startswith(steam):
        candidate = local + p[len(steam):]
        if os.path.exists(candidate):
            return candidate
    return p


def scan_wow_installations():
    """Find WoW installations and hide duplicate Steam aliases.

    Steam on Linux often exposes the same compatdata tree through both
    ~/.local/share/Steam and ~/.steam/steam.  We compare real paths and keep
    only one entry, preferring the ~/.local/share/Steam display path.
    """
    found = []
    seen = set()

    for pattern in WOW_SEARCH_PATHS:
        for wow_dir in glob.glob(os.path.expanduser(pattern)):
            if not os.path.isdir(wow_dir):
                continue

            wow_real = os.path.realpath(wow_dir)

            for flavor, (name, key, _) in WOW_FLAVORS.items():
                fp = os.path.join(wow_dir, flavor)
                if not os.path.isdir(fp):
                    continue

                addons_real = os.path.realpath(os.path.join(fp, "Interface", "AddOns"))
                dedupe_key = (wow_real, flavor, addons_real)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)

                display_fp = _display_path_preference(fp)
                found.append({
                    "flavor": flavor,
                    "flavor_name": name,
                    "flavor_key": key,
                    "addons_path": os.path.join(display_fp, "Interface", "AddOns"),
                })

    found = normalize_installations(found)
    found.sort(key=lambda x: (0 if "/.local/share/Steam/" in x["addons_path"] else 1, x["flavor_name"], x["addons_path"]))
    return found


def sync_filesystem_with_db(addons_path, catalog):
    """Reconcile the active profile's installed DB with the AddOns folder.

    ``catalog`` is the addon catalog list (passed in by the caller). Drops
    installed entries whose primary folder no longer exists, then adopts any
    on-disk addon folders not yet tracked — matched to the catalog when
    possible, otherwise recorded as an ``external`` discovery.
    """
    if not addons_path or not os.path.isdir(addons_path):
        return

    installed = load_installed()

    # Cleanup stale entries
    for aid in list(installed.keys()):
        entry = installed[aid]
        if not entry.get("folders"):
            continue
        primary = entry["folders"][0]
        if not os.path.isdir(os.path.join(addons_path, primary)):
            del installed[aid]

    try:
        fs_folders = [f for f in os.listdir(addons_path)
                      if os.path.isdir(os.path.join(addons_path, f))
                      and not f.startswith(".")]
    except Exception:
        return

    known_folders = set()
    for entry in installed.values():
        for f in entry.get("folders", []):
            known_folders.add(f)

    catalog_by_folder = {}
    catalog_by_lower = {}
    for addon in catalog:
        for folder in addon["folders"]:
            catalog_by_folder[folder] = addon
            catalog_by_lower[folder.lower()] = addon

    processed = set(known_folders)

    for folder in sorted(fs_folders):
        if folder in processed:
            continue
        full = os.path.join(addons_path, folder)
        toc = read_addon_toc(full)
        if not toc:
            continue

        catalog_addon = catalog_by_folder.get(folder) or catalog_by_lower.get(folder.lower())
        if catalog_addon and catalog_addon["id"] not in installed:
            actual_folders = [f for f in catalog_addon["folders"]
                              if os.path.isdir(os.path.join(addons_path, f))]
            installed[catalog_addon["id"]] = {
                "name": catalog_addon["name"],
                "version": toc.get("version") or "unknown",
                "folders": actual_folders,
                "source": catalog_addon.get("provider") or catalog_addon.get("source") or "unknown",
                "interface": toc.get("interface"),
                "discovered": True,
            }
            for f in actual_folders:
                processed.add(f)
            continue

        # External addon
        related = [folder]
        for other in fs_folders:
            if other != folder and other.startswith(folder + "_") and other not in processed:
                related.append(other)

        addon_id = "fs_" + folder.lower().replace(" ", "_")
        if addon_id in installed:
            continue

        installed[addon_id] = {
            "name": toc.get("title") or folder,
            "version": toc.get("version") or "unknown",
            "folders": related,
            "source": "external",
            "interface": toc.get("interface"),
            "discovered": True,
        }
        for f in related:
            processed.add(f)

    save_installed(installed)
