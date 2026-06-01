"""CurseForge provider — function-based implementation.

The PURE PROVIDER functions for CurseForge, extracted verbatim from
app.py during the v0.5 provider extraction (Etappe A). Behaviour is
pinned by tests/test_characterize_providers.py — 15 tests covering
slug parsing, the web-fallback functions, header building, and the
flavor-matching logic.

NOT moved here (deliberately): the install layer (install_curseforge,
install_curseforge_dependencies, import_zip_file), the API-call layer
(curseforge_json, curseforge_mod_from_ref, curseforge_get_files,
curseforge_pick_file), and all *_url / *_search / *_manual helpers.
Per the migration dossier, those belong to later stages.
"""

from __future__ import annotations

import re

from wowusky import APP_NAME, __version__

CURSEFORGE_URL_RX = re.compile(
    r'curseforge\.com/wow/addons/([a-zA-Z0-9_-]+)')

CF_FLAVOR_TEXT = {
    "retail":      ("retail", "mainline", "the war within", "dragonflight", "war within"),
    "ptr":         ("ptr", "retail", "mainline"),
    "anniversary": ("anniversary", "tbc", "burning crusade", "classic", "bcc"),
    "vanilla":     ("classic era", "classic", "vanilla", "sod", "season of discovery"),
    "mop_classic": ("mists", "mop", "mists of pandaria", "classic"),
}

CF_VERSION_TYPE_HINTS = {
    "retail": 517,
    "ptr": 517,
    "anniversary": 67408,
    "vanilla": 67408,
    "mop_classic": 73246,
}


def get_curseforge_api_key():
    """Imported back from app.py at runtime — see app.py injection.

    Falls back to the env-var / empty string outside the GUI.
    """
    import os
    return os.environ.get("CURSEFORGE_API_KEY", "")


def get_current_flavor():
    """Imported back from app.py at runtime — see app.py injection.

    Falls back to "retail" when called outside the GUI (e.g. health_check).
    """
    return "retail"


def cf_slug_from_ref(ref):
    ref = (ref or "").strip()
    if not ref:
        return ""
    m = CURSEFORGE_URL_RX.search(ref)
    if m:
        return m.group(1)
    if ref.isdigit():
        return ""
    return ref.strip("/").split("/")[-1]


def curseforge_headers():
    key = get_curseforge_api_key()
    if not key:
        raise RuntimeError(
            "CurseForge API key missing. Add it in Settings or set CURSEFORGE_API_KEY.")
    return {
        "Accept": "application/json",
        "x-api-key": key,
        "User-Agent": f"{APP_NAME}/{__version__}",
    }


def curseforge_web_version(a):
    return "manual"


def curseforge_web_url(a):
    return "https://www.curseforge.com/wow/addons/" + a.get("curseforge_slug", a.get("id", ""))


def _cf_file_versions(file_data):
    versions = []
    versions.extend(str(v).lower() for v in file_data.get("gameVersions", []) if v)
    for v in file_data.get("sortableGameVersions", []) or []:
        for key in ("gameVersion", "gameVersionName", "gameVersionPadded"):
            if v.get(key):
                versions.append(str(v[key]).lower())
        if v.get("gameVersionTypeId"):
            versions.append(f"type:{v['gameVersionTypeId']}")
    return versions


def curseforge_file_matches_flavor(file_data):
    flavor = get_current_flavor() or "retail"
    versions = _cf_file_versions(file_data)
    text_hints = CF_FLAVOR_TEXT.get(flavor, ())
    type_hint = CF_VERSION_TYPE_HINTS.get(flavor)
    if type_hint and f"type:{type_hint}" in versions:
        return True
    if not versions:
        return True
    joined = " ".join(versions)
    return any(h in joined for h in text_hints)
