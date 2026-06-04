"""Tests for wowusky.core.favorites."""

from __future__ import annotations

import json

import pytest

from wowusky.core import favorites as fav


@pytest.fixture(autouse=True)
def _tmp_favs(tmp_path, monkeypatch):
    tmp_file = tmp_path / "favorites.json"
    monkeypatch.setattr("wowusky.core.favorites.FAVORITES_FILE", tmp_file)
    monkeypatch.setattr("wowusky.core.favorites.ensure_dirs", lambda: None)
    yield tmp_file


def test_load_empty_when_file_missing(_tmp_favs):
    assert fav.load() == set()


def test_toggle_adds_and_returns_true(_tmp_favs):
    result = fav.toggle("elvui")
    assert result is True
    assert fav.load() == {"elvui"}


def test_toggle_removes_and_returns_false(_tmp_favs):
    fav.toggle("elvui")
    result = fav.toggle("elvui")
    assert result is False
    assert fav.load() == set()


def test_toggle_idempotent_on_second_add(_tmp_favs):
    fav.toggle("ace3")
    fav.toggle("ace3")
    assert fav.load() == set()


def test_is_favorite(_tmp_favs):
    assert not fav.is_favorite("bigwigs")
    fav.toggle("bigwigs")
    assert fav.is_favorite("bigwigs")


def test_persists_sorted(_tmp_favs, tmp_path):
    fav.toggle("zzz")
    fav.toggle("aaa")
    data = json.loads(_tmp_favs.read_text())
    assert data == ["aaa", "zzz"]


def test_multiple_favorites_preserved(_tmp_favs):
    fav.toggle("a")
    fav.toggle("b")
    fav.toggle("c")
    assert fav.load() == {"a", "b", "c"}
