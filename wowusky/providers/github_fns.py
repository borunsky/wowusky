"""GitHub provider — function-based implementation.

The GitHub provider functions, extracted verbatim from app.py during
the v0.5 provider extraction (Etappe A). Behaviour is pinned by
tests/test_characterize_providers.py — 19 tests covering releases,
tags, branch probing (the B2 fix), asset picking and the
repo_by_flavor logic.

Note: github_version_choices() (used by the version-selection dialog
in the GUI) is NOT a provider function and stays in app.py — it is
GUI-specific code that happens to call the GitHub API.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request

from wowusky import APP_NAME, __version__
from wowusky.core.http import get_json as http_get_json


def get_current_flavor():
    """Imported back from app.py at runtime — see below."""
    raise NotImplementedError  # filled in by app.py


def github_repo_for_addon(addon):
    """Return the best GitHub repository for the currently selected WoW flavor.
    Some addons keep Classic/TBC/Retail packages in different repositories.
    repo_by_flavor keeps links and downloads flavor-aware without duplicating
    addon cards.
    """
    if isinstance(addon, dict):
        flavor = get_current_flavor() or "retail"
        by_flavor = addon.get("repo_by_flavor") or {}
        for key in (flavor, "anniversary" if flavor == "anniversary" else None, "retail", "default"):
            if key and by_flavor.get(key):
                return by_flavor[key]
        return addon.get("repo", "")
    return str(addon or "")


def github_repo_url(repo):
    return f"https://github.com/{repo}"


def github_releases(repo):
    """Return releases with fallbacks. Many WoW addons do not expose /latest."""
    try:
        latest = http_get_json(f"https://api.github.com/repos/{repo}/releases/latest")
        if latest:
            return [latest]
    except Exception:
        pass
    try:
        rels = http_get_json(f"https://api.github.com/repos/{repo}/releases?per_page=10")
        if isinstance(rels, list):
            return rels
    except Exception:
        pass
    return []


def github_tags(repo):
    try:
        tags = http_get_json(f"https://api.github.com/repos/{repo}/tags?per_page=10")
        return tags if isinstance(tags, list) else []
    except Exception:
        return []


def github_default_branch(repo):
    try:
        data = http_get_json(f"https://api.github.com/repos/{repo}")
        branch = data.get("default_branch")
        if branch:
            return branch
    except Exception:
        pass
    # The GitHub API failed (commonly: unauthenticated rate limit, 60
    # req/h per IP). Do NOT blindly assume "main" — many WoW addon
    # repos still use "master", which produced 404s on download (B2).
    # Probe the actual archive URLs and use whichever branch exists.
    for candidate in ("main", "master"):
        if _github_branch_exists(repo, candidate):
            return candidate
    return "main"


def _github_branch_exists(repo, branch):
    """Return True if the branch archive URL is reachable (no download)."""
    url = f"https://github.com/{repo}/archive/refs/heads/{branch}.zip"
    try:
        req = urllib.request.Request(
            url, method="HEAD",
            headers={"User-Agent": f"{APP_NAME}/{__version__}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= getattr(resp, "status", 200) < 400
    except urllib.error.HTTPError:
        return False
    except Exception:
        # Network error rather than a definitive 404 — don't claim the
        # branch is missing, let the caller fall back to its default.
        return True


def github_version(a):
    repo = github_repo_for_addon(a)
    rels = github_releases(repo)
    if rels:
        tag = rels[0].get("tag_name") or rels[0].get("name")
        if tag:
            return str(tag).lstrip("v")
    tags = github_tags(repo)
    if tags:
        return str(tags[0].get("name", "?")).lstrip("v")
    branch = github_default_branch(repo)
    return f"{branch} snapshot"


def _github_pick_asset(assets):
    assets = [x for x in assets
              if x.get("name", "").lower().endswith(".zip")
              and "nolib" not in x.get("name", "").lower()
              and "source code" not in x.get("name", "").lower()]
    if not assets:
        return None
    flavor = get_current_flavor()
    flavor_hints = {
        "anniversary": ["tbc", "bcc", "anniversary", "classic"],
        "vanilla":     ["classic", "vanilla", "era", "sod"],
        "mop_classic": ["mists", "mop", "classic"],
        "retail":      ["mainline", "retail"],
    }
    if flavor and flavor in flavor_hints:
        for hint in flavor_hints[flavor]:
            matches = [a for a in assets if hint in a.get("name", "").lower()]
            if matches:
                matches.sort(key=lambda x: x.get("size", 0), reverse=True)
                return matches[0]
    assets.sort(key=lambda x: x.get("size", 0), reverse=True)
    return assets[0]


def github_url(a):
    repo = github_repo_for_addon(a)
    for rel in github_releases(repo):
        asset = _github_pick_asset(rel.get("assets", []))
        if asset and asset.get("browser_download_url"):
            return asset["browser_download_url"]
        if rel.get("zipball_url"):
            return rel["zipball_url"]
    tags = github_tags(repo)
    if tags:
        name = tags[0].get("name")
        if name:
            return f"https://github.com/{repo}/archive/refs/tags/{urllib.parse.quote(name)}.zip"
    branch = github_default_branch(repo)
    return f"https://github.com/{repo}/archive/refs/heads/{urllib.parse.quote(branch)}.zip"
