"""Scheduled-update support via a systemd *user* timer.

wowusky can install a ``wowusky-update.timer`` into the user's systemd
instance so addon updates are checked on a schedule (daily by default)
without a running GUI. This module is the pure orchestration layer: it
writes the unit files, drives ``systemctl --user``, and reports status.

Everything degrades gracefully when systemd is unavailable (e.g. a
non-systemd distro or a container) — :func:`available` returns ``False``
and :func:`status` reports ``available: False`` rather than raising.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess

SERVICE_NAME = "wowusky-update.service"
TIMER_NAME = "wowusky-update.timer"

BACKUP_SERVICE_NAME = "wowusky-backup.service"
BACKUP_TIMER_NAME = "wowusky-backup.timer"

COMPANION_SERVICE_NAME = "wowusky-companion.service"
COMPANION_TIMER_NAME = "wowusky-companion.timer"

# systemd OnCalendar expressions for the intervals we expose.
INTERVALS = {
    "hourly": "hourly",
    "daily": "daily",
    "weekly": "weekly",
}


def _unit_dir() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "systemd", "user")


def service_path() -> str:
    return os.path.join(_unit_dir(), SERVICE_NAME)


def timer_path() -> str:
    return os.path.join(_unit_dir(), TIMER_NAME)


def _wowusky_exec() -> str:
    """Resolve the command the timer should run.

    Prefer the installed ``wowusky`` launcher on PATH; fall back to the
    conventional ``~/.local/bin/wowusky`` the installer creates.
    """
    found = shutil.which("wowusky")
    if found:
        return found
    return os.path.expanduser("~/.local/bin/wowusky")


def available() -> bool:
    """True when a usable ``systemctl --user`` instance is present."""
    if not shutil.which("systemctl"):
        return False
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "is-system-running"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    # is-system-running prints running/degraded/… with rc 0; "offline" or a
    # missing user bus yields non-zero output we treat as unavailable.
    return bool(proc.stdout.strip()) and "offline" not in proc.stdout


def _systemctl(*args: str) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["systemctl", "--user", *args],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _show(prop: str, timer_name: str = TIMER_NAME) -> str:
    rc, out = _systemctl("show", timer_name, "-p", prop, "--value")
    return out.strip() if rc == 0 else ""


def status() -> dict:
    """Report the current scheduled-update state.

    Returns a dict with at least ``available`` and ``installed``; when
    installed it adds ``enabled``, ``active``, ``interval`` and the
    next/last run timestamps.
    """
    if not available():
        return {"available": False, "installed": False}
    installed = os.path.isfile(timer_path())
    if not installed:
        return {"available": True, "installed": False}
    enabled = _show("UnitFileState") in ("enabled", "enabled-runtime")
    active = _show("ActiveState") == "active"
    return {
        "available": True,
        "installed": True,
        "enabled": enabled,
        "active": active,
        "interval": _read_interval(),
        "next_run": _show("NextElapseUSecRealtime") or None,
        "last_run": _show("LastTriggerUSec") or None,
    }


def _read_interval() -> str:
    """Recover the configured interval from the on-disk timer unit."""
    try:
        with open(timer_path(), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("OnCalendar="):
                    val = line.split("=", 1)[1].strip()
                    for name, expr in INTERVALS.items():
                        if expr == val:
                            return name
                    return val
    except OSError:
        pass
    return "daily"


def _write_units(interval: str) -> None:
    oncal = INTERVALS.get(interval, INTERVALS["daily"])
    os.makedirs(_unit_dir(), exist_ok=True)
    service = (
        "[Unit]\n"
        "Description=wowusky scheduled addon update\n"
        "After=network-online.target\n"
        "Wants=network-online.target\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"ExecStart={_wowusky_exec()} update -q\n"
    )
    timer = (
        "[Unit]\n"
        "Description=wowusky scheduled addon update timer\n"
        "\n"
        "[Timer]\n"
        f"OnCalendar={oncal}\n"
        "Persistent=true\n"
        "\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )
    with open(service_path(), "w", encoding="utf-8") as fh:
        fh.write(service)
    with open(timer_path(), "w", encoding="utf-8") as fh:
        fh.write(timer)


def enable(interval: str = "daily") -> dict:
    """Install the unit files and enable + start the timer.

    Returns the resulting :func:`status` on success, or
    ``{"ok": False, "error": ...}`` on failure.
    """
    if not available():
        return {"ok": False, "error": "systemd user instance not available"}
    if interval not in INTERVALS:
        interval = "daily"
    _write_units(interval)
    _systemctl("daemon-reload")
    rc, out = _systemctl("enable", "--now", TIMER_NAME)
    if rc != 0:
        return {"ok": False, "error": out or "failed to enable timer"}
    return {"ok": True, **status()}


def disable() -> dict:
    """Stop, disable and remove the timer + service units."""
    if not available():
        return {"ok": False, "error": "systemd user instance not available"}
    _systemctl("disable", "--now", TIMER_NAME)
    for path in (timer_path(), service_path()):
        with contextlib.suppress(OSError):
            os.remove(path)
    _systemctl("daemon-reload")
    return {"ok": True, **status()}


# ---------------------------------------------------------------------------
# Scheduled full backups (a second, independent user timer)
# ---------------------------------------------------------------------------

def backup_service_path() -> str:
    return os.path.join(_unit_dir(), BACKUP_SERVICE_NAME)


def backup_timer_path() -> str:
    return os.path.join(_unit_dir(), BACKUP_TIMER_NAME)


def _read_backup_keep() -> int:
    """Recover the configured ``--keep N`` from the on-disk service unit."""
    try:
        with open(backup_service_path(), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("ExecStart=") and "--keep" in line:
                    parts = line.split()
                    if "--keep" in parts:
                        idx = parts.index("--keep")
                        if idx + 1 < len(parts):
                            with contextlib.suppress(ValueError):
                                return int(parts[idx + 1])
    except OSError:
        pass
    return 5


def backup_status() -> dict:
    """Report the current scheduled-backup state (mirrors :func:`status`)."""
    if not available():
        return {"available": False, "installed": False}
    if not os.path.isfile(backup_timer_path()):
        return {"available": True, "installed": False}
    enabled = _show("UnitFileState", BACKUP_TIMER_NAME) in ("enabled", "enabled-runtime")
    active = _show("ActiveState", BACKUP_TIMER_NAME) == "active"
    interval = "daily"
    try:
        with open(backup_timer_path(), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("OnCalendar="):
                    val = line.split("=", 1)[1].strip()
                    interval = next((n for n, e in INTERVALS.items() if e == val), val)
                    break
    except OSError:
        pass
    return {
        "available": True,
        "installed": True,
        "enabled": enabled,
        "active": active,
        "interval": interval,
        "keep": _read_backup_keep(),
        "next_run": _show("NextElapseUSecRealtime", BACKUP_TIMER_NAME) or None,
        "last_run": _show("LastTriggerUSec", BACKUP_TIMER_NAME) or None,
    }


def _write_backup_units(interval: str, keep: int) -> None:
    oncal = INTERVALS.get(interval, INTERVALS["daily"])
    os.makedirs(_unit_dir(), exist_ok=True)
    service = (
        "[Unit]\n"
        "Description=wowusky scheduled full backup\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"ExecStart={_wowusky_exec()} backup auto --keep {int(keep)}\n"
    )
    timer = (
        "[Unit]\n"
        "Description=wowusky scheduled full backup timer\n"
        "\n"
        "[Timer]\n"
        f"OnCalendar={oncal}\n"
        "Persistent=true\n"
        "\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )
    with open(backup_service_path(), "w", encoding="utf-8") as fh:
        fh.write(service)
    with open(backup_timer_path(), "w", encoding="utf-8") as fh:
        fh.write(timer)


def backup_enable(interval: str = "daily", keep: int = 5) -> dict:
    """Install + enable the scheduled-backup timer."""
    if not available():
        return {"ok": False, "error": "systemd user instance not available"}
    if interval not in INTERVALS:
        interval = "daily"
    _write_backup_units(interval, max(1, int(keep)))
    _systemctl("daemon-reload")
    rc, out = _systemctl("enable", "--now", BACKUP_TIMER_NAME)
    if rc != 0:
        return {"ok": False, "error": out or "failed to enable backup timer"}
    return {"ok": True, **backup_status()}


def backup_disable() -> dict:
    """Stop, disable and remove the scheduled-backup timer + service units."""
    if not available():
        return {"ok": False, "error": "systemd user instance not available"}
    _systemctl("disable", "--now", BACKUP_TIMER_NAME)
    for path in (backup_timer_path(), backup_service_path()):
        with contextlib.suppress(OSError):
            os.remove(path)
    _systemctl("daemon-reload")
    return {"ok": True, **backup_status()}


# ---------------------------------------------------------------------------
# Scheduled WeakAurasCompanion rebuilds (#63) — a third user timer
# ---------------------------------------------------------------------------

def companion_service_path() -> str:
    return os.path.join(_unit_dir(), COMPANION_SERVICE_NAME)


def companion_timer_path() -> str:
    return os.path.join(_unit_dir(), COMPANION_TIMER_NAME)


def companion_status() -> dict:
    """Report the current companion-build timer state (mirrors :func:`status`)."""
    if not available():
        return {"available": False, "installed": False}
    if not os.path.isfile(companion_timer_path()):
        return {"available": True, "installed": False}
    enabled = _show("UnitFileState", COMPANION_TIMER_NAME) in ("enabled", "enabled-runtime")
    active = _show("ActiveState", COMPANION_TIMER_NAME) == "active"
    interval = "daily"
    try:
        with open(companion_timer_path(), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("OnCalendar="):
                    val = line.split("=", 1)[1].strip()
                    interval = next((n for n, e in INTERVALS.items() if e == val), val)
                    break
    except OSError:
        pass
    return {
        "available": True,
        "installed": True,
        "enabled": enabled,
        "active": active,
        "interval": interval,
        "next_run": _show("NextElapseUSecRealtime", COMPANION_TIMER_NAME) or None,
        "last_run": _show("LastTriggerUSec", COMPANION_TIMER_NAME) or None,
    }


def _write_companion_units(interval: str) -> None:
    oncal = INTERVALS.get(interval, INTERVALS["daily"])
    os.makedirs(_unit_dir(), exist_ok=True)
    service = (
        "[Unit]\n"
        "Description=wowusky scheduled WeakAurasCompanion rebuild\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"ExecStart={_wowusky_exec()} weakauras companion -q\n"
    )
    timer = (
        "[Unit]\n"
        "Description=wowusky scheduled WeakAurasCompanion rebuild timer\n"
        "\n"
        "[Timer]\n"
        f"OnCalendar={oncal}\n"
        "Persistent=true\n"
        "\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )
    with open(companion_service_path(), "w", encoding="utf-8") as fh:
        fh.write(service)
    with open(companion_timer_path(), "w", encoding="utf-8") as fh:
        fh.write(timer)


def companion_enable(interval: str = "daily") -> dict:
    """Install + enable the scheduled companion-rebuild timer."""
    if not available():
        return {"ok": False, "error": "systemd user instance not available"}
    if interval not in INTERVALS:
        interval = "daily"
    _write_companion_units(interval)
    _systemctl("daemon-reload")
    rc, out = _systemctl("enable", "--now", COMPANION_TIMER_NAME)
    if rc != 0:
        return {"ok": False, "error": out or "failed to enable companion timer"}
    return {"ok": True, **companion_status()}


def companion_disable() -> dict:
    """Stop, disable and remove the companion-rebuild timer + service units."""
    if not available():
        return {"ok": False, "error": "systemd user instance not available"}
    _systemctl("disable", "--now", COMPANION_TIMER_NAME)
    for path in (companion_timer_path(), companion_service_path()):
        with contextlib.suppress(OSError):
            os.remove(path)
    _systemctl("daemon-reload")
    return {"ok": True, **companion_status()}
