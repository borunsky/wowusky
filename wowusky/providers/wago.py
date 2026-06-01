"""Wago.io provider for WeakAura tracking.

Delegates to :mod:`wowusky.providers.wago_fns` for network logic.
"""

from __future__ import annotations

import re

from .base import AddonRef
from .wago_fns import wago_fetch_info

WAGO_RE = re.compile(r'wago\.io/([A-Za-z0-9_-]+)')


class WagoProvider:
    name = "wago"

    def resolve(self, ref: str, flavor: str = "") -> AddonRef | None:
        m = WAGO_RE.search(ref or "")
        slug = m.group(1) if m else (ref or "").strip()
        if not slug:
            return None
        return AddonRef("wago", slug, f"https://wago.io/{slug}")

    def latest_version(self, ref: AddonRef) -> str | None:
        data = wago_fetch_info(ref.ref) or {}
        v = data.get("version") or data.get("wagoVersion")
        return str(v) if v is not None else None

    def page_url(self, ref: AddonRef) -> str:
        return ref.page_url
