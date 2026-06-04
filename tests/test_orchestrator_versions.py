"""Tests for orchestrator version-listing dispatch.

These cover the provider-routing in ``list_addon_versions`` and the
GitHub/CurseForge choice builders without hitting the network — the
provider HTTP/API calls are monkeypatched.
"""

from __future__ import annotations

from wowusky import orchestrator as orch


def test_list_addon_versions_unsupported_source_returns_empty():
    assert orch.list_addon_versions({"source": "tukui", "id": "x"}) == []
    assert orch.list_addon_versions({"source": "wowi", "id": "x"}) == []
    assert orch.list_addon_versions({"source": "internal_wac", "id": "x"}) == []


def test_github_version_choices_uses_releases(monkeypatch):
    monkeypatch.setattr(orch._github_fns, "github_repo_for_addon", lambda a: "owner/repo")
    monkeypatch.setattr(
        orch._ws_http, "get_json",
        lambda url: [
            {"tag_name": "v2.0", "prerelease": False,
             "assets": [{"name": "Addon.zip", "browser_download_url": "http://x/2.zip"}]},
            {"tag_name": "v1.0", "prerelease": True,
             "assets": [], "zipball_url": "http://x/1.zip"},
        ],
    )
    monkeypatch.setattr(orch._github_fns, "_github_pick_asset",
                        lambda assets: assets[0] if assets else None)

    choices = orch.list_addon_versions({"source": "github", "id": "a", "repo": "owner/repo"})
    assert [c["label"] for c in choices] == ["v2.0", "v1.0"]
    assert choices[0]["url"] == "http://x/2.zip"
    assert choices[0]["type"] == "release"
    assert choices[1]["url"] == "http://x/1.zip"  # falls back to zipball_url
    assert choices[1]["type"] == "beta"           # prerelease → beta


def test_github_version_choices_falls_back_to_tags(monkeypatch):
    monkeypatch.setattr(orch._github_fns, "github_repo_for_addon", lambda a: "owner/repo")
    monkeypatch.setattr(orch._ws_http, "get_json", lambda url: [])  # no releases
    monkeypatch.setattr(orch._github_fns, "github_tags",
                        lambda repo: [{"name": "v3.1"}])

    choices = orch.list_addon_versions({"source": "github", "id": "a"})
    assert len(choices) == 1
    assert choices[0]["label"] == "v3.1"
    assert choices[0]["type"] == "tag"
    assert "archive/refs/tags/v3.1.zip" in choices[0]["url"]


def test_curseforge_version_choices_without_api_key_is_empty(monkeypatch):
    monkeypatch.setattr(orch, "get_curseforge_api_key", lambda: "")
    assert orch.list_addon_versions(
        {"source": "curseforge", "id": "a", "curseforge_mod_id": 123}
    ) == []


def test_curseforge_version_choices_builds_from_files(monkeypatch):
    monkeypatch.setattr(orch, "get_curseforge_api_key", lambda: "key")
    monkeypatch.setattr(orch._cf_fns, "curseforge_json",
                        lambda path, *a, **k: {"data": {"id": 123}})
    monkeypatch.setattr(orch._cf_fns, "curseforge_get_files", lambda mid: [
        {"id": 2, "displayName": "Addon-2.0", "fileDate": "2024-02", "releaseType": 1},
        {"id": 1, "displayName": "Addon-1.0", "fileDate": "2024-01", "releaseType": 2},
    ])
    monkeypatch.setattr(orch._cf_fns, "curseforge_file_matches_flavor", lambda f: True)
    monkeypatch.setattr(orch._cf_fns, "curseforge_download_url",
                        lambda mid, f: f"http://cf/{f['id']}.zip")

    choices = orch.list_addon_versions(
        {"source": "curseforge", "id": "a", "curseforge_mod_id": 123}
    )
    labels = [c["label"] for c in choices]
    assert labels == ["Addon-2.0", "Addon-1.0"]  # newest first
    assert choices[0]["type"] == "release"
    assert choices[1]["type"] == "beta"
    assert choices[0]["url"] == "http://cf/2.zip"
