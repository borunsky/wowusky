"""WoWInterface provider via the MMOUI JSON API.

Some addons on WoWI don't expose a stable direct ZIP URL — when that
happens we return ``None`` from :meth:`download_url` and the caller
falls back to opening :meth:`page_url` in the browser.
"""

from __future__ import annotations

from .base import AddonRef
from .common import HttpError, get_json

API = "https://api.mmoui.com/v3/game/WOW"


def _normalise_id(ref: str) -> str:
    return "".join(ch for ch in (ref or "") if ch.isdigit())


def _fetch_info(addon_id: str) -> dict:
    data = get_json(f"{API}/filedetails/{addon_id}.json")
    if isinstance(data, list):
        return data[0] if data else {}
    return data or {}


class WoWInterfaceProvider:
    name = "wowi"

    def resolve(self, ref: str, flavor: str = "") -> AddonRef | None:
        rid = _normalise_id(ref)
        if not rid:
            return None
        return AddonRef("wowi", rid,
                        f"https://www.wowinterface.com/downloads/info{rid}")

    def latest_version(self, ref: AddonRef) -> str | None:
        try:
            info = _fetch_info(ref.ref)
            return info.get("UIVersion") or info.get("version")
        except HttpError:
            return None

    def download_url(self, ref: AddonRef, flavor: str = "") -> str | None:
        try:
            info = _fetch_info(ref.ref)
            url = info.get("UIDownload") or ""
            return url or None
        except HttpError:
            return None

    def page_url(self, ref: AddonRef) -> str:
        return ref.page_url
