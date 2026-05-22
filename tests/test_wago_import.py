from wowusky.app import extract_wago_slugs_from_text


def test_extract_wago_slugs_from_url_and_wagoid():
    text = '["url"] = "https://wago.io/abc-123", ["wagoID"] = "XYZ_789"'
    assert extract_wago_slugs_from_text(text) == ["XYZ_789", "abc-123"]
