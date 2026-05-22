"""Addon backup and rollback.

Before an install/update overwrites an addon, wowusky archives the
existing folders into a timestamped ZIP under

    ~/.local/share/wowusky/backups/<profile_id>/<addon_id>/

The most recent :data:`MAX_BACKUPS_PER_ADDON` archives are kept; older
ones are pruned automatically. Users can roll back from any kept
archive via the UI.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import time
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from wowusky.core.paths import backup_dir_for, ensure_dirs

MAX_BACKUPS_PER_ADDON = 3


@dataclass
class Backup:
    """One archived snapshot of an addon."""
    path: Path
    timestamp: float
    version_tag: str

    @property
    def age_seconds(self) -> float:
        return time.time() - self.timestamp


def _archive_name(version_tag: str, existing: list[Path] | None = None) -> str:
    """Build a unique archive filename.

    The base form is ``<YYYYmmdd-HHMMSS>_<version>.zip``. Two backups
    created in the same second would collide; we append ``-1``, ``-2``,
    … to disambiguate by checking against ``existing`` paths.
    """
    ts = time.strftime("%Y%m%d-%H%M%S")
    safe = version_tag.replace("/", "_").replace(" ", "_")[:32] or "unknown"
    base = f"{ts}_{safe}"
    if not existing:
        return f"{base}.zip"
    names = {p.name for p in existing}
    candidate = f"{base}.zip"
    n = 1
    while candidate in names:
        candidate = f"{base}-{n}.zip"
        n += 1
    return candidate


# Legacy helpers from the original 14-line module — kept for
# backwards compatibility with code that still imports them.
def zip_tree(src: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in src.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(src))
    return dest


def timestamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def make_backup(profile_id: str, addon_id: str, addons_path: str,
                folders: Iterable[str], version_tag: str = "unknown") -> Backup | None:
    """Archive the listed addon folders into a ZIP under the profile backup dir.

    Returns ``None`` if none of the folders exist on disk (nothing to back up).
    Otherwise returns the resulting :class:`Backup` and prunes old archives.
    """
    ensure_dirs()
    existing_folders = [f for f in folders
                        if os.path.isdir(os.path.join(addons_path, f))]
    if not existing_folders:
        return None

    backup_dir = backup_dir_for(profile_id, addon_id)
    backup_dir.mkdir(parents=True, exist_ok=True)
    existing_archives = list(backup_dir.glob("*.zip"))
    archive_path = backup_dir / _archive_name(version_tag, existing_archives)

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for folder in existing_folders:
            src_root = os.path.join(addons_path, folder)
            for dirpath, _dirs, filenames in os.walk(src_root):
                for name in filenames:
                    full = os.path.join(dirpath, name)
                    arc  = os.path.relpath(full, addons_path)
                    zf.write(full, arc)

    _prune(backup_dir)
    return Backup(path=archive_path, timestamp=time.time(), version_tag=version_tag)


def _prune(backup_dir: Path) -> None:
    archives = sorted(backup_dir.glob("*.zip"),
                      key=lambda p: p.stat().st_mtime,
                      reverse=True)
    for old in archives[MAX_BACKUPS_PER_ADDON:]:
        with contextlib.suppress(OSError):
            old.unlink()


def list_backups(profile_id: str, addon_id: str) -> list[Backup]:
    """Return all archives for an addon, newest first."""
    backup_dir = backup_dir_for(profile_id, addon_id)
    if not backup_dir.exists():
        return []
    out: list[Backup] = []
    for p in backup_dir.glob("*.zip"):
        st = p.stat()
        version_tag = "unknown"
        stem = p.stem
        if "_" in stem:
            version_tag = stem.split("_", 1)[1]
        out.append(Backup(path=p, timestamp=st.st_mtime, version_tag=version_tag))
    out.sort(key=lambda b: b.timestamp, reverse=True)
    return out


def restore(backup: Backup, addons_path: str,
            folders_to_clear: Iterable[str]) -> list[str]:
    """Roll back: delete the given folders, then extract ``backup.path``.

    Returns the list of top-level folders the archive contained.
    """
    for folder in folders_to_clear:
        target = os.path.join(addons_path, folder)
        if os.path.isdir(target):
            shutil.rmtree(target)
    with zipfile.ZipFile(backup.path, "r") as zf:
        zf.extractall(addons_path)
        top = {n.split("/", 1)[0] for n in zf.namelist() if "/" in n}
        return sorted(top)
