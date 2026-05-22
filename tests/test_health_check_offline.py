"""Tests for the offline path of wowusky.tools.health_check.

The offline path is what the per-push CI job runs: it must not touch
the network, must catch the three failure modes documented in the
module's docstring, and must treat internal-only providers as healthy.
"""

from __future__ import annotations

import json

from wowusky.tools.health_check import (
    _INTERNAL_PROVIDERS,
    check_addon_offline,
    main,
)

# ── failure modes ───────────────────────────────────────────────────

def test_offline_flags_missing_provider_field():
    result = check_addon_offline({"id": "x", "repo": "owner/repo"})
    assert result["error"] == "no provider field"
    assert result["provider"] == ""


def test_offline_flags_unknown_provider():
    result = check_addon_offline(
        {"id": "x", "provider": "does-not-exist", "repo": "owner/repo"}
    )
    assert result["error"] == "unknown provider"


def test_offline_flags_unresolvable_reference():
    # GitHub provider's resolve() returns None for input without a slash.
    result = check_addon_offline(
        {"id": "x", "provider": "github", "repo": "no-slash"}
    )
    assert "resolve returned None" in result["error"]


# ── happy paths ─────────────────────────────────────────────────────

def test_offline_resolves_github_repo():
    result = check_addon_offline(
        {"id": "elvui", "provider": "github", "repo": "tukui-org/ElvUI"}
    )
    assert "error" not in result
    assert result["resolved"] == "tukui-org/ElvUI"


def test_offline_resolves_curseforge_slug():
    result = check_addon_offline(
        {"id": "details", "provider": "curseforge_web",
         "curseforge_slug": "details"}
    )
    assert "error" not in result
    assert result["resolved"] == "details"


def test_offline_treats_internal_providers_as_healthy():
    # WeakAurasCompanion uses the internal_wac sentinel — it has no
    # external API but must not be flagged as broken.
    assert "internal_wac" in _INTERNAL_PROVIDERS
    result = check_addon_offline({"id": "wac", "provider": "internal_wac"})
    assert "error" not in result
    assert result["resolved"] == "internal"


# ── no network ──────────────────────────────────────────────────────

def test_offline_path_does_not_call_get_json(monkeypatch):
    """If the offline path ever reached for the network we want to know."""
    import wowusky.core.http as http_mod

    def boom(*_args, **_kwargs):
        raise AssertionError("offline path attempted a network call")

    monkeypatch.setattr(http_mod, "_open",   boom)
    monkeypatch.setattr(http_mod, "get_json", boom)

    check_addon_offline(
        {"id": "elvui", "provider": "github", "repo": "tukui-org/ElvUI"}
    )
    check_addon_offline(
        {"id": "details", "provider": "curseforge_web",
         "curseforge_slug": "details"}
    )
    check_addon_offline({"id": "wac", "provider": "internal_wac"})


# ── real catalog ────────────────────────────────────────────────────

def test_offline_passes_against_real_catalog():
    """Every shipped catalog entry must pass the offline check.

    This is the safety net: a manifest edit that introduces a typo'd
    provider name or an unresolvable reference will fail this test
    in the lint-and-test workflow, before any deploy.
    """
    from wowusky.catalog import load_catalog

    failures = [check_addon_offline(e)
                for e in load_catalog()
                if "error" in check_addon_offline(e)]
    assert failures == [], (
        f"{len(failures)} catalog entries fail the offline check:\n"
        + "\n".join(f"  {f['id']:30s} [{f['provider']:14s}] {f['error']}"
                    for f in failures[:10])
    )


# ── CLI ─────────────────────────────────────────────────────────────

def test_cli_offline_exits_zero_for_healthy_catalog(monkeypatch, capsys):
    rc = main(["--offline"])
    captured = capsys.readouterr()
    assert rc == 0, captured.out
    assert "offline" in captured.out


def test_cli_offline_json_includes_mode(capsys):
    rc = main(["--offline", "--json", "--limit", "5"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["mode"] == "offline"
    assert payload["total"] == 5
    assert rc == 0
