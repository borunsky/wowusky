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