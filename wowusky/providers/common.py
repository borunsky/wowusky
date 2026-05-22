"""Shared helpers for provider modules.

Each provider in :mod:`wowusky.providers` needs the same small set of
HTTP primitives (cached JSON GET, streaming download, retry wrapper,
shared error type). Rather than have every provider import directly
from :mod:`wowusky.core.http`, we expose them here so that:

  * the import surface for new providers is a single line
    (``from .common import HttpError, get_json``),
  * provider-specific helpers (URL builders, asset filters, etc.)
    that grow out of multiple providers have an obvious home,
  * the underlying HTTP layer can be swapped or augmented without
    touching every provider file.

This module intentionally contains no logic of its own — it is a
re-export shim. Add genuinely shared provider helpers here as they
emerge, not before.
"""

from __future__ import annotations

from wowusky.core.http import (
    USER_AGENT,
    HttpError,
    clear_cache,
    download,
    get_json,
    retry,
)

__all__ = [
    "USER_AGENT",
    "HttpError",
    "clear_cache",
    "download",
    "get_json",
    "retry",
]
