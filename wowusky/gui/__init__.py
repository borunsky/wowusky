"""GUI layer for wowusky.

The Tk interface is being incrementally extracted out of the historic
``app.py`` monolith into this package. Self-contained pieces (theme
palettes, reusable widgets) live here; the large ``run_gui`` builder and
its tab closures are migrated in later stages.
"""

from .theme import (
    PALETTE_DARK,
    PALETTE_LIGHT,
    detect_system_theme,
    get_palette,
    set_theme_mode,
)
from .widgets import HoverScrollbar, UltraHiddenScrollbar

__all__ = [
    "PALETTE_DARK",
    "PALETTE_LIGHT",
    "detect_system_theme",
    "get_palette",
    "set_theme_mode",
    "UltraHiddenScrollbar",
    "HoverScrollbar",
]
