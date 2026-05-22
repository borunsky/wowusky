"""WoW flavor (client version) definitions and compatibility rules.

A *flavor* is one specific WoW client (Retail, TBC Anniversary, Classic
Era, MoP Classic, PTRs). Each one has:

  * a directory marker like ``_anniversary_`` that appears inside the
    WoW install path,
  * a stable short key (``anniversary``, ``vanilla``, …) used in code,
  * an interface number (the value seen in ``## Interface:`` lines of
    TOC files),
  * a human-friendly display name.

Addons declare compatible flavors via a ``flavors`` list (``"all"``
means "every flavor"). The :func:`is_compatible` helper applies the
:data:`FLAVOR_COMPATIBILITY` map so e.g. the TBC Anniversary client
also picks up plain Classic addons that the developer never explicitly
tagged as TBC.

The :func:`flavor_for_directory` helper inspects a path string and
returns the detected flavor key, used during WoW-install scanning.
"""

from __future__ import annotations

from collections.abc import Iterable

# Directory marker → (display name, key, interface number)
WOW_FLAVORS: dict[str, tuple[str, str, int]] = {
    "_anniversary_": ("TBC Anniversary",    "anniversary",  20505),
    "_classic_era_": ("Classic Era / SoD",  "vanilla",      11508),
    "_classic_":     ("MoP Classic",        "mop_classic",  50503),
    "_retail_":      ("Retail",             "retail",       120001),
    "_ptr_":         ("PTR",                "ptr",          120001),
    "_xptr_":        ("PTR 2",              "ptr",          120001),
}

# Client flavor key → addon-flavor tags accepted on that client.
FLAVOR_COMPATIBILITY: dict[str, list[str]] = {
    "anniversary":  ["anniversary", "tbc", "bcc", "vanilla", "classic"],
    "vanilla":      ["vanilla", "classic", "era"],
    "mop_classic":  ["mop_classic", "mop", "mists", "classic"],
    "retail":       ["retail", "mainline"],
    "ptr":          ["retail", "mainline", "ptr"],
}

# TOC filename suffixes indicating flavor-specific TOC variants.
# An addon may ship Foo.toc, Foo_TBC.toc, Foo_Mainline.toc — we prefer
# the variant matching the active flavor when scanning installed addons.
TOC_SUFFIXES: dict[str, list[str]] = {
    "anniversary": ["_TBC", "_BCC", "-TBC", "-BCC", "_Anniversary"],
    "vanilla":     ["_Vanilla", "_Classic", "-Classic", "-Vanilla"],
    "mop_classic": ["_Mists", "_MoP", "-Mists", "-MoP", "_Classic"],
    "retail":      ["_Mainline", "-Mainline"],
    "ptr":         ["_Mainline", "-Mainline"],
}


def is_compatible(addon_flavors: Iterable[str],
                  current_flavor: str | None) -> bool:
    """Return True if an addon's declared flavors include one the client accepts.

    The special tag ``"all"`` always matches. If ``current_flavor`` is
    ``None`` (no profile selected yet), we return True so the UI can
    still show the catalog.
    """
    if not current_flavor:
        return True
    if "all" in addon_flavors:
        return True
    compat = FLAVOR_COMPATIBILITY.get(current_flavor, [current_flavor])
    return any(f in compat for f in addon_flavors)


def flavor_for_directory(path: str) -> str | None:
    """Detect the flavor key from a path containing a ``_flavor_`` marker.

    >>> flavor_for_directory("/games/WoW/_anniversary_/Interface/AddOns")
    'anniversary'

    Returns ``None`` if no marker is present.
    """
    for marker, (_name, key, _iface) in WOW_FLAVORS.items():
        if marker in path:
            return key
    return None


def flavor_display_name(key: str) -> str:
    """Return the user-facing name of a flavor key, or the key itself."""
    for _marker, (name, k, _iface) in WOW_FLAVORS.items():
        if k == key:
            return name
    return key


def flavor_interface(key: str) -> int:
    """Return the default ``## Interface:`` value for a flavor key, or 0."""
    for _marker, (_name, k, iface) in WOW_FLAVORS.items():
        if k == key:
            return iface
    return 0
