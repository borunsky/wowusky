"""AppContext — shared GUI state passed to all GUI components.

Bundles palette, font-set, root window and lightweight mutable state so
future tab classes can accept a single ``ctx: AppContext`` argument instead
of capturing dozens of locals from the ``run_gui()`` closure.

Construction happens inside ``run_gui()`` after Tk is initialised.  The type
of ``root`` is ``Any`` so this module stays importable without a running Tk
display (useful for tests).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any


@dataclasses.dataclass
class AppContext:
    """Shared state for the wowusky GUI session."""

    # Theme
    palette: dict
    theme_mode: str

    # Typography
    sans_family: str
    mono_family: str
    fonts: dict  # make_font_set() output — keyed by FONT_* names

    # Tk root (Any to avoid importing tkinter at module level)
    root: Any

    # Convenience factories / callbacks
    make_button: Callable
    app_log: Callable

    # Lightweight mutable state shared across tabs
    version_cache: dict = dataclasses.field(default_factory=dict)
    checking_versions: list = dataclasses.field(default_factory=lambda: [False])

    # ------------------------------------------------------------------
    # Font shortcuts — avoid ctx.fonts["FONT_SM"] boilerplate in tab code
    # ------------------------------------------------------------------

    @property
    def C(self) -> dict:
        """Alias for palette (matches the historic ``C`` local in run_gui)."""
        return self.palette

    @property
    def font_sm(self) -> tuple:
        return self.fonts["FONT_SM"]

    @property
    def font_body(self) -> tuple:
        return self.fonts["FONT_BODY"]

    @property
    def font_head(self) -> tuple:
        return self.fonts["FONT_HEAD"]

    @property
    def font_logo(self) -> tuple:
        return self.fonts["FONT_LOGO"]

    @property
    def font_section(self) -> tuple:
        return self.fonts["FONT_SECTION"]

    @property
    def font_xs(self) -> tuple:
        return self.fonts["FONT_XS"]

    @property
    def font_name(self) -> tuple:
        return self.fonts["FONT_NAME"]

    @property
    def font_mono(self) -> tuple:
        return self.fonts["FONT_MONO"]
