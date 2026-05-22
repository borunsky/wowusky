# Contributing to wowusky

Thanks for taking a look. This file describes the workflow we use to
keep the codebase healthy.

## Development setup

```bash
git clone https://github.com/wowusky/wowusky
cd wowusky
pip install -e ".[dev]"

# run the suite
pytest -q

# lint
ruff check wowusky tests
```

The project deliberately avoids runtime dependencies. The only external
packages are dev-time tools (`pytest`, `ruff`, `build`).

## What to put where

- `wowusky/core/`     — primitives that have no GUI and no provider deps.
- `wowusky/providers/` — one file per addon source. Each provider
  implements the `AddonProvider` protocol from `providers/base.py`.
- `wowusky/catalog/`  — manifest loader and the bundled `*.json` files.
- `wowusky/tools/`    — small CLIs we ship alongside the GUI (e.g. the
  weekly health check).
- `wowusky/app.py`    — Tk GUI orchestration. We're actively splitting
  this into a `wowusky/gui/` package; new GUI code goes there.
- `tests/`            — one file per module under test.

## Adding an addon to the catalog

Open an issue using the **Catalog request** template, or send a PR that
adds an entry to the appropriate manifest under
`wowusky/catalog/manifests/`. Keep manifests sorted by category for
readable diffs.

## Adding a new provider

1. Create `wowusky/providers/<name>.py` implementing `resolve`,
   `latest_version`, `page_url` and (when possible) `download_url`.
2. Register it in `wowusky/providers/__init__.py` under a stable name.
3. Add tests in `tests/test_providers.py` for `resolve` and any URL
   helpers. Live network calls go through the weekly health check, not
   into the unit tests.

## Coding style

- Ruff handles formatting and lint. New code must pass
  `ruff check wowusky tests` with the strict ruleset (the per-file
  ignores for `app.py` are a transition mechanism, not a license).
- Type hints on all new public functions, please.
- Docstrings: one-line summary, then a blank line, then prose if
  needed. Module-level docstrings explain *why* the module exists.

## Tests

- `pytest -q` on the new module's behaviour before opening a PR.
- For anything touching disk, use the `tmp_path` fixture.
- For anything touching `~/.local/share/wowusky/`, use the
  `isolated_data_dir` fixture pattern from `tests/test_profiles.py`
  (it pins `XDG_DATA_HOME` to a tmp dir and reloads the modules whose
  paths are cached).

## Commit / PR conventions

- Subject line in present tense, ≤ 70 chars.
- A short paragraph in the body explaining *why* if the change isn't
  obvious from the diff.
- Link to issues with `Closes #123` so the bot can clean up.

That's it. Welcome aboard.
