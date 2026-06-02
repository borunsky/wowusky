"""Modal dialogs for the wowusky GUI.

Like the tab classes, each dialog is extracted out of the historic
``app.py`` into a small class that accepts an
:class:`~wowusky.gui.context.AppContext` plus injected callbacks for the
config / profile / provider operations it performs.
"""

from .addon_details import AddonDetailsDialog
from .settings import SettingsDialog

__all__ = ["AddonDetailsDialog", "SettingsDialog"]
