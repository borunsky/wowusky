"""Global (cross-profile) configuration.

This module owns ``config.json``, the place we keep settings that apply
to the whole application — theme choice, optional CurseForge API key,
dry-run flag, etc.

Per-profile settings live in :mod:`wowusky.core.profiles` instead. The
old single-profile fields ``addons_path`` and ``active_profile`` are
read on first run for migration and then phased out.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from wowusky.core.paths import (
    CONFIG_FILE,
    DATA_DIR,
    LEGACY_INSTALLED_FILE,
    ensure_dirs,
    installed_file_for,
)

APP_NAME = "wowusky"


def ensure_config_dir() -> Path:
    """Make sure the data directory exists and return its path."""
    ensure_dirs()
    return DATA_DIR


def read_json(path: Path, default: Any) -> Any:
    """Read JSON from ``path`` or return ``default`` on any failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, data: Any) -> None:
    """Write ``data`` as pretty-printed JSON, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_config() -> dict:
    return read_json(CONFIG_FILE, {})


def save_config(cfg: dict) -> None:
    write_json(CONFIG_FILE, cfg)


def get(key: str, default: Any = None) -> Any:
    return load_config().get(key, default)


def set_key(key: str, value: Any) -> None:
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)


# Convenience accessors:

def get_theme() -> str:
    return get("theme", "auto")

def set_theme(mode: str) -> None:
    set_key("theme", mode)

def get_curseforge_api_key() -> str:
    return get("curseforge_api_key", "") or ""

def set_curseforge_api_key(key: str) -> None:
    set_key("curseforge_api_key", (key or "").strip())

def is_dry_run() -> bool:
    return bool(get("dry_run", False))

def set_dry_run(value: bool) -> None:
    set_key("dry_run", bool(value))

def get_auto_update_on_launch() -> bool:
    return bool(get("auto_update_on_launch", False))

def set_auto_update_on_launch(value: bool) -> None:
    set_key("auto_update_on_launch", bool(value))

def get_desktop_notifications() -> bool:
    return bool(get("desktop_notifications", True))

def set_desktop_notifications(value: bool) -> None:
    set_key("desktop_notifications", bool(value))

def get_update_diff_before_install() -> bool:
    return bool(get("update_diff_before_install", False))

def set_update_diff_before_install(value: bool) -> None:
    set_key("update_diff_before_install", bool(value))


def migrate_legacy_installed(target_profile_id: str) -> bool:
    """Move the pre-0.4 ``installed.json`` into the per-profile location.

    A no-op if there is nothing to migrate or the target already exists.
    Returns ``True`` if a migration happened.
    """
    if not LEGACY_INSTALLED_FILE.exists():
        return False
    target = installed_file_for(target_profile_id)
    if target.exists():
        return False
    ensure_dirs()
    shutil.copy2(LEGACY_INSTALLED_FILE, target)
    LEGACY_INSTALLED_FILE.rename(LEGACY_INSTALLED_FILE.with_suffix(".json.migrated"))
    return True
