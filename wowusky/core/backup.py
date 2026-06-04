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
import json
import os
import re
import shutil
import tempfile
import time
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from wowusky.core.paths import BACKUP_DIR, backup_dir_for, ensure_dirs

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


# ---------------------------------------------------------------------------
# Profile-aware addon backup helpers (used by the GUI and install path)
# ---------------------------------------------------------------------------

MAX_ADDON_BACKUPS = 10
FULL_BACKUP_DIR_NAME = "full"


def _safe_addon_id(addon_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", addon_id)


def _addon_backup_meta(zip_path: str) -> dict:
    meta: dict = {}
    with contextlib.suppress(Exception):
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in ("wowusky-addon-backup.json", "wowusky-backup.json"):
                if name in zf.namelist():
                    meta = json.loads(zf.read(name).decode("utf-8"))
                    break
    return meta if isinstance(meta, dict) else {}


def list_addon_backups(addon_id: str) -> list[dict]:
    """Return all per-addon backup ZIPs for the active profile, newest first."""
    from wowusky.core.state import get_active_profile_id  # late import avoids circular
    profile_id = get_active_profile_id()
    safe = _safe_addon_id(addon_id)
    target_dir = Path(str(BACKUP_DIR)) / profile_id
    backups: list[dict] = []
    if target_dir.exists():
        for z in target_dir.glob(f"{safe}-*.zip"):
            with contextlib.suppress(OSError):
                meta = _addon_backup_meta(str(z))
                entry = meta.get("entry", {}) if isinstance(meta.get("entry"), dict) else {}
                backups.append({
                    "path": str(z),
                    "name": z.name,
                    "mtime": z.stat().st_mtime,
                    "size": z.stat().st_size,
                    "version": entry.get("version") or meta.get("version") or "unknown",
                    "source": entry.get("source") or meta.get("source") or "backup",
                    "folders": entry.get("folders") or meta.get("folders") or [],
                    "entry": entry,
                })
    backups.sort(key=lambda x: x["mtime"], reverse=True)
    return backups


def backup_addon_folders(
    addon_id: str,
    entry: dict,
    addons_path: str,
    log=print,
) -> str | None:
    """Archive the addon's current folders before an install/update.

    Returns the path to the created ZIP, or ``None`` if nothing was backed up.
    Prunes old archives beyond :data:`MAX_ADDON_BACKUPS`.
    """
    from wowusky.core.state import get_active_profile_id, is_dry_run  # late import
    if not entry or not entry.get("folders") or not addons_path:
        return None
    existing = [f for f in entry.get("folders", [])
                if os.path.exists(os.path.join(addons_path, f))]
    if not existing:
        return None
    profile_id = get_active_profile_id()
    ts = time.strftime("%Y%m%d-%H%M%S")
    safe = _safe_addon_id(addon_id)
    target_dir = os.path.join(str(BACKUP_DIR), profile_id)
    os.makedirs(target_dir, exist_ok=True)
    zip_base = os.path.join(target_dir, f"{safe}-{ts}")
    if is_dry_run():
        log(f"  dry-run: would backup {', '.join(existing)}")
        return zip_base + ".zip"
    with zipfile.ZipFile(zip_base + ".zip", "w", zipfile.ZIP_DEFLATED) as zf:
        meta = {
            "type": "addon",
            "addon_id": addon_id,
            "profile": profile_id,
            "created_at": ts,
            "version": entry.get("version"),
            "source": entry.get("source"),
            "folders": existing,
            "entry": entry,
        }
        zf.writestr("wowusky-addon-backup.json", json.dumps(meta, indent=2))
        for folder in existing:
            root_path = os.path.join(addons_path, folder)
            for root, _dirs, files in os.walk(root_path):
                for name in files:
                    fp = os.path.join(root, name)
                    arc = os.path.relpath(fp, addons_path)
                    zf.write(fp, arc)
    log(f"  ↶ backup: {os.path.basename(zip_base)}.zip")
    archives = sorted(
        Path(target_dir).glob(f"{safe}-*.zip"),
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    )
    for old in archives[MAX_ADDON_BACKUPS:]:
        with contextlib.suppress(Exception):
            old.unlink()
    return zip_base + ".zip"


def _zip_index(zip_path: str) -> dict[str, int]:
    """Map archive member path -> uncompressed size, skipping wowusky meta files."""
    index: dict[str, int] = {}
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir() or info.filename.startswith("wowusky-"):
                continue
            index[info.filename] = info.file_size
    return index


def diff_backups(path_a: str, path_b: str) -> dict:
    """Compare two backup archives by their ZIP indices (no extraction).

    Returns ``{added, removed, changed}`` where *added* are files present only
    in B, *removed* only in A, and *changed* files whose uncompressed size
    differs between A and B.
    """
    if not os.path.isfile(path_a) or not os.path.isfile(path_b):
        raise RuntimeError("backup ZIP not found")
    idx_a = _zip_index(path_a)
    idx_b = _zip_index(path_b)
    added = sorted(set(idx_b) - set(idx_a))
    removed = sorted(set(idx_a) - set(idx_b))
    changed = [
        {"path": p, "size_a": idx_a[p], "size_b": idx_b[p]}
        for p in sorted(set(idx_a) & set(idx_b))
        if idx_a[p] != idx_b[p]
    ]
    return {"added": added, "removed": removed, "changed": changed}


def latest_backup_for_addon(addon_id: str) -> str | None:
    backups = list_addon_backups(addon_id)
    return backups[0]["path"] if backups else None


def rollback_addon_to_backup(
    addon_id: str,
    backup: str,
    addons_path: str,
    log=print,
) -> bool:
    """Restore a specific backup ZIP for an addon."""
    from wowusky.core.installer import append_version_history  # late import
    from wowusky.core.state import is_dry_run, load_installed, save_installed  # late import
    if not backup:
        log("  ✗ no backup selected")
        return False
    if not os.path.isfile(backup):
        log("  ✗ backup ZIP not found")
        return False
    installed = load_installed()
    entry = installed.get(addon_id)
    if entry:
        for folder in entry.get("folders", []):
            p = os.path.join(addons_path, folder)
            if os.path.exists(p):
                if is_dry_run():
                    log(f"  dry-run: would remove {folder}")
                else:
                    shutil.rmtree(p)
    if is_dry_run():
        log(f"  dry-run: would restore {os.path.basename(backup)}")
        return True
    with zipfile.ZipFile(backup, "r") as zf:
        members = [n for n in zf.namelist() if not n.startswith("wowusky-")]
        for n in members:
            zf.extract(n, addons_path)
    meta = _addon_backup_meta(backup)
    restored_entry = meta.get("entry") if isinstance(meta.get("entry"), dict) else None
    if restored_entry:
        current_entry = installed.get(addon_id)
        restored_entry = dict(restored_entry)
        restored_entry["restored_from"] = backup
        restored_entry["restored_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        append_version_history(restored_entry, current_entry, backup_path=backup, action="restore")
        installed[addon_id] = restored_entry
        save_installed(installed)
    log(f"  ✓ restored {os.path.basename(backup)}")
    return True


def rollback_addon(addon_id: str, addons_path: str, log=print) -> bool:
    backup = latest_backup_for_addon(addon_id)
    if not backup:
        log("  ✗ no backup found")
        return False
    return rollback_addon_to_backup(addon_id, backup, addons_path, log)


# ---------------------------------------------------------------------------
# Full-profile backup (AddOns + WTF)
# ---------------------------------------------------------------------------

def full_backup_dir() -> str:
    from wowusky.core.state import get_active_profile_id  # late import
    profile_id = get_active_profile_id()
    path = os.path.join(str(BACKUP_DIR), profile_id, FULL_BACKUP_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def list_full_backups() -> list[dict]:
    d = Path(full_backup_dir())
    items: list[dict] = []
    for z in d.glob("wowusky-full-*.zip"):
        with contextlib.suppress(OSError):
            items.append({
                "path": str(z),
                "name": z.name,
                "mtime": z.stat().st_mtime,
                "size": z.stat().st_size,
            })
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items


def create_full_backup(log=print) -> str:
    """Create a full profile backup (Interface/AddOns + WTF settings)."""
    from wowusky.core.state import (  # late import
        get_active_profile,
        get_active_profile_id,
        get_addons_path,
        get_wtf_path,
        is_dry_run,
        load_installed,
    )
    prof = get_active_profile()
    addons_path = prof.get("addons_path") or get_addons_path()
    wtf_path = prof.get("wtf_path") or get_wtf_path()
    if not addons_path or not os.path.isdir(addons_path):
        raise RuntimeError("AddOns path is not configured")
    ts = time.strftime("%Y%m%d-%H%M%S")
    out = os.path.join(full_backup_dir(), f"wowusky-full-{get_active_profile_id()}-{ts}.zip")
    log(f"⟩ creating full backup for {prof.get('name', get_active_profile_id())}")
    if is_dry_run():
        log(f"  dry-run: would write {out}")
        return out
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        meta = {
            "profile": get_active_profile_id(),
            "created_at": ts,
            "addons_path": addons_path,
            "wtf_path": wtf_path,
            "installed": load_installed(),
        }
        zf.writestr("wowusky-backup.json", json.dumps(meta, indent=2))
        for label, base in (("AddOns", addons_path), ("WTF", wtf_path)):
            if not base or not os.path.isdir(base):
                continue
            for root, _dirs, files in os.walk(base):
                for name in files:
                    fp = os.path.join(root, name)
                    arc = os.path.join(label, os.path.relpath(fp, base))
                    with contextlib.suppress(OSError):
                        zf.write(fp, arc)
    log(f"  ✓ full backup: {os.path.basename(out)}")
    return out


def restore_full_backup(zip_path: str, log=print) -> bool:
    """Restore a full profile backup, overwriting current AddOns and WTF files."""
    from wowusky.core.state import (  # late import
        get_active_profile,
        get_addons_path,
        get_wtf_path,
        is_dry_run,
        save_installed,
    )
    prof = get_active_profile()
    addons_path = prof.get("addons_path") or get_addons_path()
    wtf_path = prof.get("wtf_path") or get_wtf_path()
    if not zip_path or not os.path.isfile(zip_path):
        raise RuntimeError("Backup ZIP not found")
    if not addons_path or not os.path.isdir(addons_path):
        raise RuntimeError("AddOns path is not configured")
    if is_dry_run():
        log(f"  dry-run: would restore {os.path.basename(zip_path)}")
        return True
    log(f"⟩ restoring full backup {os.path.basename(zip_path)}")
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp)
        addons_src = os.path.join(tmp, "AddOns")
        wtf_src = os.path.join(tmp, "WTF")
        if os.path.isdir(addons_src):
            os.makedirs(addons_path, exist_ok=True)
            for name in os.listdir(addons_src):
                src = os.path.join(addons_src, name)
                dst = os.path.join(addons_path, name)
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
        if os.path.isdir(wtf_src) and wtf_path:
            os.makedirs(wtf_path, exist_ok=True)
            for root, _dirs, files in os.walk(wtf_src):
                rel = os.path.relpath(root, wtf_src)
                dst_root = os.path.join(wtf_path, rel) if rel != "." else wtf_path
                os.makedirs(dst_root, exist_ok=True)
                for name in files:
                    shutil.copy2(os.path.join(root, name), os.path.join(dst_root, name))
        meta_path = os.path.join(tmp, "wowusky-backup.json")
        if os.path.exists(meta_path):
            with contextlib.suppress(Exception):
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
                if isinstance(meta.get("installed"), dict):
                    save_installed(meta["installed"])
    log("  ✓ full backup restored")
    return True
