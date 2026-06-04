"""Tests for v0.11.0 features: auto_update_on_launch config, wago bridge enhancements."""

from __future__ import annotations

import pytest

from wowusky.core import config as _config


# ── auto_update_on_launch ────────────────────────────────────────────


def test_auto_update_on_launch_default(tmp_path, monkeypatch):
    monkeypatch.setattr(_config, "CONFIG_FILE", tmp_path / "config.json")
    assert _config.get_auto_update_on_launch() is False


def test_auto_update_on_launch_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(_config, "CONFIG_FILE", tmp_path / "config.json")
    _config.set_auto_update_on_launch(True)
    assert _config.get_auto_update_on_launch() is True
    _config.set_auto_update_on_launch(False)
    assert _config.get_auto_update_on_launch() is False


# ── _has_aura_update helper (internal) ──────────────────────────────


def test_has_aura_update_true():
    from wowusky.bridge.server import _has_aura_update
    assert _has_aura_update({"version": 3, "latest_version": 5}) is True


def test_has_aura_update_false():
    from wowusky.bridge.server import _has_aura_update
    assert _has_aura_update({"version": 5, "latest_version": 5}) is False


def test_has_aura_update_no_latest():
    from wowusky.bridge.server import _has_aura_update
    assert _has_aura_update({"version": 5}) is False


def test_has_aura_update_bad_values():
    from wowusky.bridge.server import _has_aura_update
    assert _has_aura_update({"version": "x", "latest_version": "y"}) is False
