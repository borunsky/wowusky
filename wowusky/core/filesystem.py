"""WoW installation detection and AddOns folder scanning.

We probe well-known Linux locations (Steam/Proton compatdata, Lutris,
plain Wine) for any directory containing the ``World of Warcraft`` game
folder. Inside that we look for the per-flavor subdirectories
(``_anniversary_``, ``_retail_``, …) and report every match.

Steam mirrors itself under both ``~/.local/share/Steam`` and
``~/.steam/steam``; we prefer the ``.local`` path for display because
that's the actual game location and the other is a symlink.
"""

from __future__ import annotations

import glob
import os
from collections.abc import Iterable
from dataclasses import dataclass

from wowusky.core.flavors import WOW_FLAVORS

WOW_SEARCH_PATHS: list[str] = [
    "~/.local/share/Steam/steamapps/compatdata/*/pfx/drive_c/Program Files (x86)/World of Warcraft",
    "~/.local/share/Steam/steamapps/compatdata/*/pfx/drive_c/Program Files/World of Warcraft",
    "~/.steam/steam/steamapps/compatdata/*/pfx/drive_c/Program Files (x86)/World of Warcraft",
    "~/.steam/steam/steamapps/compatdata/*/pfx/drive_c/Program Files/World of Warcraft",
    "~/Games/world-of-warcraft/drive_c/Program Files (x86)/World of Warcraft",
    "~/Games/battlenet/drive_c/Program Files (x86)/World of Warcraft",
    "~/.wine/drive_c/Program Files (x86)/World of Warcraft",
    "~/.wine/drive_c/Program Files/World of Warcraft",
]


@dataclass
class WowInstall:
    """One detected WoW client (one flavor inside one game folder)."""
    wow_root: str       # the "World of Warcraft" directory
    flavor: str         # short key from WOW_FLAVORS
    flavor_name: str    # human-friendly display name
    interface: int
    addons_path: str
    wtf_path: str


def _prefer_local_path(path: str) -> str:
    """Rewrite ``~/.steam/steam/...`` to the canonical ``~/.local/share/Steam/...``."""
    home = os.path.expanduser("~")
    local_steam = os.path.join(home, ".local/share/Steam")
    dot_steam   = os.path.join(home, ".steam/steam")
    if path.startswith(dot_steam):
        return path.replace(dot_steam, local_steam, 1)
    return path


def scan_installations(extra_paths: Iterable[str] | None = None) -> list[WowInstall]:
    """Walk the well-known WoW install locations and return every detected flavor.

    Duplicates (same AddOns directory reached via different glob patterns
    or Steam-path aliases) are removed automatically.
    """
    results: list[WowInstall] = []
    seen: set[str] = set()

    patterns = list(WOW_SEARCH_PATHS)
    if extra_paths:
        patterns.extend(extra_paths)

    for pattern in patterns:
        expanded = os.path.expanduser(pattern)
        for wow_dir in glob.glob(expanded):
            if not os.path.isdir(wow_dir):
                continue
            wow_dir = _prefer_local_path(wow_dir)
            for marker, (name, key, iface) in WOW_FLAVORS.items():
                flavor_root = os.path.join(wow_dir, marker)
                if not os.path.isdir(flavor_root):
                    continue
                addons = os.path.join(flavor_root, "Interface", "AddOns")
                if addons in seen:
                    continue
                seen.add(addons)
                results.append(WowInstall(
                    wow_root=wow_dir,
                    flavor=key,
                    flavor_name=name,
                    interface=iface,
                    addons_path=addons,
                    wtf_path=os.path.join(flavor_root, "WTF"),
                ))
    return results


def list_addon_folders(addons_path: str) -> list[str]:
    """List top-level addon directories inside ``addons_path``."""
    try:
        return sorted([
            f for f in os.listdir(addons_path)
            if os.path.isdir(os.path.join(addons_path, f))
            and not f.startswith(".")
        ])
    except OSError:
        return []
