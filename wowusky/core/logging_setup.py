"""Logging configuration: rotating files + ring buffer for the GUI.

We want three sinks for log output:

  * a rotating file at ``~/.local/share/wowusky/logs/wowusky.log``
    (kept across sessions, useful for bug reports),
  * an in-memory ring buffer that the GUI ``Activity`` tab can read
    from at any time,
  * optionally stderr when running in headless / CLI mode.

The :func:`configure` function wires these up and is idempotent — calling
it more than once is a no-op.
"""

from __future__ import annotations

import contextlib
import logging
import logging.handlers
import sys
from collections import deque
from collections.abc import Callable

from wowusky.core.paths import LOG_DIR, ensure_dirs

_RING: deque[str] = deque(maxlen=2000)
_subscribers: list[Callable[[str], None]] = []
_configured = False


class _RingHandler(logging.Handler):
    """Logger sink that pushes formatted messages into the ring buffer."""
    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        _RING.append(msg)
        for cb in list(_subscribers):
            with contextlib.suppress(Exception):  # never let UI callbacks crash logging
                cb(msg)


def configure(level: int = logging.INFO, also_stderr: bool = False) -> None:
    """Initialise logging (safe to call multiple times)."""
    global _configured
    if _configured:
        return
    ensure_dirs()

    root = logging.getLogger()
    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    fh = logging.handlers.TimedRotatingFileHandler(
        LOG_DIR / "wowusky.log", when="midnight",
        backupCount=7, encoding="utf-8",
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)

    rh = _RingHandler()
    rh.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(rh)

    if also_stderr:
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(fmt)
        root.addHandler(sh)

    _configured = True


def get(name: str) -> logging.Logger:
    """``logging.getLogger(name)`` but ensures :func:`configure` ran first."""
    if not _configured:
        configure()
    return logging.getLogger(name)


def recent(n: int = 200) -> list[str]:
    """Return the last ``n`` formatted log lines from the buffer."""
    return list(_RING)[-n:]


def subscribe(cb: Callable[[str], None]) -> Callable[[], None]:
    """Register a callback for every new log line. Returns an unsubscribe fn."""
    _subscribers.append(cb)
    def _off():
        with contextlib.suppress(ValueError):
            _subscribers.remove(cb)
    return _off
