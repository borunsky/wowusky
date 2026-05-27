"""WoWInterface provider — function-based implementation.

These functions are the behaviour that wowusky actually runs. They
were extracted verbatim from app.py during the v0.5 provider
extraction (Etappe A). Behaviour is pinned by
tests/test_characterize_providers.py — it must not change here.

This module is separate from wowinterface.py (the older class-based
AddonProvider API), which is left untouched for now.
"""

from __future__ import annotations

from wowusky.core.http import get_json as http_get_json


def wowi_info(wid):
    try:
        data = http_get_json(
            f"https://api.mmoui.com/v3/game/WOW/filedetails/{wid}.json")
        return data[0] if isinstance(data, list) and data else data
    except Exception:
        return {}


def wowi_version(a):
    info = wowi_info(a["wowi_id"])
    return info.get("UIVersion") or info.get("Version") or "manual"


def wowi_page_url(a):
    return f"https://www.wowinterface.com/downloads/info{a['wowi_id']}.html"


def wowi_url(a):
    info = wowi_info(a["wowi_id"])
    return info.get("UIDownload") or ""

