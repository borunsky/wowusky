"""ZIP utilities for addon installation.

GitHub ``Source code.zip`` files wrap everything in a single top-level
directory like ``WeakAuras2-5.18.0/``. Without handling that wrapper
the addon would end up at ``Interface/AddOns/WeakAuras2-5.18.0/`` and
the game would not load it.

:func:`smart_extract` detects this case and unpacks the contents into
the AddOns folder under the correct addon name. It also handles the
common "wrapper contains multiple addon folders" pattern.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import zipfile
from pathlib import Path


def sha256_of_file(path: str | Path) -> str:
    """Return the SHA-256 hex digest of a file (streamed in 64 KiB chunks)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_file(path: str | Path) -> str:
    """Alias for :func:`sha256_of_file` (name used by the GUI install path)."""
    return sha256_of_file(path)


def _find_toc_dirs(root: str) -> list[str]:
    """Return every directory under *root* that holds a ``.toc`` file.

    Nested library folders are dropped when an ancestor already has a
    TOC, so wrapper / ``release`` layouts unpack to the real addon roots.
    """
    found = []
    for path, _dirs, files in os.walk(root):
        if any(f.lower().endswith(".toc") for f in files):
            found.append(path)
    found = sorted(found, key=lambda p: (p.count(os.sep), p.lower()))
    filtered: list[str] = []
    for p in found:
        if not any(p.startswith(parent + os.sep) for parent in filtered):
            filtered.append(p)
    return filtered


def _copy_addon_dir(src: str, addons_path: str | Path) -> str:
    """Copy a single addon directory into *addons_path*, replacing any
    existing folder of the same name. Returns the placed folder name."""
    name = os.path.basename(src.rstrip(os.sep))
    dst = os.path.join(str(addons_path), name)
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return name


def extract_addon_zip(zip_path: str | Path, addons_path: str | Path) -> list[str]:
    """Extract an addon ZIP into *addons_path* and return the folder names.

    Handles ZIPs from GitHub, WoWInterface, Tukui, manual imports, and
    CurseForge. The archive is unpacked to a temp dir and searched
    recursively for folders containing ``.toc`` files, so packages with
    wrapper directories or ``release/`` subdirectories work. Falls back to
    top-level directories when no TOC is found, and raises ``RuntimeError``
    if the archive contains no addon folders at all.
    """
    addons_path = str(addons_path)
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp)

        toc_dirs = _find_toc_dirs(tmp)
        if toc_dirs:
            return [_copy_addon_dir(src, addons_path) for src in toc_dirs]

        # Fallback: copy top-level directories if no TOC was found.
        placed = [
            _copy_addon_dir(os.path.join(tmp, item), addons_path)
            for item in os.listdir(tmp)
            if os.path.isdir(os.path.join(tmp, item))
        ]
        if placed:
            return placed

        raise RuntimeError("ZIP does not contain any addon folders or .toc files.")


def _toc_in_top_dir(names: list[str], top: str) -> bool:
    """True if at least one ``*.toc`` sits directly inside ``top/`` (depth 1)."""
    prefix = top + "/"
    for n in names:
        if not n.startswith(prefix):
            continue
        rest = n[len(prefix):]
        if rest and "/" not in rest and rest.lower().endswith(".toc"):
            return True
    return False


def _inner_dirs(names: list[str], top: str) -> list[str]:
    """Direct subdirectories of ``top/``."""
    prefix = top + "/"
    inner: set[str] = set()
    for n in names:
        if not n.startswith(prefix):
            continue
        rest = n[len(prefix):]
        if "/" in rest:
            inner.add(rest.split("/", 1)[0])
    return sorted(inner)


def smart_extract(zip_path: str | Path, addons_path: str | Path,
                  preferred_target_name: str | None = None) -> list[str]:
    """Extract an addon ZIP into ``addons_path``.

    Returns the list of addon folder names that were placed under
    ``addons_path``.

    Detection rules:

      1. Archive has exactly one top-level directory **and** that
         directory contains a ``.toc`` file directly → the wrapper *is*
         the addon. Extract to a temp dir and copy under the preferred
         target name (falling back to the wrapper name).
      2. Archive has exactly one top-level directory containing further
         folders with TOCs → the inner folders are the real addons.
         Extract each one to the AddOns folder.
      3. Otherwise: plain layout, extract as-is.
    """
    addons_path = str(addons_path)
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        top_dirs = {n.split("/", 1)[0] for n in names if "/" in n}
        top_dirs.discard("")

        if len(top_dirs) == 1:
            wrapper = next(iter(top_dirs))
            if _toc_in_top_dir(names, wrapper):
                with tempfile.TemporaryDirectory() as tmp:
                    zf.extractall(tmp)
                    src = os.path.join(tmp, wrapper)
                    target = preferred_target_name or wrapper
                    dst = os.path.join(addons_path, target)
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                    return [target]

            inner = _inner_dirs(names, wrapper)
            if inner:
                with tempfile.TemporaryDirectory() as tmp:
                    zf.extractall(tmp)
                    root = os.path.join(tmp, wrapper)
                    placed: list[str] = []
                    for d in os.listdir(root):
                        src = os.path.join(root, d)
                        if not os.path.isdir(src):
                            continue
                        dst = os.path.join(addons_path, d)
                        if os.path.exists(dst):
                            shutil.rmtree(dst)
                        shutil.copytree(src, dst)
                        placed.append(d)
                    return placed

        zf.extractall(addons_path)
        return [d for d in top_dirs
                if os.path.isdir(os.path.join(addons_path, d))]
