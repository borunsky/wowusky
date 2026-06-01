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
import wowusky.providers.curseforge_fns as cf_fns
import wowusky.providers.github_fns as github_fns
import wowusky.providers.tukui_fns as tukui_fns
import wowusky.providers.wago_fns as wago_fns
import wowusky.providers.wowi_fns as wowi_fns

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
    """Replace http_get_json in the wowi_fns module with a stub."""
    monkeypatch.setattr(wowi_fns, "http_get_json", lambda url: response)


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
    monkeypatch.setattr(wowi_fns, "http_get_json", boom)
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
    monkeypatch.setattr(wago_fns, "_http", lambda url: _FakeResponse(payload))

    def fallback_must_not_run(url):
        raise AssertionError("fallback http_get_json should not be called")
    monkeypatch.setattr(wago_fns, "http_get_json", fallback_must_not_run)

    info = app.wago_fetch_info("abc123")
    assert info["name"] == "My Aura"
    assert info["version"] == 7


def test_wago_fetch_info_falls_back_on_primary_failure(monkeypatch):
    """If the _http path raises, wago_fetch_info tries http_get_json."""
    def primary_boom(url):
        raise RuntimeError("primary endpoint down")
    monkeypatch.setattr(wago_fns, "_http", primary_boom)
    monkeypatch.setattr(wago_fns, "http_get_json",
                        lambda url: {"wagoVersion": 3})

    info = app.wago_fetch_info("abc123")
    assert info == {"wagoVersion": 3}


def test_wago_fetch_info_returns_none_when_both_fail(monkeypatch):
    """Both endpoints down → None, never an exception."""
    def boom(url):
        raise RuntimeError("down")
    monkeypatch.setattr(wago_fns, "_http", boom)
    monkeypatch.setattr(wago_fns, "http_get_json", boom)
    assert app.wago_fetch_info("abc123") is None


def test_wago_fetch_encoded_returns_string(monkeypatch):
    """wago_fetch_encoded returns the raw decoded import string."""
    monkeypatch.setattr(wago_fns, "_http",
                        lambda url: _FakeResponse(b"!WA:2!encodedstring"))
    result = app.wago_fetch_encoded("abc123")
    assert result == "!WA:2!encodedstring"


def test_wago_fetch_encoded_returns_none_on_error(monkeypatch):
    def boom(url):
        raise RuntimeError("down")
    monkeypatch.setattr(wago_fns, "_http", boom)
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
    monkeypatch.setattr(tukui_fns, "http_get_json",
                        lambda url: _FAKE_TUKUI_API_RESPONSE)
    v = app.tukui_version({"api_url": "https://api.tukui.org/v1/addon/elvui"})
    assert v == "13.62"


def test_tukui_version_falls_back_to_question_mark(monkeypatch):
    """With no 'version' field in the response, the literal '?' is used."""
    monkeypatch.setattr(tukui_fns, "http_get_json", lambda url: {"name": "ElvUI"})
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

# ── GitHub ────────────────────────────────────────────────────────────
#
# The most complex provider: eight interlocking functions. Three things
# need mocking — http_get_json (API calls), get_current_flavor (flavor
# logic), and urllib.request.urlopen (the HEAD probe in
# _github_branch_exists). The B2 branch-probing fix is pinned here
# explicitly: it must be preserved across the migration.
import urllib.error

# ---- github_repo_for_addon ----

def test_github_repo_plain_string_passthrough():
    """A bare string addon ref is returned as-is."""
    assert app.github_repo_for_addon("owner/repo") == "owner/repo"


def test_github_repo_uses_plain_repo_field(monkeypatch):
    """A dict without repo_by_flavor falls back to the 'repo' field."""
    monkeypatch.setattr(github_fns, "get_current_flavor", lambda: "retail")
    assert app.github_repo_for_addon({"repo": "owner/repo"}) == "owner/repo"


def test_github_repo_by_flavor_picks_flavor_specific(monkeypatch):
    """repo_by_flavor: the current flavor selects its own repository."""
    monkeypatch.setattr(github_fns, "get_current_flavor", lambda: "vanilla")
    addon = {
        "repo": "owner/retail-repo",
        "repo_by_flavor": {
            "vanilla": "owner/classic-repo",
            "retail": "owner/retail-repo",
        },
    }
    assert app.github_repo_for_addon(addon) == "owner/classic-repo"


def test_github_repo_by_flavor_falls_back_to_retail(monkeypatch):
    """A flavor with no specific entry falls back through retail/default."""
    monkeypatch.setattr(github_fns, "get_current_flavor", lambda: "mop_classic")
    addon = {
        "repo": "owner/plain",
        "repo_by_flavor": {"retail": "owner/retail-repo"},
    }
    assert app.github_repo_for_addon(addon) == "owner/retail-repo"


# ---- github_releases ----

def test_github_releases_prefers_latest(monkeypatch):
    """When /releases/latest succeeds, it is wrapped in a one-item list."""
    monkeypatch.setattr(github_fns, "http_get_json",
                        lambda url: {"tag_name": "v1.2.3"})
    rels = app.github_releases("owner/repo")
    assert rels == [{"tag_name": "v1.2.3"}]


def test_github_releases_returns_empty_on_total_failure(monkeypatch):
    """All endpoints failing yields [] — never an exception."""
    def boom(url):
        raise RuntimeError("api down")
    monkeypatch.setattr(github_fns, "http_get_json", boom)
    assert app.github_releases("owner/repo") == []


# ---- github_tags ----

def test_github_tags_returns_list(monkeypatch):
    monkeypatch.setattr(github_fns, "http_get_json",
                        lambda url: [{"name": "v2.0"}])
    assert app.github_tags("owner/repo") == [{"name": "v2.0"}]


def test_github_tags_empty_on_error(monkeypatch):
    def boom(url):
        raise RuntimeError("down")
    monkeypatch.setattr(github_fns, "http_get_json", boom)
    assert app.github_tags("owner/repo") == []


# ---- github_default_branch + _github_branch_exists (the B2 fix) ----

def test_github_default_branch_from_api(monkeypatch):
    """When the API answers, its default_branch is used directly."""
    monkeypatch.setattr(github_fns, "http_get_json",
                        lambda url: {"default_branch": "develop"})
    assert app.github_default_branch("owner/repo") == "develop"


def test_github_default_branch_probes_master_on_api_failure(monkeypatch):
    """B2 fix: when the API fails, the branch is PROBED, not assumed.
    Here 'main' does not exist but 'master' does — result must be
    'master', not a blind 'main'."""
    def api_down(url):
        raise RuntimeError("rate limited")
    monkeypatch.setattr(github_fns, "http_get_json", api_down)

    def fake_exists(repo, branch):
        return branch == "master"
    monkeypatch.setattr(github_fns, "_github_branch_exists", fake_exists)

    assert app.github_default_branch("owner/repo") == "master"


def test_github_default_branch_defaults_to_main_when_nothing_probes(
        monkeypatch):
    """If neither branch probes positive, the final fallback is 'main'."""
    monkeypatch.setattr(github_fns, "http_get_json",
                        lambda url: (_ for _ in ()).throw(RuntimeError()))
    monkeypatch.setattr(github_fns, "_github_branch_exists",
                        lambda repo, branch: False)
    assert app.github_default_branch("owner/repo") == "main"


def test_branch_exists_true_on_http_ok(monkeypatch):
    """_github_branch_exists: a 2xx/3xx HEAD response means True."""
    class _Resp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=10: _Resp())
    assert app._github_branch_exists("owner/repo", "main") is True


def test_branch_exists_false_on_http_error(monkeypatch):
    """A definitive HTTPError (e.g. 404) means the branch is missing."""
    def raise_404(req, timeout=10):
        raise urllib.error.HTTPError("u", 404, "Not Found", {}, None)
    monkeypatch.setattr(urllib.request, "urlopen", raise_404)
    assert app._github_branch_exists("owner/repo", "nope") is False


def test_branch_exists_true_on_network_error(monkeypatch):
    """Key B2 nuance: a NON-HTTP error (network down) must NOT be read
    as 'branch missing'. It returns True so the caller keeps its
    fallback instead of wrongly ruling the branch out."""
    def raise_netfail(req, timeout=10):
        raise OSError("network unreachable")
    monkeypatch.setattr(urllib.request, "urlopen", raise_netfail)
    assert app._github_branch_exists("owner/repo", "main") is True


# ---- github_version ----

def test_github_version_from_release_tag(monkeypatch):
    """Release tag wins, with the leading 'v' stripped."""
    monkeypatch.setattr(github_fns, "github_releases",
                        lambda repo: [{"tag_name": "v3.4.5"}])
    assert app.github_version({"repo": "o/r"}) == "3.4.5"


def test_github_version_branch_snapshot_fallback(monkeypatch):
    """No releases, no tags → '<branch> snapshot'."""
    monkeypatch.setattr(github_fns, "github_releases", lambda repo: [])
    monkeypatch.setattr(github_fns, "github_tags", lambda repo: [])
    monkeypatch.setattr(github_fns, "github_default_branch", lambda repo: "main")
    monkeypatch.setattr(github_fns, "get_current_flavor", lambda: "retail")
    assert app.github_version({"repo": "o/r"}) == "main snapshot"


# ---- _github_pick_asset ----

def test_pick_asset_skips_nolib_and_nonzip(monkeypatch):
    """Non-zip and nolib assets are filtered out."""
    monkeypatch.setattr(github_fns, "get_current_flavor", lambda: "retail")
    assets = [
        {"name": "Addon-nolib.zip", "size": 999},
        {"name": "Addon.txt", "size": 999},
        {"name": "Addon.zip", "size": 100},
    ]
    picked = app._github_pick_asset(assets)
    assert picked["name"] == "Addon.zip"


def test_pick_asset_prefers_flavor_hint(monkeypatch):
    """With a vanilla flavor, an asset whose name contains 'classic'
    is preferred over a larger non-matching one."""
    monkeypatch.setattr(github_fns, "get_current_flavor", lambda: "vanilla")
    assets = [
        {"name": "Addon-mainline.zip", "size": 5000},
        {"name": "Addon-classic.zip", "size": 100},
    ]
    picked = app._github_pick_asset(assets)
    assert picked["name"] == "Addon-classic.zip"


def test_pick_asset_none_when_no_zip(monkeypatch):
    monkeypatch.setattr(github_fns, "get_current_flavor", lambda: "retail")
    assert app._github_pick_asset([{"name": "readme.txt"}]) is None

# ── CurseForge ────────────────────────────────────────────────────────
#
# CurseForge is the most complex provider. We characterise the PROVIDER
# layer only — slug parsing, the web-fallback functions, header
# building, and the flavor-matching logic. The INSTALL layer
# (install_curseforge, install_curseforge_dependencies, import_zip_file)
# is deliberately NOT covered here: per the migration dossier it belongs
# to a separate post-A stage, not provider extraction.


# ---- cf_slug_from_ref ----

def test_cf_slug_from_full_url():
    """A full CurseForge addon URL yields just the slug."""
    slug = app.cf_slug_from_ref(
        "https://www.curseforge.com/wow/addons/details")
    assert slug == "details"


def test_cf_slug_from_bare_slug():
    """A bare slug passes through unchanged."""
    assert app.cf_slug_from_ref("weakauras") == "weakauras"


def test_cf_slug_empty_for_blank():
    assert app.cf_slug_from_ref("") == ""
    assert app.cf_slug_from_ref(None) == ""


def test_cf_slug_empty_for_pure_digits():
    """A pure numeric ref is NOT a slug — it returns empty."""
    assert app.cf_slug_from_ref("123456") == ""


# ---- curseforge_web_version / curseforge_web_url ----

def test_cf_web_version_is_always_manual():
    """The web fallback cannot discover a version — always 'manual'."""
    assert app.curseforge_web_version({"id": "x"}) == "manual"


def test_cf_web_url_uses_slug():
    entry = {"curseforge_slug": "weakauras"}
    url = app.curseforge_web_url(entry)
    assert url == "https://www.curseforge.com/wow/addons/weakauras"


def test_cf_web_url_falls_back_to_id():
    """With no slug, the addon id is used to build the URL."""
    url = app.curseforge_web_url({"id": "details"})
    assert url.endswith("/addons/details")


# ---- curseforge_headers ----

def test_cf_headers_raise_without_key(monkeypatch):
    """Building headers without an API key is a hard error — it must
    raise, not return half-built headers."""
    monkeypatch.setattr(cf_fns, "get_curseforge_api_key", lambda: "")
    import pytest
    with pytest.raises(RuntimeError):
        app.curseforge_headers()


def test_cf_headers_include_key_when_present(monkeypatch):
    monkeypatch.setattr(cf_fns, "get_curseforge_api_key", lambda: "SECRET123")
    headers = app.curseforge_headers()
    assert "SECRET123" in headers.values()


# ---- _cf_file_versions ----

def test_cf_file_versions_extracts_game_versions():
    """gameVersions entries are lower-cased into the version list."""
    versions = app._cf_file_versions({"gameVersions": ["11.0.5", "Retail"]})
    assert "11.0.5" in versions
    assert "retail" in versions


def test_cf_file_versions_extracts_type_ids():
    """A gameVersionTypeId becomes a 'type:NNN' marker."""
    file_data = {
        "sortableGameVersions": [
            {"gameVersion": "11.0.5", "gameVersionTypeId": 517},
        ]
    }
    versions = app._cf_file_versions(file_data)
    assert "type:517" in versions


# ---- curseforge_file_matches_flavor ----

def test_cf_file_matches_flavor_by_type_id(monkeypatch):
    """A file whose type id matches the flavor's hint matches."""
    monkeypatch.setattr(cf_fns, "get_current_flavor", lambda: "retail")
    file_data = {
        "sortableGameVersions": [{"gameVersionTypeId": 517}]
    }
    assert app.curseforge_file_matches_flavor(file_data) is True


def test_cf_file_matches_flavor_by_text(monkeypatch):
    """A file matches when a version string contains a flavor keyword."""
    monkeypatch.setattr(cf_fns, "get_current_flavor", lambda: "vanilla")
    file_data = {"gameVersions": ["1.15.4 Classic Era"]}
    assert app.curseforge_file_matches_flavor(file_data) is True


def test_cf_file_matches_flavor_empty_versions_passes(monkeypatch):
    """A file with NO version info is treated as matching — better to
    offer it than to hide a possibly-correct download."""
    monkeypatch.setattr(cf_fns, "get_current_flavor", lambda: "retail")
    assert app.curseforge_file_matches_flavor({}) is True


def test_cf_file_does_not_match_wrong_flavor(monkeypatch):
    """A retail-only file must NOT match the vanilla flavor."""
    monkeypatch.setattr(cf_fns, "get_current_flavor", lambda: "vanilla")
    file_data = {"gameVersions": ["11.0.5 The War Within"]}
    assert app.curseforge_file_matches_flavor(file_data) is False
