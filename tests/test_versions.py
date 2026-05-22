"""Tests for version-string normalisation and comparison."""

from wowusky.core.versions import (
    normalise_version,
    version_sort_key,
    version_tokens,
    versions_equal,
)


def test_versions_equal_strips_leading_v():
    assert versions_equal("v1.2.3", "1.2.3")
    assert versions_equal("V1.0", "1.0")


def test_versions_equal_handles_whitespace_and_case():
    assert versions_equal("  V1.0  ", "1.0")
    assert versions_equal("ALPHA", "alpha")


def test_versions_equal_handles_none():
    assert versions_equal(None, None)  # both normalise to ""
    assert versions_equal(None, "")


def test_versions_equal_distinct_versions():
    assert not versions_equal("1.0", "1.1")
    assert not versions_equal("v2", "v3")


def test_normalise_version_returns_empty_for_none():
    assert normalise_version(None) == ""


def test_version_tokens_natural_chunks():
    assert version_tokens("v1.10.2") == [1, ".", 10, ".", 2]


def test_version_sort_key_orders_numerically():
    versions = ["v1.2", "v1.10", "v1.9", "v2.0"]
    s = sorted(versions, key=version_sort_key)
    # "1.10" must come after "1.9" naturally
    assert s == ["v1.2", "v1.9", "v1.10", "v2.0"]
