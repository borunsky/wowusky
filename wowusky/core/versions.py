"""Version-string handling.

Provider version strings come in many shapes (``v1.2.3``, ``15.13``,
``2024-03-01``, ``r12345``). For comparison we normalise them: strip a
leading ``v`` and lowercase. For natural sorting we split into numeric
chunks so ``1.10`` sorts after ``1.9``.
"""

from __future__ import annotations

import re
from typing import Any


def normalise_version(value: Any) -> str:
    """Lower-case the value and strip a leading ``v``.

    Returns ``""`` for ``None`` so callers can compare safely.
    """
    if value is None:
        return ""
    return str(value).strip().lower().lstrip("v")


def versions_equal(a: Any, b: Any) -> bool:
    """Compare two version strings after normalisation."""
    return normalise_version(a) == normalise_version(b)


def version_tokens(value: Any) -> list:
    """Split a version string into chunks for natural sorting.

    >>> version_tokens("v1.10.2")
    [1, '.', 10, '.', 2]
    """
    return [int(x) if x.isdigit() else x
            for x in re.split(r'([0-9]+)', normalise_version(value)) if x]


def version_sort_key(value: Any) -> tuple:
    """Return a tuple usable as a ``sorted(..., key=...)`` key."""
    return tuple(version_tokens(value))
