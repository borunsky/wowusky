"""GitHub releases provider.

GitHub is the preferred source for most addons. We try a fallback chain:

  1. ``GET /repos/{repo}/releases/latest`` for the most recent published release,
  2. ``GET /repos/{repo}/releases`` and use the first non-prerelease,
  3. ``GET /repos/{repo}/tags`` for the latest tag,
  4. ``GET /repos/{repo}`` to learn the default branch and download
     ``<branch>.zip`` as a last resort.

Many addon releases ship multiple ZIP variants tagged with the flavor
(``MyAddon-bcc.zip``, ``MyAddon-classic.zip``, ``MyAddon-mainline.zip``).
:func:`pick_asset` chooses the right one for the client flavor.
"""

from __future__ import annotations

from typing import Any

from .base import AddonRef
from .common import HttpError, get_json

API = "https://api.github.com"


class GitHubProvider:
    name = "github"

    # ── resolve ───────────────────────────────────────────────────────

    def resolve(self, ref: str, flavor: str = "") -> AddonRef | None:
        if not ref:
            return None
        ref = ref.strip().replace("https://github.com/", "").strip("/")
        if ref.count("/") < 1:
            return None
        owner, repo = ref.split("/", 2)[:2]
        return AddonRef("github", f"{owner}/{repo}",
                        f"https://github.com/{owner}/{repo}")

    # ── version ───────────────────────────────────────────────────────

    def latest_version(self, ref: AddonRef) -> str | None:
        repo = ref.ref
        try:
            rel = get_json(f"{API}/repos/{repo}/releases/latest")
            return (rel.get("tag_name") or rel.get("name") or "").lstrip("v") or None
        except HttpError:
            pass
        try:
            releases = get_json(f"{API}/repos/{repo}/releases")
            for r in releases or []:
                if r.get("prerelease"):
                    continue
                return (r.get("tag_name") or r.get("name") or "").lstrip("v") or None
        except HttpError:
            pass
        try:
            tags = get_json(f"{API}/repos/{repo}/tags")
            if tags:
                return tags[0].get("name", "").lstrip("v") or None
        except HttpError:
            return None
        return None

    # ── download URL ──────────────────────────────────────────────────

    def download_url(self, ref: AddonRef, flavor: str = "") -> str | None:
        """Return the best ZIP URL for ``flavor``, falling back to branch ZIP."""
        repo = ref.ref
        try:
            rel = get_json(f"{API}/repos/{repo}/releases/latest")
            asset = pick_asset(rel.get("assets") or [], flavor)
            if asset:
                return asset["browser_download_url"]
            # source-only release? fall back to zipball
            if rel.get("zipball_url"):
                return rel["zipball_url"]
        except HttpError:
            pass

        try:
            info = get_json(f"{API}/repos/{repo}")
            branch = info.get("default_branch") or "main"
            return f"https://github.com/{repo}/archive/refs/heads/{branch}.zip"
        except HttpError:
            return None

    def page_url(self, ref: AddonRef) -> str:
        return ref.page_url or f"https://github.com/{ref.ref}"


# ── helpers ───────────────────────────────────────────────────────────

# Flavor → keywords commonly seen in release-asset filenames.
_FLAVOR_HINTS = {
    "anniversary": ["bcc", "tbc", "anniversary", "burningcrusade"],
    "vanilla":     ["classic", "vanilla", "era"],
    "mop_classic": ["mists", "mop"],
    "retail":      ["mainline", "retail"],
}


def pick_asset(assets: list[dict[str, Any]], flavor: str = "") -> dict | None:
    """Pick the best ZIP asset from a release.

    Strategy:

      * filter to ``.zip`` files,
      * drop ``nolib``/``no-lib`` packages (they require libraries
        we'd have to resolve separately),
      * if ``flavor`` matches a known hint, prefer assets whose
        filename contains a matching keyword,
      * otherwise pick the largest remaining asset (the most complete
        bundle).
    """
    zips = [a for a in assets
            if a.get("name", "").lower().endswith(".zip")
            and "nolib" not in a.get("name", "").lower()
            and "no-lib" not in a.get("name", "").lower()]
    if not zips:
        return None

    hints = _FLAVOR_HINTS.get(flavor, [])
    if hints:
        for hint in hints:
            matches = [a for a in zips if hint in a["name"].lower()]
            if matches:
                matches.sort(key=lambda a: a.get("size", 0), reverse=True)
                return matches[0]

    zips.sort(key=lambda a: a.get("size", 0), reverse=True)
    return zips[0]
