"""Characterisation tests for the provider functions in app.py.

These tests pin the CURRENT behaviour of the WoWInterface provider
functions before the v0.5 provider extraction. They are a safety net:
if the upcoming migration changes behaviour, these go red.

Network calls are mocked — http_get_json is replaced with a function
returning a fixed, known API response. We test what the wowi_*
functions DERIVE from that response, not the network itself.
"""

from __future__ import annotations

import wowusky.app as app


# A representative MMOUI filedetails response (as the API returns it:
# a single-element list of dicts).
_FAKE_WOWI_RESPONSE = [
    {
        "UID": "12345",
        "UIVersion": "3.4.1",
        "UIDownload": "https://cdn.wowinterface.com/downloads/file12345/MyAddon.zip",
        "UIName": "MyAddon",
    }
]


def _patch_http(monkeypatch, response):
    """Replace app.http_get_json with a stub returning `response`."""
    monkeypatch.setattr(app, "http_get_json", lambda url: response)


def test_wowi_info_unwraps_single_element_list(monkeypatch):
    """The MMOUI API returns a list; wowi_info unwraps the first dict."""
    _patch_http(monkeypatch, _FAKE_WOWI_RESPONSE)
    info = app.wowi_info("12345")
    assert isinstance(info, dict)
    assert info["UIVersion"] == "3.4.1"


def test_wowi_info_returns_empty_dict_on_error(monkeypatch):
    """A network failure must yield {} — never raise."""
    def boom(url):
        raise RuntimeError("network down")
    monkeypatch.setattr(app, "http_get_json", boom)
    assert app.wowi_info("12345") == {}


def test_wowi_version_reads_uiversion(monkeypatch):
    _patch_http(monkeypatch, _FAKE_WOWI_RESPONSE)
    assert app.wowi_version({"wowi_id": "12345"}) == "3.4.1"


def test_wowi_version_falls_back_to_manual(monkeypatch):
    """With no version field, wowi_version yields the literal 'manual'."""
    _patch_http(monkeypatch, [{"UID": "12345"}])
    assert app.wowi_version({"wowi_id": "12345"}) == "manual"


def test_wowi_url_reads_uidownload(monkeypatch):
    _patch_http(monkeypatch, _FAKE_WOWI_RESPONSE)
    url = app.wowi_url({"wowi_id": "12345"})
    assert url.endswith("MyAddon.zip")


def test_wowi_url_empty_when_no_download(monkeypatch):
    _patch_http(monkeypatch, [{"UID": "12345"}])
    assert app.wowi_url({"wowi_id": "12345"}) == ""


def test_wowi_page_url_format(monkeypatch):
    """page_url is pure string-building — no network needed."""
    url = app.wowi_page_url({"wowi_id": "12345"})
    assert url == "https://www.wowinterface.com/downloads/info12345.html"


# ── Wago ──────────────────────────────────────────────────────────────
#
# wago_fetch_info is trickier: it uses TWO network mechanisms.
#   1. `with _http(url) as r: ... r.read()`  — low-level, primary path
#   2. `http_get_json(url)`                  — fallback path
# Both must be mocked or the test leaks to the real network.


class _FakeResponse:
    """Minimal stand-in for the object `_http` yields as a context
    manager: supports `with ... as r` and `r.read()`."""

    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._payload


def test_parse_wago_url_extracts_slug(monkeypatch):
    """parse_wago_url is pure string parsing — no network."""
    slug, version = app.parse_wago_url("https://wago.io/abc123XYZ")
    assert slug == "abc123XYZ"


def test_parse_wago_url_returns_none_pair_on_no_match():
    """A non-wago string yields the (None, None) pair, never raises."""
    result = app.parse_wago_url("not a wago url at all")
    assert result == (None, None)


def test_wago_fetch_info_uses_primary_endpoint(monkeypatch):
    """When the _http path succeeds, its JSON payload is returned and
    the http_get_json fallback is never consulted."""
    import json as _json
    payload = _json.dumps({"name": "My Aura", "version": 7}).encode("utf-8")
    monkeypatch.setattr(app, "_http", lambda url: _FakeResponse(payload))

    def fallback_must_not_run(url):
        raise AssertionError("fallback http_get_json should not be called")
    monkeypatch.setattr(app, "http_get_json", fallback_must_not_run)

    info = app.wago_fetch_info("abc123")
    assert info["name"] == "My Aura"
    assert info["version"] == 7


def test_wago_fetch_info_falls_back_on_primary_failure(monkeypatch):
    """If the _http path raises, wago_fetch_info tries http_get_json."""
    def primary_boom(url):
        raise RuntimeError("primary endpoint down")
    monkeypatch.setattr(app, "_http", primary_boom)
    monkeypatch.setattr(app, "http_get_json",
                        lambda url: {"wagoVersion": 3})

    info = app.wago_fetch_info("abc123")
    assert info == {"wagoVersion": 3}


def test_wago_fetch_info_returns_none_when_both_fail(monkeypatch):
    """Both endpoints down → None, never an exception."""
    def boom(url):
        raise RuntimeError("down")
    monkeypatch.setattr(app, "_http", boom)
    monkeypatch.setattr(app, "http_get_json", boom)
    assert app.wago_fetch_info("abc123") is None


def test_wago_fetch_encoded_returns_string(monkeypatch):
    """wago_fetch_encoded returns the raw decoded import string."""
    monkeypatch.setattr(app, "_http",
                        lambda url: _FakeResponse(b"!WA:2!encodedstring"))
    result = app.wago_fetch_encoded("abc123")
    assert result == "!WA:2!encodedstring"


def test_wago_fetch_encoded_returns_none_on_error(monkeypatch):
    def boom(url):
        raise RuntimeError("down")
    monkeypatch.setattr(app, "_http", boom)
    assert app.wago_fetch_encoded("abc123") is None

# ── Tukui ─────────────────────────────────────────────────────────────
#
# Tukui is the simplest provider: tukui_version/tukui_url just read
# fields off the catalog entry dict. The interesting bit is
# _load_addon_catalog_with_compat(), which RECONSTRUCTS those fields
# (api_url, download_url) from the slug when a manifest omits them.


_FAKE_TUKUI_API_RESPONSE = {"version": "13.62", "name": "ElvUI"}


def test_tukui_version_reads_version_field(monkeypatch):
    """tukui_version fetches api_url and returns its 'version'."""
    monkeypatch.setattr(app, "http_get_json",
                        lambda url: _FAKE_TUKUI_API_RESPONSE)
    v = app.tukui_version({"api_url": "https://api.tukui.org/v1/addon/elvui"})
    assert v == "13.62"


def test_tukui_version_falls_back_to_question_mark(monkeypatch):
    """With no 'version' field in the response, the literal '?' is used."""
    monkeypatch.setattr(app, "http_get_json", lambda url: {"name": "ElvUI"})
    v = app.tukui_version({"api_url": "https://api.tukui.org/v1/addon/elvui"})
    assert v == "?"


def test_tukui_url_returns_download_url_field():
    """tukui_url is a pure field read — no network."""
    entry = {"download_url": "https://api.tukui.org/v1/download/dev/elvui/main"}
    assert app.tukui_url(entry) == entry["download_url"]


def test_compat_reconstructs_tukui_urls_when_missing(monkeypatch):
    """_load_addon_catalog_with_compat must synthesise api_url and
    download_url for a tukui entry that lacks them, using the slug."""
    fake_manifest = [
        {"id": "elvui", "provider": "tukui", "slug": "elvui", "name": "ElvUI"},
    ]
    monkeypatch.setattr(app, "_load_manifest_catalog", lambda: fake_manifest)

    catalog = app._load_addon_catalog_with_compat()
    entry = catalog[0]
    assert entry["api_url"] == "https://api.tukui.org/v1/addon/elvui"
    assert entry["download_url"] == \
        "https://api.tukui.org/v1/download/dev/elvui/main"


def test_compat_keeps_existing_tukui_urls(monkeypatch):
    """If a manifest already provides the URLs, they must NOT be
    overwritten — setdefault only fills what is missing."""
    fake_manifest = [
        {
            "id": "elvui", "provider": "tukui", "slug": "elvui",
            "api_url": "https://custom.example/api",
            "download_url": "https://custom.example/dl",
        },
    ]
    monkeypatch.setattr(app, "_load_manifest_catalog", lambda: fake_manifest)

    entry = app._load_addon_catalog_with_compat()[0]
    assert entry["api_url"] == "https://custom.example/api"
    assert entry["download_url"] == "https://custom.example/dl"


def test_compat_falls_back_to_id_when_no_slug(monkeypatch):
    """Reconstruction uses 'slug', but falls back to 'id' when slug
    is absent."""
    fake_manifest = [
        {"id": "tukui", "provider": "tukui", "name": "Tukui"},
    ]
    monkeypatch.setattr(app, "_load_manifest_catalog", lambda: fake_manifest)

    entry = app._load_addon_catalog_with_compat()[0]
    assert entry["api_url"] == "https://api.tukui.org/v1/addon/tukui"


def test_compat_mirrors_provider_into_source(monkeypatch):
    """The provider↔source duality: an entry with only 'provider'
    must get a matching 'source' field."""
    fake_manifest = [
        {"id": "x", "provider": "github", "name": "X"},
    ]
    monkeypatch.setattr(app, "_load_manifest_catalog", lambda: fake_manifest)

    entry = app._load_addon_catalog_with_compat()[0]
    assert entry["source"] == "github"