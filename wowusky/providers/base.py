"""Provider abstraction.

A *provider* knows how to talk to one source of addons — Tukui's API,
GitHub releases, WoWInterface, CurseForge, Wago. Every provider
exposes the same minimal interface so the rest of the application can
treat them uniformly.

Each provider:

  * ``resolve(ref, flavor)`` turns a slug / URL / repo identifier into
    a normalised :class:`AddonRef`,
  * ``latest_version(ref)`` fetches the current version string
    (or ``None`` if unavailable),
  * ``page_url(ref)`` returns a browser URL for manual fallback,
  * ``download_url(ref)`` (optional) returns a direct ZIP URL when one
    is known and free to use.

Providers that can't offer a direct download (CurseForge without API
key, WoWInterface CDN throttling, …) are *semi-managed*: the
application opens ``page_url`` in the browser instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class AddonRef:
    """A reference to a specific addon at a specific source.

    Different providers use different identifiers; the ``ref`` field
    stores whichever string is canonical for that provider (owner/repo,
    slug, numeric id, …). ``page_url`` is the human-readable URL for
    the addon, set during :meth:`AddonProvider.resolve`.
    """
    source: str
    ref: str
    page_url: str = ""


class AddonProvider(Protocol):
    """Every provider implements at least the first three methods.

    ``download_url`` is optional — the application falls back to
    opening :meth:`page_url` if it's missing or returns ``None``.
    """
    name: str

    def resolve(self, ref: str, flavor: str = "") -> AddonRef | None: ...
    def latest_version(self, ref: AddonRef) -> str | None: ...
    def page_url(self, ref: AddonRef) -> str: ...
