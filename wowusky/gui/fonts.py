"""Font-family resolution and font-set construction for the wowusky GUI."""

_SANS_CANDIDATES = (
    "Inter", "Segoe UI", "SF Pro Text",
    "DejaVu Sans", "Helvetica", "TkDefaultFont",
)
_MONO_CANDIDATES = (
    "JetBrains Mono", "Fira Code", "Hack",
    "DejaVu Sans Mono", "monospace",
)


def _font_exists(font_name: str) -> bool:
    try:
        import tkinter.font as tkfont
        return font_name in list(tkfont.families())
    except Exception:
        return False


def resolve_sans_family() -> str:
    for candidate in _SANS_CANDIDATES:
        if _font_exists(candidate):
            return candidate
    return "Helvetica"


def resolve_mono_family() -> str:
    for candidate in _MONO_CANDIDATES:
        if _font_exists(candidate) or candidate == "monospace":
            return candidate
    return "monospace"


def make_font_set(sans: str, mono: str) -> dict:
    """Return a dict of named font tuples for the given font families."""
    return {
        "FONT_LOGO":    (sans, 14, "bold"),
        "FONT_HEAD":    (sans, 13, "bold"),
        "FONT_SECTION": (sans, 10, "bold"),
        "FONT_BODY":    (sans, 10),
        "FONT_SM":      (sans, 9),
        "FONT_XS":      (sans, 8),
        "FONT_NAME":    (sans, 11, "bold"),
        "FONT_VER":     (sans, 9),
        "FONT_MONO":    (mono, 9),
    }
