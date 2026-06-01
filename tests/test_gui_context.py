"""Tests for wowusky.gui.context.AppContext.

Headless — no Tk required: root is passed as None in all tests.
"""

import wowusky.gui.theme as _theme
from wowusky.gui.context import AppContext
from wowusky.gui.fonts import make_font_set

_SANS = "Helvetica"
_MONO = "monospace"
_FONTS = make_font_set(_SANS, _MONO)


def _make_ctx(**overrides) -> AppContext:
    defaults = dict(
        palette=_theme.PALETTE_DARK,
        theme_mode="dark",
        sans_family=_SANS,
        mono_family=_MONO,
        fonts=_FONTS,
        root=None,
        make_button=lambda *a, **kw: None,
        app_log=lambda m: None,
    )
    defaults.update(overrides)
    return AppContext(**defaults)


def test_construction():
    ctx = _make_ctx()
    assert ctx.theme_mode == "dark"
    assert ctx.sans_family == _SANS


def test_palette_alias():
    ctx = _make_ctx()
    assert ctx.C is ctx.palette
    assert ctx.C is _theme.PALETTE_DARK


def test_font_shortcuts():
    ctx = _make_ctx()
    assert ctx.font_sm   == _FONTS["FONT_SM"]
    assert ctx.font_body == _FONTS["FONT_BODY"]
    assert ctx.font_head == _FONTS["FONT_HEAD"]
    assert ctx.font_logo == _FONTS["FONT_LOGO"]
    assert ctx.font_section == _FONTS["FONT_SECTION"]
    assert ctx.font_xs   == _FONTS["FONT_XS"]
    assert ctx.font_name == _FONTS["FONT_NAME"]
    assert ctx.font_mono == _FONTS["FONT_MONO"]


def test_default_version_cache_is_empty_dict():
    ctx = _make_ctx()
    assert ctx.version_cache == {}


def test_default_checking_versions():
    ctx = _make_ctx()
    assert ctx.checking_versions == [False]


def test_version_cache_is_mutable():
    ctx = _make_ctx()
    ctx.version_cache["SomeAddon"] = "1.2.3"
    assert ctx.version_cache["SomeAddon"] == "1.2.3"


def test_two_contexts_do_not_share_default_cache():
    ctx_a = _make_ctx()
    ctx_b = _make_ctx()
    ctx_a.version_cache["x"] = 1
    assert "x" not in ctx_b.version_cache


def test_light_palette():
    ctx = _make_ctx(palette=_theme.PALETTE_LIGHT, theme_mode="light")
    assert ctx.theme_mode == "light"
    assert ctx.C is _theme.PALETTE_LIGHT


def test_app_log_callable():
    log = []
    ctx = _make_ctx(app_log=log.append)
    ctx.app_log("hello")
    assert log == ["hello"]
