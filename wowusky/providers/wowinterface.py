"""WoWInterface provider via the MMOUI JSON API.

Delegates to :mod:`wowusky.providers.wowi_fns` for all network logic.
"""

from __future__ import annotations

from .base import AddonRef
from .wowi_fns import wowi_url, wowi_version


def _normalise_id(ref: str) -> str:
    return "".join(ch for ch in (ref or "") if ch.isdigit())


class WoWInterfaceProvider:
    name = "wowi"

    def resolve(self, ref: str, flavor: str = "") -> AddonRef | None:
        rid = _normalise_id(ref)
        if not rid:
            return None
        return AddonRef("wowi", rid,
                        f"https://www.wowinterface.com/downloads/info{rid}")

    def latest_version(self, ref: AddonRef) -> str | None:
        addon = {"wowi_id": ref.ref}
        v = wowi_version(addon)
        # "manual" = no API version available, but the addon entry is valid
        return v if v else None

    def download_url(self, ref: AddonRef, flavor: str = "") -> str | None:
        url = wowi_url({"wowi_id": ref.ref})
        return url or None

    def page_url(self, ref: AddonRef) -> str:
        return ref.page_url
