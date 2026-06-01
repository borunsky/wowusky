"""GUI layer for wowusky.

The Tk interface is being incrementally extracted out of the historic
``app.py`` monolith into this package. Self-contained pieces (theme
palettes, reusable widgets) live here; the large ``run_gui`` builder and
its tab closures are migrated in later stages.
"""

from .context import AppContext
from .fonts import make_font_set, resolve_mono_family, resolve_sans_family
from .theme import (
    PALETTE_DARK,
    PALETTE_LIGHT,
    detect_system_theme,
    get_palette,
    set_theme_mode,
)
from .widgets import HoverScrollbar, UltraHiddenScrollbar, _safe_grab, make_button

__all__ = [
    "AppContext",
    "PALETTE_DARK",
    "PALETTE_LIGHT",
    "detect_system_theme",
    "get_palette",
    "set_theme_mode",
    "UltraHiddenScrollbar",
    "HoverScrollbar",
    "_safe_grab",
    "make_button",
    "resolve_sans_family",
    "resolve_mono_family",
    "make_font_set",
]
