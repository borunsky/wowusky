"""Tukui provider — function-based implementation.

The pure provider functions for Tukui/ElvUI, extracted verbatim from
app.py during the v0.5 provider extraction (Etappe A). Behaviour is
pinned by tests/test_characterize_providers.py.

Note: the catalog-compat reconstruction of api_url/download_url lives
in _load_addon_catalog_with_compat() in app.py and stays there — it is
general catalog logic, not a Tukui provider function.
"""

from __future__ import annotations

from wowusky.core.http import get_json as http_get_json


def tukui_version(a):
    return http_get_json(a["api_url"]).get("version", "?")


def tukui_url(a):
    return a["download_url"]
