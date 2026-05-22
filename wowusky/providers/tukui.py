"""Tukui provider for ElvUI and Tukui via api.tukui.org."""

from __future__ import annotations

from .base import AddonRef
from .common import HttpError, get_json

KNOWN_SLUGS = {"elvui", "tukui"}
API = "https://api.tukui.org/v1/addon"


class TukuiProvider:
    name = "tukui"

    def resolve(self, ref: str, flavor: str = "") -> AddonRef | None:
        slug = (ref or "").strip().lower()
        # Accept short slugs and the legacy addons.php?id=... URLs
        slug = slug.replace("https://www.tukui.org/addons.php?id=", "")
        slug = slug.rstrip("/").split("/")[-1]
        if slug not in KNOWN_SLUGS:
            return None
        return AddonRef("tukui", slug, f"https://tukui.org/{slug}")

    def latest_version(self, ref: AddonRef) -> str | None:
        try:
            data = get_json(f"{API}/{ref.ref}")
            return data.get("version")
        except HttpError:
            return None

    def download_url(self, ref: AddonRef, flavor: str = "") -> str | None:
        # tukui's stable download endpoint:
        return f"https://api.tukui.org/v1/download/dev/{ref.ref}/main"

    def page_url(self, ref: AddonRef) -> str:
        return ref.page_url
