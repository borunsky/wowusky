"""Wago.io provider for WeakAura tracking."""

from __future__ import annotations

import re

from .base import AddonRef
from .common import HttpError, get_json

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
        try:
            data = get_json(f"https://data.wago.io/api/check/?id={ref.ref}")
        except HttpError:
            return None
        v = data.get("version") or data.get("wagoVersion")
        return str(v) if v is not None else None

    def page_url(self, ref: AddonRef) -> str:
        return ref.page_url
