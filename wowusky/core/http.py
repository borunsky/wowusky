"""HTTP layer with in-memory caching and exponential-backoff retry.

All providers go through these helpers so that:

  * we send a consistent ``User-Agent`` (helps GitHub API rate limits),
  * successful GET responses are cached for a short TTL (saves repeated
    look-ups when the UI re-renders),
  * download streams support optional progress callbacks,
  * transient failures can be retried automatically via :func:`retry`.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from wowusky import __version__

USER_AGENT      = f"wowusky/{__version__}"
DEFAULT_TIMEOUT = 20
CACHE_TTL       = 300  # seconds

# Module-level GET cache: url → (timestamp, payload)
_cache: dict[str, tuple[float, Any]] = {}


class HttpError(Exception):
    """Raised when an HTTP request fails after all retries are exhausted."""


def _open(url: str, headers: dict[str, str] | None = None,
          timeout: int = DEFAULT_TIMEOUT):
    h = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    return urllib.request.urlopen(req, timeout=timeout)


def get_json(url: str, headers: dict[str, str] | None = None,
             timeout: int = DEFAULT_TIMEOUT, cache: bool = True) -> Any:
    """Fetch ``url`` and decode the response body as JSON.

    Successful responses are cached in memory for :data:`CACHE_TTL`
    seconds when ``cache`` is True (the default). Raises
    :class:`HttpError` on network or decoding failure.
    """
    if cache and url in _cache:
        ts, payload = _cache[url]
        if time.time() - ts < CACHE_TTL:
            return payload
    try:
        with _open(url, headers, timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        raise HttpError(f"GET {url} failed: {e}") from e
    if cache:
        _cache[url] = (time.time(), data)
    return data


def download(url: str, dest: str,
             progress: Callable[[int, int], None] | None = None,
             headers: dict[str, str] | None = None,
             timeout: int = 60) -> int:
    """Stream ``url`` into the file at ``dest``.

    The optional ``progress(bytes_done, total_bytes)`` callback is
    invoked while reading. Returns the number of bytes written. Raises
    :class:`HttpError` on failure.
    """
    try:
        with _open(url, headers, timeout) as r:
            total = int(r.headers.get("Content-Length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                while True:
                    chunk = r.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress and total > 0:
                        progress(downloaded, total)
            return downloaded
    except (urllib.error.URLError, OSError) as e:
        raise HttpError(f"download {url} failed: {e}") from e


def retry(fn: Callable[[], Any], attempts: int = 3, delay: float = 0.7,
          exceptions: tuple = (HttpError, urllib.error.URLError, OSError)) -> Any:
    """Call ``fn()`` with exponential backoff. Re-raises the last error."""
    last_exc: BaseException | None = None
    for i in range(attempts):
        try:
            return fn()
        except exceptions as e:
            last_exc = e
            if i < attempts - 1:
                time.sleep(delay * (2 ** i))
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("retry: no attempts made")


def clear_cache() -> None:
    """Empty the response cache (used by tests and the Settings 'refresh')."""
    _cache.clear()
