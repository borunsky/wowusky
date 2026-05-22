"""Tests for TOC parsing, including multi-flavor suffix selection."""

import os
import tempfile
from pathlib import Path

import pytest

from wowusky.core.toc import parse_toc_file, parse_toc_text, read_addon_toc, strip_color_codes


def test_parse_toc_text_basic():
    info = parse_toc_text('## Interface: 20505\n'
                          '## Title: |cff00ff00Demo|r\n'
                          '## Version: 1.2.3\n')
    assert info['interface'] == 20505
    assert info['title'] == 'Demo'
    assert info['version'] == '1.2.3'


def test_parse_toc_text_missing_fields_returns_partial():
    info = parse_toc_text('## Interface: 11508\n')
    assert info['interface'] == 11508
    assert 'version' not in info
    assert 'title'   not in info


def test_parse_toc_text_handles_notes_and_color_codes():
    info = parse_toc_text(
        '## Title: |cFFFF0000Red|r Addon\n'
        '## Notes: |cFF00FF00green note|r\n'
        '## Version: v1.0\n'
    )
    assert info['title'] == 'Red Addon'
    assert info['notes'] == 'green note'
    assert info['version'] == 'v1.0'


def test_parse_toc_text_invalid_interface_ignored():
    info = parse_toc_text('## Interface: not-a-number\n')
    assert 'interface' not in info


def test_strip_color_codes_handles_none_and_empty():
    assert strip_color_codes(None) is None
    assert strip_color_codes("") == ""
    assert strip_color_codes("plain") == "plain"


def test_parse_toc_file_unreadable_returns_empty():
    assert parse_toc_file("/definitely/does/not/exist.toc") == {}


def test_read_addon_toc_picks_flavor_specific_toc(tmp_path):
    """When an addon ships both Foo.toc and Foo_TBC.toc, the Anniversary
    client should get the TBC variant.
    """
    addon = tmp_path / "Foo"
    addon.mkdir()
    (addon / "Foo.toc").write_text(
        "## Interface: 120001\n## Version: retail-1.0\n")
    (addon / "Foo_TBC.toc").write_text(
        "## Interface: 20505\n## Version: tbc-1.0\n")

    info_tbc = read_addon_toc(addon, client_flavor="anniversary")
    assert info_tbc["interface"] == 20505
    assert info_tbc["version"] == "tbc-1.0"

    info_base = read_addon_toc(addon, client_flavor="retail")
    assert info_base["interface"] == 120001
    assert info_base["version"] == "retail-1.0"


def test_read_addon_toc_falls_back_to_shortest_filename(tmp_path):
    addon = tmp_path / "Bar"
    addon.mkdir()
    (addon / "Bar.toc").write_text("## Version: base\n")
    (addon / "Bar_SomethingElse.toc").write_text("## Version: other\n")

    info = read_addon_toc(addon, client_flavor="retail")
    assert info["version"] == "base"


def test_read_addon_toc_empty_folder_returns_empty(tmp_path):
    folder = tmp_path / "Empty"
    folder.mkdir()
    assert read_addon_toc(folder) == {}
