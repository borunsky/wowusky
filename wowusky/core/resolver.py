"""Provider resolution helpers — manual-download URLs + page/label dispatch.

This module owns the flavor-aware URL building for CurseForge's website
(search and file listings) and the small dispatch helpers that map an
addon's ``source`` to a provider page URL and an action-button label.

Everything here is parameterised by the active WoW ``flavor`` (passed in
by the caller) and imports the pure provider helpers directly from
:mod:`wowusky.providers`, so it carries no GUI, config, or profile
coupling. ``app.py`` keeps thin wrappers that supply ``get_current_flavor()``.
"""

from __future__ import annotations

import urllib.parse

from wowusky.providers.curseforge_fns import (
    cf_slug_from_ref,
)
from wowusky.providers.curseforge_fns import (
    curseforge_manual_url as _cf_manual_url,
)
from wowusky.providers.github_fns import github_repo_for_addon, github_repo_url
from wowusky.providers.wowi_fns import wowi_page_url

# CurseForge web URLs use gameVersionTypeId. 67408 currently opens the
# Classic flavor listing; for TBC Anniversary we also seed the query with
# TBC terms so the browser starts in the correct area even when CF changes
# the exact flavor id again.
CF_WEB_VERSION_TYPE_HINTS = {
    "retail": 517,
    "ptr": 517,
    "anniversary": 67408,
    "vanilla": 67408,
    "mop_classic": 73246,
}

CF_WEB_SEARCH_HINT = {
    "anniversary": "tbc classic anniversary",
    "vanilla": "classic era",
    "mop_classic": "mop classic",
    "retail": "",
    "ptr": "",
}

SEMI_MANAGED_SOURCES = {"curseforge_web", "curseforge_manual", "wowi"}


def cf_web_version_type(flavor):
    """The CurseForge gameVersionTypeId for a flavor (retail fallback)."""
    return CF_WEB_VERSION_TYPE_HINTS.get(flavor or "retail")


def curseforge_search_url(query="", flavor=None):
    """Build a CurseForge website search URL seeded for the given flavor."""
    q = (query or "").strip()
    slug = cf_slug_from_ref(q)
    if slug and ("/" in q or "curseforge.com" in q):
        return "https://www.curseforge.com/wow/addons/" + urllib.parse.quote(slug)

    flavor = flavor or "retail"
    params = {"class": "addons", "page": 1, "sortBy": "popularity"}
    vt = cf_web_version_type(flavor)
    if vt:
        params["gameVersionTypeId"] = vt

    hint = CF_WEB_SEARCH_HINT.get(flavor, "")
    search = " ".join(x for x in (q, hint) if x).strip()
    if search:
        params["search"] = search

    return "https://www.curseforge.com/wow/search?" + urllib.parse.urlencode(params)


def curseforge_files_url(slug_or_url="", flavor=None):
    """Build the 'files/all' page URL for a CurseForge addon ref."""
    slug = cf_slug_from_ref(slug_or_url)
    if slug:
        return f"https://www.curseforge.com/wow/addons/{urllib.parse.quote(slug)}/files/all"
    return curseforge_search_url(slug_or_url, flavor)


def curseforge_manual_url(entry, flavor=None):
    """Resolve the manual-update URL for an installed CurseForge entry."""
    return _cf_manual_url(
        entry,
        files_url_fn=lambda s="": curseforge_files_url(s, flavor),
        search_url_fn=lambda q="": curseforge_search_url(q, flavor),
    )


def addon_provider_page(addon, flavor=None):
    """The best 'open in provider' URL for an addon, by source."""
    src = addon.get("source")
    if src == "curseforge_web":
        return curseforge_files_url(addon.get("curseforge_slug", addon.get("id", "")), flavor)
    if src == "curseforge_manual":
        return curseforge_manual_url(addon, flavor)
    if src == "wowi":
        return wowi_page_url(addon)
    if src == "github":
        return github_repo_url(github_repo_for_addon(addon))
    if src == "tukui":
        return addon.get("download_url") or addon.get("api_url")
    return addon.get("url") or ""


def provider_action_label(addon, installed=False):
    """Label for the addon's primary action button, by source."""
    src = addon.get("source")
    if src == "curseforge_web":
        return "Open CF"
    if src == "curseforge_manual":
        return "Open update"
    return "Install" if not installed else "Update"
