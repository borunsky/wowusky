"""CurseForge providers (API and browser-based).

There are two flavours here:

  * :class:`CurseForgeProvider` uses the official Eternal API and needs
    an API key (set via Settings or the ``CURSEFORGE_API_KEY`` env var).
    With a key it can resolve numeric mod IDs and fetch the latest file.

  * :class:`CurseForgeWebProvider` is the default zero-config fallback:
    it simply derives the project URL from a slug, lets the user
    download the ZIP from the browser, and then imports it.

We never scrape CurseForge HTML or proxy ZIPs; both providers above
respect Overwolf's API terms.
"""

from __future__ import annotations

import os

from .base import AddonRef
from .common import HttpError, get_json

API_BASE = "https://api.curseforge.com/v1"


def slug_from_ref(ref: str) -> str:
    return (ref or "").rstrip("/").split("/")[-1].strip()


class CurseForgeProvider:
    name = "curseforge"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("CURSEFORGE_API_KEY", "")

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self.api_key} if self.api_key else {}

    def resolve(self, ref: str, flavor: str = "") -> AddonRef | None:
        ref = (ref or "").strip()
        if not ref:
            return None
        if ref.isdigit():
            page = f"https://www.curseforge.com/wow/addons/{ref}"
            return AddonRef("curseforge", ref, page)
        slug = slug_from_ref(ref)
        if not slug:
            return None
        return AddonRef("curseforge", slug,
                        f"https://www.curseforge.com/wow/addons/{slug}")

    def latest_version(self, ref: AddonRef) -> str | None:
        # Only numeric mod IDs are addressable via the public API,
        # and we need a key.
        if not self.api_key or not ref.ref.isdigit():
            return None
        try:
            data = get_json(f"{API_BASE}/mods/{ref.ref}/files",
                            headers=self._headers())
        except HttpError:
            return None
        files = data.get("data", [])
        if not files:
            return None
        files.sort(key=lambda x: x.get("fileDate", ""), reverse=True)
        latest = files[0]
        return latest.get("displayName") or latest.get("fileName")

    def page_url(self, ref: AddonRef) -> str:
        return ref.page_url


class CurseForgeWebProvider:
    """No-API fallback: open the project page so the user can download."""
    name = "curseforge_web"

    def resolve(self, ref: str, flavor: str = "") -> AddonRef | None:
        slug = slug_from_ref(ref)
        if not slug:
            return None
        return AddonRef("curseforge_web", slug,
                        f"https://www.curseforge.com/wow/addons/{slug}")

    def latest_version(self, ref: AddonRef) -> str | None:
        # No way to discover the version without scraping; we leave
        # this to the manual ZIP-import flow.
        return None

    def page_url(self, ref: AddonRef) -> str:
        return ref.page_url
