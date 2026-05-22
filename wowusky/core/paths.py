"""Filesystem paths used by wowusky.

All user data lives under ``$XDG_DATA_HOME/wowusky`` (default
``~/.local/share/wowusky``). The on-disk layout is::

    wowusky/
    ├── config.json               # global settings (theme, dry-run, …)
    ├── profiles.json             # WoW installation profiles
    ├── wago.json                 # tracked WeakAuras (account-wide)
    ├── installed/                # one file per profile
    │   └── <profile_id>.json
    ├── backups/                  # rollback archives
    │   └── <profile_id>/<addon_id>/<timestamp>.zip
    ├── manifests/                # user-supplied catalog extensions
    │   └── *.json
    └── logs/                     # rotating log files

This module exposes the canonical paths so the rest of the code never
hard-codes them.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "wowusky"


def _xdg_data_home() -> Path:
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base).expanduser()
    return Path.home() / ".local" / "share"


DATA_DIR      = _xdg_data_home() / APP_NAME
CONFIG_FILE   = DATA_DIR / "config.json"
PROFILES_FILE = DATA_DIR / "profiles.json"
WAGO_FILE     = DATA_DIR / "wago.json"

INSTALLED_DIR = DATA_DIR / "installed"
BACKUP_DIR    = DATA_DIR / "backups"
MANIFEST_DIR  = DATA_DIR / "manifests"
LOG_DIR       = DATA_DIR / "logs"

# Legacy locations (pre-0.4) that we still migrate from.
LEGACY_INSTALLED_FILE = DATA_DIR / "installed.json"

# ``CONFIG_DIR`` is an alias for ``DATA_DIR``. The Tk GUI (``app.py``)
# historically used this name for the same directory; exposing it here
# lets the GUI import the canonical, XDG-aware paths instead of
# re-deriving its own with ``os.path.expanduser`` (which ignores
# ``XDG_DATA_HOME``). ``INSTALLED_FILE`` is the same legacy single-
# profile database as ``LEGACY_INSTALLED_FILE``, under the name the
# GUI expects.
CONFIG_DIR     = DATA_DIR
INSTALLED_FILE = LEGACY_INSTALLED_FILE


def ensure_dirs() -> None:
    """Create all wowusky data directories if they don't exist yet."""
    for d in (DATA_DIR, INSTALLED_DIR, BACKUP_DIR, MANIFEST_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)


def installed_file_for(profile_id: str) -> Path:
    """Return the per-profile installed-addons JSON path."""
    return INSTALLED_DIR / f"{profile_id}.json"


def backup_dir_for(profile_id: str, addon_id: str) -> Path:
    """Return the per-addon backup directory inside a profile."""
    return BACKUP_DIR / profile_id / addon_id
