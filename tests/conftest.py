"""Shared pytest fixtures for the wowusky test suite."""

import pytest


@pytest.fixture(autouse=True)
def _suppress_tk_dialogs(monkeypatch):
    """Stop real Tk modal dialogs from blocking the test run.

    Several GUI code paths call ``tkinter.messagebox.*`` on validation
    errors (e.g. ``ImportTab._install`` shows "Please select a valid ZIP
    file." when no file is chosen). With a real display — for example a
    packaging sandbox running ``makepkg``'s ``check()`` on a desktop — those
    calls pop a modal dialog that blocks the build forever waiting for a
    click. Replace them with no-ops (and auto-confirm prompts) so the tests
    stay fully non-interactive regardless of whether a display is present.

    On a headless machine where ``tkinter`` is unavailable the GUI tests
    skip anyway, so importing the module is best-effort.
    """
    try:
        import tkinter.messagebox as mb
    except Exception:
        return

    for name in ("showerror", "showinfo", "showwarning"):
        monkeypatch.setattr(mb, name, lambda *a, **k: None, raising=False)
    for name in ("askyesno", "askokcancel", "askretrycancel"):
        monkeypatch.setattr(mb, name, lambda *a, **k: True, raising=False)
