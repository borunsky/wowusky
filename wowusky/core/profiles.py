"""Profile management for multi-version WoW setups.

A *profile* binds together one WoW client installation (path + flavor)
with its own installed-addon database, backup directory, and a few
per-profile settings (auto-update, custom color tag).

The active profile is recorded in ``profiles.json``::

    {
      "active": "<id>",
      "profiles": {
        "<id>": { name, flavor, addons_path, wtf_path, interface,
                  auto_update, color, created_at }
      }
    }

Operations that touch installed addons take a profile id rather than
reading a single global ``addons_path`` so users can switch between
e.g. TBC Anniversary and Retail without confusion.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from wowusky.core.config import read_json, write_json
from wowusky.core.flavors import (
    flavor_display_name,
    flavor_for_directory,
    flavor_interface,
)
from wowusky.core.paths import PROFILES_FILE, ensure_dirs


@dataclass
class Profile:
    """One WoW client + flavor binding stored in profiles.json."""
    id: str
    name: str
    flavor: str                            # short key (anniversary, retail, …)
    addons_path: Path
    wtf_path: Path | None = None
    interface: int | None = None
    auto_update: bool = False
    color: str = "#3fdbb1"
    created_at: float = field(default_factory=time.time)

    def display_name(self) -> str:
        return self.name or flavor_display_name(self.flavor)


def _default_color_for(flavor: str) -> str:
    return {
        "anniversary":  "#3fdbb1",
        "vanilla":      "#f0a85e",
        "mop_classic":  "#7b9cf0",
        "retail":       "#e677b3",
        "ptr":          "#888888",
    }.get(flavor, "#3fdbb1")


def slugify(text: str) -> str:
    """Turn ``'TBC Anniversary'`` into ``'tbc_anniversary'``."""
    s = re.sub(r'[^a-zA-Z0-9]+', '_', (text or "").lower()).strip('_')
    return s or "profile"


def _read_store() -> dict:
    ensure_dirs()
    if not PROFILES_FILE.exists():
        return {"active": None, "profiles": {}}
    data = read_json(PROFILES_FILE, {})
    data.setdefault("active", None)
    data.setdefault("profiles", {})
    return data


def _write_store(data: dict) -> None:
    write_json(PROFILES_FILE, data)


def _from_dict(pid: str, entry: dict) -> Profile:
    return Profile(
        id=pid,
        name=entry.get("name", pid),
        flavor=entry.get("flavor") or entry.get("flavor_key") or "anniversary",
        addons_path=Path(entry["addons_path"]),
        wtf_path=Path(entry["wtf_path"]) if entry.get("wtf_path") else None,
        interface=int(entry["interface"]) if entry.get("interface") else None,
        auto_update=bool(entry.get("auto_update", False)),
        color=entry.get("color", _default_color_for(entry.get("flavor", ""))),
        created_at=float(entry.get("created_at", time.time())),
    )


def _to_dict(profile: Profile) -> dict:
    return {
        "name":        profile.name,
        "flavor":      profile.flavor,
        "addons_path": str(profile.addons_path),
        "wtf_path":    str(profile.wtf_path) if profile.wtf_path else "",
        "interface":   profile.interface or 0,
        "auto_update": profile.auto_update,
        "color":       profile.color,
        "created_at":  profile.created_at,
    }


def list_profiles() -> list[Profile]:
    """Return every known profile, sorted by display name."""
    store = _read_store()
    profiles: list[Profile] = []
    for pid, entry in store.get("profiles", {}).items():
        try:
            profiles.append(_from_dict(pid, entry))
        except (KeyError, TypeError, ValueError):
            continue
    profiles.sort(key=lambda p: p.display_name().lower())
    return profiles


def get_profile(pid: str) -> Profile | None:
    store = _read_store()
    entry = store.get("profiles", {}).get(pid)
    return _from_dict(pid, entry) if entry else None


def get_active_id() -> str | None:
    return _read_store().get("active")


def get_active() -> Profile | None:
    pid = get_active_id()
    return get_profile(pid) if pid else None


def set_active(pid: str | None) -> None:
    store = _read_store()
    if pid is not None and pid not in store.get("profiles", {}):
        raise KeyError(f"unknown profile id: {pid}")
    store["active"] = pid
    _write_store(store)


def upsert(profile: Profile) -> Profile:
    """Insert or update ``profile`` (keyed by ``profile.id``).

    The first profile inserted automatically becomes active.
    """
    store = _read_store()
    store.setdefault("profiles", {})[profile.id] = _to_dict(profile)
    if store.get("active") is None:
        store["active"] = profile.id
    _write_store(store)
    return profile


def remove(pid: str) -> bool:
    """Delete a profile. The active one falls back to whatever remains."""
    store = _read_store()
    if pid not in store.get("profiles", {}):
        return False
    del store["profiles"][pid]
    if store.get("active") == pid:
        remaining = list(store["profiles"].keys())
        store["active"] = remaining[0] if remaining else None
    _write_store(store)
    return True


def create_from_path(name: str, addons_path: str,
                     wtf_path: str = "",
                     flavor: str | None = None) -> Profile:
    """Build a Profile from a manually entered or detected AddOns path.

    If ``flavor`` is not given we sniff it from the path. The id is
    derived from ``name`` and made unique against existing profiles.
    """
    if flavor is None:
        flavor = flavor_for_directory(addons_path) or "anniversary"

    iface = flavor_interface(flavor)

    base_id = slugify(name)
    store   = _read_store()
    existing = store.get("profiles", {})
    pid = base_id
    suffix = 1
    while pid in existing:
        suffix += 1
        pid = f"{base_id}_{suffix}"

    wtf = wtf_path or os.path.normpath(
        os.path.join(addons_path, "..", "..", "..", "WTF"))

    profile = Profile(
        id=pid,
        name=name,
        flavor=flavor,
        addons_path=Path(addons_path),
        wtf_path=Path(wtf) if wtf else None,
        interface=iface,
        color=_default_color_for(flavor),
    )
    return upsert(profile)
