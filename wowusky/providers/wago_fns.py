"""Wago.io provider — function-based implementation.

The pure provider functions for wago.io, extracted verbatim from
app.py during the v0.5 provider extraction (Etappe A). Behaviour is
pinned by tests/test_characterize_providers.py.

Note: the stateful Wago helpers (wago_add, wago_remove,
wago_check_updates, wago_search) deliberately stay in app.py — they
manage the local tracking file and belong to a later persistence
stage, not provider extraction.
"""

from __future__ import annotations

import json
import re

from wowusky.core.http import _open as _http
from wowusky.core.http import get_json as http_get_json

WAGO_SLUG_RX = re.compile(r'wago\.io/([a-zA-Z0-9_-]+)(?:/(\d+))?')


def parse_wago_url(url):
    """Extracts slug and optional version from a wago.io URL."""
    m = WAGO_SLUG_RX.search(url)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def wago_fetch_info(slug):
    """Fetch WeakAura metadata from wago.io API."""
    try:
        url = f"https://data.wago.io/api/raw/encoded?id={slug}"
        with _http(url) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data
    except Exception:
        # Try alternate endpoint
        try:
            url = f"https://data.wago.io/api/check/?id={slug}"
            return http_get_json(url)
        except Exception:
            return None


def wago_fetch_encoded(slug, version=None):
    """Fetch the actual import string."""
    try:
        url = f"https://data.wago.io/api/raw/encoded?id={slug}"
        if version:
            url += f"&version={version}"
        with _http(url) as r:
            return r.read().decode("utf-8")
    except Exception:
        return None
