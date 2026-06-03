"""Entry point: ``python -m wowusky``.

We bootstrap ``sys.path`` defensively so that ``python -m wowusky`` works
no matter which directory the user is in. The two failure modes we
guard against:

  * The user runs ``python -m wowusky`` from *inside* the ``wowusky/``
    package directory itself. In that case Python puts the package
    directory on ``sys.path`` instead of its parent, and imports like
    ``from wowusky.catalog import ...`` fail with ``ModuleNotFoundError``.
  * The user runs ``python3 wowusky/__main__.py`` directly. Same problem.

The fix is to detect either case and prepend the real parent of the
``wowusky`` package to ``sys.path`` before the first internal import.
"""

from __future__ import annotations

import os
import sys


def _ensure_package_on_path() -> None:
    here = os.path.dirname(os.path.abspath(__file__))   # .../wowusky
    parent = os.path.dirname(here)                       # .../  (contains 'wowusky')
    if parent and parent not in sys.path:
        sys.path.insert(0, parent)


_ensure_package_on_path()

# Dispatch: CLI when arguments are given, GUI/terminal otherwise.
_CLI_COMMANDS = {
    "install", "uninstall", "update", "status",
    "search", "orphans", "import", "profile", "set", "version", "help",
    "backup", "rollback", "weakauras", "wa", "completion",
    "--help", "-h", "--version",
}

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in _CLI_COMMANDS:
        from wowusky.cli import run_cli  # noqa: E402
        run_cli()
    else:
        from wowusky.app import main  # noqa: E402
        main()
