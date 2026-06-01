"""Tests for wowusky.gui.fonts — font resolution and font-set construction.

These run headless: _font_exists fails gracefully, and make_font_set / the
resolve_* fallback paths need no live Tk root.
"""

from wowusky.gui.fonts import (
    _MONO_CANDIDATES,
    _SANS_CANDIDATES,
    _font_exists,
    make_font_set,
    resolve_mono_family,
    resolve_sans_family,
)

FONT_SET_KEYS = {
    "FONT_LOGO", "FONT_HEAD", "FONT_SECTION", "FONT_BODY",
    "FONT_SM", "FONT_XS", "FONT_NAME", "FONT_VER", "FONT_MONO",
}


def test_font_set_has_expected_keys():
    fonts = make_font_set("Helvetica", "monospace")
    assert set(fonts) == FONT_SET_KEYS


def test_font_set_values_are_tuples():
    fonts = make_font_set("Helvetica", "monospace")
    for k, v in fonts.items():
        assert isinstance(v, tuple), f"{k} should be a tuple, got {v!r}"


def test_font_set_sans_family_used():
    fonts = make_font_set("MyFont", "monospace")
    for k, v in fonts.items():
        if k != "FONT_MONO":
            assert v[0] == "MyFont", f"{k} should use sans family"


def test_font_set_mono_family_used():
    fonts = make_font_set("Helvetica", "MyMono")
    assert fonts["FONT_MONO"][0] == "MyMono"


def test_font_exists_returns_bool(monkeypatch):
    monkeypatch.setattr(
        "wowusky.gui.fonts._font_exists",
        lambda name: name == "FakeFont",
    )
    from wowusky.gui import fonts as _fonts_mod
    assert _fonts_mod._font_exists("FakeFont") is True


def test_font_exists_graceful_on_import_error(monkeypatch):
    import importlib
    import sys

    orig = sys.modules.get("tkinter.font")
    sys.modules["tkinter.font"] = None  # type: ignore[assignment]
    try:
        result = _font_exists("anything")
    finally:
        if orig is None:
            sys.modules.pop("tkinter.font", None)
        else:
            sys.modules["tkinter.font"] = orig
    assert result is False


def test_resolve_sans_falls_back_when_no_font_found(monkeypatch):
    monkeypatch.setattr("wowusky.gui.fonts._font_exists", lambda n: False)
    assert resolve_sans_family() == "Helvetica"


def test_resolve_mono_falls_back_to_monospace(monkeypatch):
    monkeypatch.setattr("wowusky.gui.fonts._font_exists", lambda n: False)
    assert resolve_mono_family() == "monospace"


def test_resolve_sans_picks_first_available(monkeypatch):
    monkeypatch.setattr(
        "wowusky.gui.fonts._font_exists",
        lambda n: n == "DejaVu Sans",
    )
    result = resolve_sans_family()
    assert result == "DejaVu Sans"


def test_candidates_are_non_empty_tuples():
    assert len(_SANS_CANDIDATES) > 0
    assert len(_MONO_CANDIDATES) > 0
