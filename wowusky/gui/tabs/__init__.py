"""Tab classes for the wowusky GUI.

Each tab is being incrementally extracted out of the historic ``run_gui()``
closure into a small class that accepts an :class:`~wowusky.gui.context.AppContext`
and builds its own frame.  The first to land is :class:`LogTab`.
"""

from .log import LogTab

__all__ = ["LogTab"]
