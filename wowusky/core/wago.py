"""Wago.io tracking + WeakAuras Companion generation.

This module owns the *stateful* side of the Wago integration — the
local tracking list (``wago.json``), the WeakAuras SavedVariables
scanner, and the WeakAurasCompanion addon generator. The pure
provider functions (``wago_fetch_info``, ``wago_fetch_encoded``,
``parse_wago_url``) live in :mod:`wowusky.providers.wago_fns`.

Persistence (``load_wago``/``save_wago``, the installed DB, the WTF
path) is reused from :mod:`wowusky.core.state`. The WeakAurasCompanion
generator takes its TOC ``interface`` and the manager ``app_version``
as parameters so it stays decoupled from how ``app.py`` resolves the
active flavor.
"""

from __future__ import annotations

import glob
import os
import re
import urllib.parse

from wowusky.core.http import get_json as http_get_json
from wowusky.core.state import (
    get_wtf_path,
    load_installed,
    load_wago,
    save_installed,
    save_wago,
)
from wowusky.providers.wago_fns import wago_fetch_encoded, wago_fetch_info

# ----------------------------------------------------------------------
# Tracking list (wago.json)
# ----------------------------------------------------------------------

def wago_add(slug, name=None, note=None):
    """Add an aura to the tracking list."""
    wago = load_wago()
    if "auras" not in wago:
        wago["auras"] = {}

    info = wago_fetch_info(slug) or {}
    if not name:
        name = info.get("name") or slug

    wago["auras"][slug] = {
        "name": name,
        "slug": slug,
        "version": info.get("version") or info.get("wagoVersion") or 1,
        "note": note or info.get("note", ""),
        "type": info.get("type", "WeakAura"),
        "url": f"https://wago.io/{slug}",
        "added_at": "now",
    }
    save_wago(wago)
    return wago["auras"][slug]


def wago_remove(slug):
    wago = load_wago()
    if slug in wago.get("auras", {}):
        del wago["auras"][slug]
        save_wago(wago)
        return True
    return False


def wago_check_updates():
    """Fetch current versions from wago for all tracked auras."""
    wago = load_wago()
    updates = []
    for slug, entry in wago.get("auras", {}).items():
        info = wago_fetch_info(slug)
        if info:
            latest = info.get("version") or info.get("wagoVersion") or 1
            try:
                if int(latest) > int(entry.get("version", 1)):
                    updates.append(slug)
                entry["latest_version"] = latest
            except (ValueError, TypeError):
                entry["latest_version"] = latest
    save_wago(wago)
    return updates


def wago_search(query, limit=20):
    """Search wago.io for auras."""
    try:
        q = urllib.parse.quote(query)
        url = f"https://data.wago.io/api/search/{q}?limit={limit}"
        return http_get_json(url)
    except Exception:
        return None


# ----------------------------------------------------------------------
# WeakAuras SavedVariables scanning
# ----------------------------------------------------------------------

def find_weakauras_savedvariables(wtf_path=None):
    """Return WeakAuras SavedVariables files for the active WoW profile."""
    wtf_path = wtf_path or get_wtf_path()
    if not wtf_path or not os.path.isdir(wtf_path):
        return []
    patterns = [
        os.path.join(wtf_path, "Account", "*", "SavedVariables", "WeakAuras.lua"),
        os.path.join(wtf_path, "Account", "*", "SavedVariables", "WeakAuras.lua.bak"),
    ]
    files = []
    for pattern in patterns:
        files.extend(glob.glob(pattern))
    return sorted(set(files), key=lambda p: os.path.getmtime(p), reverse=True)


def extract_wago_slugs_from_text(text):
    """Extract Wago slugs from WeakAuras SavedVariables text.

    WeakAuras stores Wago data in different shapes over time, so we use a few
    conservative patterns instead of a fragile Lua parser.
    """
    slugs = set()
    for m in re.finditer(r'wago\.io/([A-Za-z0-9_-]{3,})', text):
        slugs.add(m.group(1))
    key_patterns = [
        r'\["wagoID"\]\s*=\s*"([A-Za-z0-9_-]{3,})"',
        r'\["wagoId"\]\s*=\s*"([A-Za-z0-9_-]{3,})"',
        r'\["wago"\]\s*=\s*"([A-Za-z0-9_-]{3,})"',
        r'wagoID\s*=\s*"([A-Za-z0-9_-]{3,})"',
        r'wagoId\s*=\s*"([A-Za-z0-9_-]{3,})"',
    ]
    for rx in key_patterns:
        for m in re.finditer(rx, text):
            slugs.add(m.group(1))
    return sorted(slugs)


def import_existing_weakauras_from_savedvariables(log=print):
    files = find_weakauras_savedvariables()
    if not files:
        return {"added": 0, "existing": 0, "failed": 0, "files": [], "slugs": []}
    wago = load_wago()
    wago.setdefault("auras", {})
    all_slugs = []
    for path in files:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            all_slugs.extend(extract_wago_slugs_from_text(content))
        except Exception as exc:
            log(f"  ! could not read {path}: {exc}")
    slugs = sorted(set(all_slugs))
    added = existing = failed = 0
    for slug in slugs:
        if slug in wago.get("auras", {}):
            existing += 1
            continue
        try:
            entry = wago_add(slug)
            if entry:
                added += 1
            else:
                failed += 1
        except Exception as exc:
            failed += 1
            log(f"  ! wago.io/{slug}: {exc}")
    return {"added": added, "existing": existing, "failed": failed,
            "files": files, "slugs": slugs}


# ----------------------------------------------------------------------
# WeakAurasCompanion addon generator
# ----------------------------------------------------------------------

def generate_wac_companion(addons_path, *, interface=120001, app_version="0"):
    """Generate WeakAurasCompanion addon files from tracked wago data.

    ``interface`` is the TOC interface number for the target flavor and
    ``app_version`` is the manager version stamped into the TOC; both are
    passed in by the caller so this stays decoupled from flavor lookup.
    """
    if not addons_path:
        return False

    wago = load_wago()
    auras = wago.get("auras", {})

    companion_dir = os.path.join(addons_path, "WeakAurasCompanion")
    os.makedirs(companion_dir, exist_ok=True)

    # ── TOC file ──
    toc_path = os.path.join(companion_dir, "WeakAurasCompanion.toc")
    with open(toc_path, "w") as f:
        f.write(f"""## Interface: {interface}
## Title: WeakAuras Companion
## Notes: Generated by wowusky v{app_version}
## Author: wowusky
## Version: 1.0
## SavedVariables: WeakAurasCompanionDB
## Dependencies: WeakAuras

data.lua
init.lua
""")

    # ── data.lua ── (contains the actual aura data)
    data_path = os.path.join(companion_dir, "data.lua")
    with open(data_path, "w") as f:
        f.write("-- Generated by wowusky\n")
        f.write("local _, addon = ...\n")
        f.write("addon.data = {\n")
        f.write('  ["WeakAuras"] = {\n')
        f.write('    slugs = {\n')

        for slug, entry in auras.items():
            encoded = wago_fetch_encoded(slug)
            if not encoded:
                continue
            # Escape Lua string
            encoded_escaped = encoded.replace("\\", "\\\\").replace('"', '\\"')
            name_escaped    = entry["name"].replace('"', '\\"')
            f.write(f'      ["{slug}"] = {{\n')
            f.write(f'        name = "{name_escaped}",\n')
            f.write('        author = "wowusky",\n')
            f.write(f'        encoded = "{encoded_escaped}",\n')
            f.write(f'        wagoVersion = "{entry.get("version", 1)}",\n')
            f.write(f'        wagoSemver = "{entry.get("version", 1)}",\n')
            f.write(f'        versionNote = "{entry.get("note", "")}",\n')
            f.write('        source = "Wago",\n')
            f.write('        logo = "Interface\\\\Icons\\\\Inv_misc_questionmark",\n')
            f.write('      },\n')

        f.write('    },\n')
        f.write('    uids = {},\n')
        f.write('    ids = {},\n')
        f.write('    stash = {},\n')
        f.write('  },\n')
        f.write("}\n")

    # ── init.lua ──
    init_path = os.path.join(companion_dir, "init.lua")
    with open(init_path, "w") as f:
        f.write("""-- WeakAurasCompanion init
local _, addon = ...

local frame = CreateFrame("Frame")
frame:RegisterEvent("ADDON_LOADED")
frame:SetScript("OnEvent", function(self, event, name)
    if name == "WeakAurasCompanion" then
        if WeakAuras and addon.data then
            for addonName, data in pairs(addon.data) do
                if WeakAuras.AddCompanionData then
                    WeakAuras.AddCompanionData(data)
                end
            end
        end
    end
end)
""")

    # Mark as installed
    installed = load_installed()
    installed["wac"] = {
        "name": "WeakAuras Companion",
        "version": f"{len(auras)} auras",
        "folders": ["WeakAurasCompanion"],
        "source": "internal_wac",
        "discovered": False,
    }
    save_installed(installed)
    return True
