"""Tab classes for the wowusky GUI.

Each tab is being incrementally extracted out of the historic ``run_gui()``
closure into a small class that accepts an :class:`~wowusky.gui.context.AppContext`
and builds its own frame.  :class:`LogTab` was the first; :class:`BackupsTab`
follows the same pattern with injected action callbacks.
"""

from .backups import BackupsTab
from .browse import BrowseTab
from .installed import InstalledTab
from .log import LogTab
from .weakauras import WeakAurasTab

__all__ = ["BackupsTab", "BrowseTab", "InstalledTab", "LogTab", "WeakAurasTab"]
