"""Documentation–reality consistency checks.

We've shipped two releases now where README and CHANGELOG quoted
``app.py`` line counts that were wrong by a few hundred lines. This
test exists so that the next time the file grows or shrinks, the
docs are forced to catch up — or this test fails and the author
notices before merging.

Scope is intentionally small: numbers that are easy to verify
programmatically and that have actually drifted in the past.
"""

from __future__ import annotations

import re
from pathlib import Path

import wowusky

REPO_ROOT  = Path(__file__).resolve().parents[1]
APP_PY     = REPO_ROOT / "wowusky" / "app.py"
README_MD  = REPO_ROOT / "README.md"
CHANGELOG  = REPO_ROOT / "CHANGELOG.md"

# Tolerance for the README's rounded "approximately N lines" claim,
# so trivial whitespace edits don't immediately fail this test.
APP_PY_TOLERANCE = 50


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ── README ──────────────────────────────────────────────────────────

def test_readme_app_py_line_count_matches_reality():
    """README's `app.py` line claim must be within tolerance of `wc -l`."""
    real_lines = sum(1 for _ in APP_PY.open("rb"))
    readme = _read(README_MD)

    # Catch both "down from X → Y lines" and "(~Y lines)" forms.
    arrow_match = re.search(r"app\.py.{0,80}?(\d{4,5})\s*lines", readme,
                            flags=re.IGNORECASE)
    approx_match = re.search(r"~\s*(\d{4,5})\s*lines", readme)
    claimed = []
    if arrow_match:
        claimed.append(int(arrow_match.group(1)))
    if approx_match:
        claimed.append(int(approx_match.group(1)))
    assert claimed, "README no longer mentions an app.py line count"

    for n in claimed:
        assert abs(n - real_lines) <= APP_PY_TOLERANCE, (
            f"README claims app.py has ~{n} lines; "
            f"actual is {real_lines}. Update README.md."
        )


def test_readme_version_banner_matches_package_version():
    readme = _read(README_MD)
    m = re.search(r"wowusky v(\d+\.\d+\.\d+)", readme)
    assert m, "README no longer has a 'wowusky vX.Y.Z' banner"
    assert m.group(1) == wowusky.__version__, (
        f"README banner says v{m.group(1)} but package is "
        f"v{wowusky.__version__}. Bump the banner."
    )


def test_readme_install_snippet_matches_package_version():
    readme = _read(README_MD)
    # `unzip wowusky-vX.Y.Z.zip` or `wowusky-X.Y.Z-py3-none-any.whl`
    for pat, label in (
        (r"wowusky-v(\d+\.\d+\.\d+)\.zip",            "unzip snippet"),
        (r"wowusky-(\d+\.\d+\.\d+)-py3-none-any\.whl", "wheel snippet"),
    ):
        m = re.search(pat, readme)
        assert m, f"README is missing the {label}"
        assert m.group(1) == wowusky.__version__, (
            f"README {label} references {m.group(1)} but package is "
            f"{wowusky.__version__}."
        )


# ── CHANGELOG ───────────────────────────────────────────────────────

def test_changelog_has_entry_for_current_version():
    changelog = _read(CHANGELOG)
    pattern = rf"##\s*\[{re.escape(wowusky.__version__)}\]"
    assert re.search(pattern, changelog), (
        f"CHANGELOG.md is missing a `## [{wowusky.__version__}]` section. "
        "Add the entry before tagging."
    )


def test_changelog_link_ref_for_current_version():
    changelog = _read(CHANGELOG)
    pattern = rf"\[{re.escape(wowusky.__version__)}\]:\s*https?://"
    assert re.search(pattern, changelog), (
        f"CHANGELOG.md is missing a `[{wowusky.__version__}]: <url>` "
        "link reference at the bottom."
    )


# ── app.py docstring sanity ─────────────────────────────────────────

def test_app_py_does_not_claim_to_import_providers():
    """Until v0.5 lands, app.py must not claim it imports from providers."""
    src = _read(APP_PY)
    # Number of *actual* imports from wowusky.providers
    import_lines = re.findall(r"^\s*from\s+wowusky\.providers\b",
                              src, flags=re.MULTILINE)
    if import_lines:
        # If a future patch wires this up for real, the test passes
        # and the docstring sentence below becomes obsolete — feel
        # free to delete this entire test.
        return

    # No imports yet — the docstring should not claim otherwise.
    head = src[:1500].lower()
    forbidden = "imports from :mod:`wowusky.providers`"
    assert forbidden not in head, (
        "app.py docstring claims it imports from wowusky.providers, "
        "but no such import exists. Either wire up the import or "
        "soften the docstring."
    )
