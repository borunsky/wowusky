"""Parser for World of Warcraft addon ``.toc`` (Table-of-Contents) files.

A TOC declares an addon's metadata in a series of ``## Key: Value``
headers at the top of the file. We extract version, title, interface
number, and notes.

Addons sometimes ship multiple TOCs for different flavors (e.g.
``Foo.toc``, ``Foo_TBC.toc``, ``Foo_Mainline.toc``). When a client
flavor is known we prefer the flavor-specific one via
:data:`~wowusky.core.flavors.TOC_SUFFIXES`.
"""

from __future__ import annotations

import contextlib
import os
import re
from pathlib import Path

from wowusky.core.flavors import TOC_SUFFIXES

_VERSION_RX   = re.compile(r'^##\s*Version\s*:\s*(.+)$',   re.IGNORECASE | re.MULTILINE)
_TITLE_RX     = re.compile(r'^##\s*Title\s*:\s*(.+)$',     re.IGNORECASE | re.MULTILINE)
_INTERFACE_RX = re.compile(r'^##\s*Interface\s*:\s*(\d+)', re.IGNORECASE | re.MULTILINE)
_NOTES_RX     = re.compile(r'^##\s*Notes\s*:\s*(.+)$',     re.IGNORECASE | re.MULTILINE)

# WoW colour escapes ``|cFF00FF00 ... |r`` appear in title strings; strip them.
_COLOR_OPEN_RX  = re.compile(r'\|c[0-9a-fA-F]{8}')
_COLOR_CLOSE_RX = re.compile(r'\|r')


def strip_color_codes(s: str | None) -> str | None:
    """Remove ``|cFFxxxxxx`` / ``|r`` colour escapes from a string."""
    if not s:
        return s
    s = _COLOR_OPEN_RX.sub("", s)
    s = _COLOR_CLOSE_RX.sub("", s)
    return s.strip()


def parse_toc_text(content: str) -> dict:
    """Parse the contents of a TOC file (already read as text).

    Returns a dict with the keys we care about. Missing fields are
    simply absent from the dict.
    """
    info: dict = {}
    if (m := _VERSION_RX.search(content)):
        info["version"] = strip_color_codes(m.group(1))
    if (m := _TITLE_RX.search(content)):
        info["title"] = strip_color_codes(m.group(1))
    if (m := _INTERFACE_RX.search(content)):
        with contextlib.suppress(ValueError):
            info["interface"] = int(m.group(1))
    if (m := _NOTES_RX.search(content)):
        info["notes"] = strip_color_codes(m.group(1))
    return info


def parse_toc_file(path: str | Path) -> dict:
    """Read a single TOC file from disk and parse it.

    Returns an empty dict on read failure (never raises).
    """
    try:
        return parse_toc_text(Path(path).read_text(encoding="utf-8", errors="ignore"))
    except OSError:
        return {}


def read_addon_toc(folder_path: str | Path,
                   client_flavor: str | None = None) -> dict:
    """Find and parse the best TOC inside an addon folder.

    Strategy:

      1. List all ``*.toc`` files in the folder.
      2. If ``client_flavor`` is known, prefer files whose name matches
         any suffix from :data:`TOC_SUFFIXES` for that flavor.
      3. Otherwise pick the shortest filename (= the base TOC).

    Returns an empty dict if the folder has no TOCs or is unreadable.
    """
    folder = Path(folder_path)
    try:
        toc_files = [f for f in os.listdir(folder)
                     if f.lower().endswith(".toc")]
    except OSError:
        return {}
    if not toc_files:
        return {}

    if client_flavor and client_flavor in TOC_SUFFIXES:
        for suf in TOC_SUFFIXES[client_flavor]:
            for tf in toc_files:
                if suf.lower() in tf.lower():
                    return parse_toc_file(folder / tf)

    toc_files.sort(key=len)
    return parse_toc_file(folder / toc_files[0])
