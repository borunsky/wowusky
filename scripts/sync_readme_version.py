#!/usr/bin/env python3
"""Sync README version strings and the "What's new" block from CHANGELOG.md.

Source of truth is the top-most ``## [X.Y.Z] — DATE`` entry in CHANGELOG.md.
This script:

1. rewrites the banner version and the install snippets in README.md to that
   version, and
2. regenerates the block between the ``WHATS-NEW`` HTML-comment markers from
   the CHANGELOG body of that entry.

Run by ``.github/workflows/readme-version-sync.yml`` on every published
release, but it is a plain script with no dependencies and can be run by hand:

    python scripts/sync_readme_version.py            # rewrite README.md
    python scripts/sync_readme_version.py --check     # exit 1 if out of date
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"
README = ROOT / "README.md"

START = "<!-- WHATS-NEW:START -->"
END = "<!-- WHATS-NEW:END -->"
GEN_NOTE = (
    "<!-- This section is generated from the latest CHANGELOG.md entry by\n"
    "     .github/workflows/readme-version-sync.yml on each published release.\n"
    "     Edit CHANGELOG.md, not the text between these markers. -->"
)


def latest_changelog_entry(text: str) -> tuple[str, str]:
    """Return (version, body) of the top-most ## [X.Y.Z] section."""
    m = re.search(r"^## \[(\d+\.\d+\.\d+)\][^\n]*\n", text, re.MULTILINE)
    if not m:
        raise SystemExit("sync_readme_version: no '## [X.Y.Z]' entry in CHANGELOG.md")
    version = m.group(1)
    rest = text[m.end():]
    nxt = re.search(r"^## \[", rest, re.MULTILINE)
    body = (rest[: nxt.start()] if nxt else rest).strip("\n")
    return version, body


def build_whats_new(version: str, body: str) -> str:
    return f"{START}\n{GEN_NOTE}\n## What's new in v{version}\n\n{body}\n{END}"


def sync(text: str, version: str, whats_new: str) -> str:
    # 1. Replace the WHATS-NEW block.
    block_re = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if not block_re.search(text):
        raise SystemExit("sync_readme_version: WHATS-NEW markers not found in README.md")
    text = block_re.sub(lambda _: whats_new, text)

    # 2. Sync version strings in banner + install snippets.
    subs = [
        (r"(wowusky v)\d+\.\d+\.\d+", rf"\g<1>{version}"),
        (r"(wowusky-v)\d+\.\d+\.\d+", rf"\g<1>{version}"),
        (r"(wowusky-)\d+\.\d+\.\d+(-py3-none-any\.whl)", rf"\g<1>{version}\g<2>"),
    ]
    for pat, repl in subs:
        text = re.sub(pat, repl, text)
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 if README is out of date")
    args = ap.parse_args()

    version, body = latest_changelog_entry(CHANGELOG.read_text(encoding="utf-8"))
    whats_new = build_whats_new(version, body)
    original = README.read_text(encoding="utf-8")
    updated = sync(original, version, whats_new)

    if args.check:
        if original != updated:
            print(f"README.md is out of date (expected v{version}). Run scripts/sync_readme_version.py.")
            return 1
        print(f"README.md is in sync (v{version}).")
        return 0

    if original != updated:
        README.write_text(updated, encoding="utf-8")
        print(f"README.md synced to v{version}.")
    else:
        print(f"README.md already in sync (v{version}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
