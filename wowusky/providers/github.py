"""GitHub releases provider.

Delegates to :mod:`wowusky.providers.github_fns` for all network logic
so that the class-based AddonProvider API used by health_check and the
function-based API used by the GUI share a single implementation.
"""

from __future__ import annotations

from .base import AddonRef
from .github_fns import (
    FLAVOR_HINTS,
    _github_branch_exists,
    github_default_branch,
    github_releases,
    github_tags,
    github_url,
    github_version,
    pick_asset,
)

__all__ = [
    "GitHubProvider",
    "pick_asset",
    "FLAVOR_HINTS",
    # Legacy names kept for any callers that imported them from here.
    "_github_branch_exists",
    "github_default_branch",
    "github_releases",
    "github_tags",
]


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
        addon = {"repo": ref.ref}
        v = github_version(addon)
        # "main snapshot" / "master snapshot" → valid, not None
        return v if v else None

    # ── download URL ──────────────────────────────────────────────────

    def download_url(self, ref: AddonRef, flavor: str = "") -> str | None:
        return github_url({"repo": ref.ref}) or None

    def page_url(self, ref: AddonRef) -> str:
        return ref.page_url or f"https://github.com/{ref.ref}"
