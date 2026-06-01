"""Tukui provider for ElvUI and Tukui via api.tukui.org.

Delegates to :mod:`wowusky.providers.tukui_fns` for network logic.
"""

from __future__ import annotations

from .base import AddonRef
from .tukui_fns import tukui_url, tukui_version

KNOWN_SLUGS = {"elvui", "tukui"}
API = "https://api.tukui.org/v1/addon"
DOWNLOAD = "https://api.tukui.org/v1/download/dev"


class TukuiProvider:
    name = "tukui"

    def resolve(self, ref: str, flavor: str = "") -> AddonRef | None:
        slug = (ref or "").strip().lower()
        slug = slug.replace("https://www.tukui.org/addons.php?id=", "")
        slug = slug.rstrip("/").split("/")[-1]
        if slug not in KNOWN_SLUGS:
            return None
        return AddonRef("tukui", slug, f"https://tukui.org/{slug}")

    def _entry(self, ref: AddonRef) -> dict:
        """Build the dict shape that tukui_fns expects."""
        slug = ref.ref
        return {
            "api_url":      f"{API}/{slug}",
            "download_url": f"{DOWNLOAD}/{slug}/main",
        }

    def latest_version(self, ref: AddonRef) -> str | None:
        v = tukui_version(self._entry(ref))
        return v if v and v != "?" else None

    def download_url(self, ref: AddonRef, flavor: str = "") -> str | None:
        return tukui_url(self._entry(ref)) or None

    def page_url(self, ref: AddonRef) -> str:
        return ref.page_url
