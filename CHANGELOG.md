# Changelog

All notable changes to wowusky will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.0] — 2026-06-03

Feature release — CLI surface. wowusky can now be driven entirely from
the terminal without opening the GUI.

### Added
- **CLI surface** (`wowusky/cli.py`): `wowusky <command>` dispatch on
  `sys.argv`. When arguments are present the GUI is bypassed entirely.
- Commands: `install <id>...`, `uninstall <id>...`, `update [<id>...]`,
  `status`, `search <query>`, `orphans`, `import [file.zip]`,
  `backup create|list|restore`, `rollback <id> [sel]`,
  `weakauras list|add|remove|update|import|search|companion` (alias `wa`),
  `profile list`, `profile switch <name|id>`,
  `set curseforge-key <key>`, `version`, `help [<command>]`.
- `install` and `update` support `-n/--dry-run` (show plan, no changes)
  and `--no-deps` (skip automatic dependency installation).
- **Automatic full backup** before every command that touches the WoW
  install (AddOns + WTF). Skipped for read-only/offline commands and via
  the global `--no-backup` flag.
- **Full-profile backup/restore** from the CLI: `backup create`,
  `backup list`, `backup restore <index|name|path>`.
- **Per-addon rollback** from the CLI: `rollback <id>` restores an addon's
  newest backup; `rollback <id> --list` lists them; `--backup <sel>` picks
  a specific one.
- **WeakAuras/Wago.io** management from the CLI: track, untrack, check for
  updates, import from SavedVariables, search Wago.io, and regenerate the
  WeakAurasCompanion addon.
- **`help` command** with a full command reference plus per-command detail
  (`wowusky help <command>`) showing syntax, options and examples.
- **`-q/--quiet`** global flag: suppresses progress/info output (keeps
  warnings, errors and explicit results) — handy for cron jobs.
- **`--json`** global flag: machine-readable JSON output for `status`,
  `search`, `orphans`, `backup list` and `weakauras list`. Implies quiet.
- **`update --all-profiles`**: update every configured profile in turn,
  each with its own automatic backup, restoring the active profile after.
- **`completion bash|zsh`**: print a shell completion script to stdout
  (no external dependency).
- **systemd user timer** (`packaging/systemd/`): `wowusky-update.service`
  + `.timer` run `wowusky update --all-profiles --quiet` daily.
- Plain/schlichte output: aligned columns with `ljust`, `✓`/`✗`/`↑`
  markers, no colours or external dependencies.

### Internal
- New tests: `tests/test_cli.py` (56 tests covering parser, search,
  install dry-run, orphans, help, backup, rollback, weakauras, auto-backup,
  quiet, json, update --all-profiles, completion, and `set curseforge-key`).

## [0.7.0] — 2026-06-03

Feature release — automatic dependency resolution. Installing a catalog
addon now pulls in any catalog entries it depends on, in the right order,
before installing the addon itself. Existing profiles, installed lists and
backups are untouched.

### Added
- **Catalog dependency resolver** (`wowusky/core/depends.py`): catalog
  entries may declare `"depends": ["id", ...]`. On install, wowusky
  resolves the transitive dependency graph against the loaded catalog and
  installs every missing dependency first (dependencies before dependents).
  Already-installed dependencies are skipped, cycles are handled safely,
  and dependency ids missing from the catalog are logged and skipped.
- Real dependency data wired into the shipped catalog: LittleWigs → BigWigs,
  the Details plugins (Tiny Threat, Compare2, Streamer) → Details!, BigWigs
  Voice → BigWigs, LittleWigs (CurseForge) → BigWigs (CurseForge).

### Changed
- `install_addon` (orchestrator) gained an `install_deps` flag (default
  `True`) and installs resolved dependencies before the target. The
  single-addon core path is unchanged.
- Manifest loader now normalises a `depends` field (defaults to `[]`).

### Internal
- New tests: `tests/test_depends.py` (resolver unit tests + orchestrator
  install-order wiring + real-catalog dependency assertions).

## [0.6.4] — 2026-06-03

Refactor + responsiveness release. Completes the journey toward
`app.py < 500 lines` (Etappes G & H) and removes the UI freezes that came
with the previous extraction passes. No catalog or install-behaviour
changes; existing profiles, installed lists and backups are untouched.

### Changed
- **`run_gui` → `wowusky/gui/main.py`** (G2): the 1385-line Tk main-window
  builder moved verbatim out of `app.py`. `app.py` keeps a lazy delegator
  to avoid an import cycle; the GUI body pulls its shared helpers via a
  star import.
- **Provider page/label + CurseForge web URLs → `core/resolver.py`** (G1):
  `addon_provider_page`, `provider_action_label`, `curseforge_search_url`,
  `curseforge_files_url`, `cf_web_version_type` and `SEMI_MANAGED_SOURCES`.
  All flavor-parameterised; `app.py` keeps thin flavor-aware wrappers.
- **Install / provider orchestration → `wowusky/orchestrator.py`** (H):
  the install/update facade (`install_addon`, `uninstall_addon`,
  `install_curseforge*`, `import_zip_file`, `generate_wac_companion`, the
  `SOURCES` version/URL dispatch, the CurseForge URL facades, the catalog
  loader and queries, `get_current_flavor`, `app_log`). `app.py` re-exports
  every public name, so the GUI star import and all call sites keep working.
- **`app.py` is now 493 lines** (down from 5179 at the start of the
  refactor) — the v0.5/v0.7 roadmap target of `< 500 lines` is reached.

### Fixed
- **Profile-switch freeze**: switching profiles no longer rebuilds every
  tab synchronously. `refresh_all()` renders only the visible tab and marks
  the rest dirty; offscreen tabs rebuild lazily when next shown.
- **Post-install freeze**: installing an addon with the Log tab open no
  longer blocks the window while the offscreen Browse/Installed tabs
  re-render.
- **Browse-tab open lag**: the ~240-entry catalog is now rendered in
  batches of 25 via the event loop, so the tab opens instantly and the
  list paints progressively instead of freezing on a single synchronous
  build.

### Internal
- New tests: `tests/test_resolver.py` (15 cases). Provider-characterisation
  and dry-run smoke tests updated to patch the orchestrator module surface.

## [0.6.3] — 2026-06-02

Refactor release — Etappe F. The remaining business logic moves out of
`app.py` into dedicated `wowusky/core/` modules, continuing the journey
toward `app.py < 500 lines`. No user-facing behaviour changes; this is a
pure internal restructuring backed by new unit tests.

### Changed
- **Manager-state persistence → `core/state.py`** (F1): config, profiles,
  per-profile installed DB, the tracked-Wago store, plus path/flavor
  inference and the dict-based profile model. `app.py` re-exports these so
  every existing call site keeps working. `get_wtf_path()` now lives here.
- **Install discovery + DB reconcile → `core/scan.py`** (F2):
  `scan_wow_installations()` (Steam/Wine/Lutris globbing with duplicate
  alias dedupe) and `sync_filesystem_with_db()` (drop stale entries, adopt
  on-disk folders). The catalog is injected as a parameter so the module
  stays decoupled from how `app.py` loads it.
- **Backup / rollback → `core/backup.py`** (F3): `backup_addon_folders`,
  `list_addon_backups`, `latest_backup_for_addon`, `rollback_addon`,
  `rollback_addon_to_backup`, and the full-profile backup operations
  (`create_full_backup`, `restore_full_backup`, `list_full_backups`,
  `full_backup_dir`). `app.py` imports them back as thin re-exports.
- **Wago tracking + WeakAuras → `core/wago.py`** (F4): the tracking list
  helpers (`wago_add`, `wago_remove`, `wago_check_updates`, `wago_search`),
  the SavedVariables scanner (`find_weakauras_savedvariables`,
  `extract_wago_slugs_from_text`,
  `import_existing_weakauras_from_savedvariables`) and the
  WeakAurasCompanion generator. `generate_wac_companion` now takes the TOC
  `interface` and `app_version` as parameters; `app.py` keeps a thin
  wrapper that resolves the active flavor's interface.
- **`app.py` is down from 2616 to 2182 lines.**

### Added
- New test modules: `tests/test_backup_ops.py` (16 tests for the
  profile-aware backup/rollback/full-backup path) and `tests/test_wago.py`
  (15 tests for the tracking list, slug extraction, SavedVariables import
  and companion generation). The suite grows to **264 tests** (49 Tk-gated).

## [0.6.2] — 2026-06-02

Bugfix release — stop a GUI test from blocking the package build with a
modal dialog.

### Fixed
- During `makepkg check()` on a machine with a display, the ImportTab test
  `test_import_tab_install_skips_when_no_file` reached
  `ImportTab._install()` with no file selected, which popped a real
  `messagebox.showerror("Please select a valid ZIP file.")` modal that
  blocked the build indefinitely (the build hung waiting for an "OK"
  click). A new `tests/conftest.py` autouse fixture now stubs all
  `tkinter.messagebox` dialogs (and auto-confirms prompts) across the whole
  suite, so tests stay non-interactive whether or not a display is present.

## [0.6.1] — 2026-06-02

Bugfix release — make the AUR/package build pass on machines with a display.

### Fixed
- Three GUI callback tests (`BackupsTab` restore, `InstalledTab` remove,
  `WeakAurasTab` remove) used a synthetic `event_generate("<Button-1>")`
  that is not reliably delivered to un-mapped widgets on a real X display.
  Headless CI skipped them, so it went unnoticed — but `makepkg check()`
  on a desktop (e.g. CachyOS via `paru`) ran them and failed, aborting the
  build. The tests now invoke the button's bound command directly, which
  is deterministic regardless of display state and still verifies that the
  tab wires the correct callback into `make_button`.

## [0.6.0] — 2026-06-02

GUI extraction — Etappe D abgeschlossen (D6–D9). Alle sieben Tab-Panes sind
jetzt eigenständige Klassen in `wowusky/gui/tabs/`. `app.py` schrumpft von
5179 auf 3385 Zeilen; die Testsuite wächst auf 248 Tests (37 Tk-gated, die
auf headless CI sauber überspringen).

### Added
- `WeakAurasTab`, `InstalledTab`, `BrowseTab`, `ImportTab`, `CurseForgeTab`
  (`gui/tabs/`) — jede Klasse nimmt `ctx: AppContext` + keyword-only
  Callbacks, baut ihr eigenes `.frame`, besitzt UI-State (StringVars,
  Chip-State, Debounce-Timer) und delegiert Threading/Install/Navigation
  an injizierte Callables.
- Neue Tests: `test_gui_browse_tab.py` (8), `test_gui_import_tab.py` (8) —
  zusätzlich zu den früheren `test_gui_weakauras_tab.py` und
  `test_gui_installed_tab.py`.

### Changed
- `render_browse_card` und `make_cf_card` bleiben als injizierte
  `render_card` / `render_mod_card` Callbacks in `app.py` (abhängig von
  `DOWNLOAD_QUEUE`, `trigger_install`, `version_cache` und
  Navigations-Closures).
- Mouse-Wheel-Handler kennt jetzt alle Tab-Canvas-Objekte inklusive
  CurseForge.

## [0.5.5] — 2026-06-01

GUI extraction — Etappe D (D1–D5). Move the Tk layer out of the `app.py`
monolith into a new `wowusky/gui/` package in five staged steps: first the
self-contained, Tk-free / closure-free pieces, then a shared context
object, then the first tab classes. `app.py` drops from ~4323 to ~4117
lines; the test suite grows from 185 to 211 (+7 Tk-gated tests that skip
cleanly when no display is available).

### Added
- `wowusky/gui/` package: `theme.py`, `widgets.py`, `fonts.py`,
  `context.py`, and a `tabs/` subpackage (`log.py`, `backups.py`).
- `AppContext` dataclass (`gui/context.py`) — bundles palette, theme mode,
  font families, font-set, root window, `make_button`, `app_log`, and the
  shared `version_cache` / `checking_versions`. Future tab classes accept
  a single `ctx` instead of capturing dozens of `run_gui()` locals.
- `LogTab` (`gui/tabs/log.py`) — first tab as a class: builds its own
  read-only `ScrolledText` and exposes `.frame` / `.log_msg()`.
- `BackupsTab` (`gui/tabs/backups.py`) — full-backup manager as a class,
  establishing the callback-injection pattern: the tab builds UI and
  renders data, while threading/install logic stays in `app.py` and is
  passed in as plain callables.
- New tests: `test_gui_theme.py` (7), `test_gui_fonts.py` (10),
  `test_gui_context.py` (10), `test_gui_log_tab.py` (2),
  `test_gui_backups_tab.py` (5).

### Changed
- **D1** — `gui/theme.py` (palettes, `detect_system_theme`, `get_palette`,
  `set_theme_mode`; reads via `core.config`, stays Tk-free) and
  `gui/widgets.py` (`UltraHiddenScrollbar` / `HoverScrollbar`).
- **D2** — `gui/fonts.py` (`_font_exists`, `resolve_sans_family`,
  `resolve_mono_family`, `make_font_set`) and the `make_button` factory +
  `_safe_grab` helper moved into `gui/widgets.py`; `run_gui()`'s inline
  font block and button closure replaced with calls + a
  `functools.partial` binding.
- **D3** — `AppContext` constructed inside `run_gui()` alongside the
  existing closures.
- **D4 / D5** — `LogTab` and `BackupsTab` replace their inline frames; the
  `render_backups` closure becomes `BackupsTab.render()`.
- `app.py` imports everything back, so runtime behaviour is unchanged.

## [0.5.4] — 2026-06-01

CurseForge API consolidation — Etappe C3. The API call layer and
install orchestration for CurseForge were duplicated between app.py
and the stub `providers/curseforge_fns.py`. This release moves
everything into the single module.

### Changed
- `providers/curseforge_fns.py` gains the full API call layer
  (`curseforge_json`, `curseforge_mod_from_ref`, `curseforge_get_files`,
  `curseforge_pick_file`, `curseforge_download_url`, `curseforge_search`,
  `curseforge_mod_summary`, `curseforge_api_diagnose`,
  `curseforge_version_from_installed`, `curseforge_url_from_installed`,
  `curseforge_manual_latest`, `curseforge_manual_url`) plus the install
  layer (`install_curseforge`, `install_curseforge_dependencies`) — all
  with injected service callbacks.
- `app.py` — all duplicated CF bodies removed; thin wrappers wire in
  `http_download`, `load_installed`, `save_installed`, and the
  flavor-aware URL builders. app.py drops from ~4507 to ~4323 lines.
- `curseforge_json` now uses `core.http._cache` / `CACHE_TTL` directly
  instead of maintaining a separate `HTTP_CACHE` dict in app.py.

## [0.5.3] — 2026-06-01

Install-path extraction — Etappe C2. `install_addon` and
`uninstall_addon` move from app.py into `core/installer.py` via an
injectable service-callback pattern. app.py retains thin wrappers that
wire in the profile/config state. `_append_version_history` (pure) also
moves to core.

### Changed
- `core/installer.py` gains `append_version_history`, `install_addon`,
  and `uninstall_addon` — full orchestration logic with no GUI or
  profile state, driven by injected callbacks. app.py wrappers delegate
  to these via keyword arguments.
- `app.py` — three large function bodies replaced by thin wrappers;
  `_append_version_history` removed and imported. app.py drops from
  ~4605 to ~4507 lines.

### Added
- `tests/test_installer.py` extended with 9 new tests covering
  `append_version_history` (pure), `install_addon` (dry-run, no-url,
  success, invalid-path), and `uninstall_addon` (not-installed, removes
  folders). Total: 15 installer tests, 185 suite-wide.

## [0.5.2] — 2026-06-01

ZIP-extraction consolidation — Etappe C (start of the install-path
extraction). `core/zipper.py` shipped a tested `smart_extract()` that
nothing actually used, while the GUI install path ran its own recursive
`extract_zip()` in app.py. Those two worlds are now one: the recursive
extractor lives in `core/zipper.py` as the single source of truth and
app.py delegates to it.

### Changed
- `core/zipper.py` gains `extract_addon_zip()` (the recursive,
  TOC-seeking extractor that handles wrapper / `release/` layouts) plus
  the `_find_toc_dirs` / `_copy_addon_dir` helpers and a `sha256_file`
  alias.
- `app.py` — `extract_zip()` is now a thin wrapper around
  `extract_addon_zip()`; the duplicated `_find_toc_dirs`,
  `_copy_addon_dir`, and `sha256_file` definitions were removed and
  imported from `core/zipper`. app.py drops from ~4692 to ~4646 lines.

### Added
- `tests/test_zipper.py` — 5 new tests pinning `extract_addon_zip`
  (release-subdir recursion, nested-library dropping, empty-archive
  error) and the `sha256_file` alias.
- `core/installer.py` — the I/O-light core of the ZIP-import path
  (`guess_addon_name_from_zip`, `build_import_entry`). `app.py`'s
  `import_zip_file()` now delegates to it and only keeps the
  profile-aware `installed.json` write; the duplicated body and name
  guesser were removed from app.py. 6 new tests in
  `tests/test_installer.py`.

## [0.5.1] — 2026-06-01

Provider consolidation — Etappe B. The class-based provider API used
by health_check now delegates to the same `*_fns` functions used by
the GUI. There is one implementation per provider; the two worlds no
longer diverge.

### Changed
- `github.py`, `wowinterface.py`, `tukui.py`, `wago.py` — class bodies
  replaced by thin adapters that delegate to their `*_fns` counterpart.
  All network/version/URL logic lives in one place.
- `github_fns.py` — two diverging flavor-hint tables and two
  `pick_asset` implementations merged into one canonical `pick_asset()`
  function (parameterised on `flavor`). `_github_pick_asset()` kept as
  a GUI-facing wrapper.
- `github_fns.get_current_flavor` and `curseforge_fns.get_current_flavor`
  / `get_curseforge_api_key` now return safe defaults ("retail" / env-var)
  instead of raising `NotImplementedError` — safe to call outside the GUI.

### Fixed
- Health-check was reporting GitHub repos without a formal release or tag
  (e.g. `dbm_classic`, `moveany`, `wim`) as broken ("no version returned").
  They now return a `"<branch> snapshot"` version — healthy and
  installable, consistent with what the GUI showed all along. Resolves
  several false-positives from issue #1.
- `wowi` entries without a downloadable version string now return
  `"manual"` (healthy) instead of `None` (broken), matching GUI behaviour.

### Added
- `providers/github_fns.py` exports `FLAVOR_HINTS` and `pick_asset` —
  usable directly by any future code that needs flavor-aware asset
  selection without importing the full class.

## [0.5.0] — 2026-05-27

First stage of a larger restructuring (Etappe A of v0.5). All five
provider function groups (WoWInterface, Wago, Tukui, GitHub,
CurseForge) move out of app.py into dedicated providers/*_fns.py
modules. Behaviour is identical — pinned by 55 new characterisation
tests added in tests/test_characterize_providers.py before each
extraction.

### Changed
- app.py shrinks from 4939 to ~4694 lines (≈250 lines of provider
  logic moved into providers/*_fns.py modules).
- The provider-dispatch table SOURCES and every call site stay
  unchanged; the functions are imported from their new modules.

### Added
- providers/wowi_fns.py, providers/wago_fns.py, providers/tukui_fns.py,
  providers/github_fns.py, providers/curseforge_fns.py — function-based
  provider modules.
- tests/test_characterize_providers.py — 55 tests that pin the
  observable behaviour of the provider functions (including the B2
  branch-probing fix for GitHub repos that still use 'master',
  the repo_by_flavor flavour-aware repository selection, the
  CurseForge gameVersionTypeId flavor matching, and the Tukui catalog
  setdefault behaviour).

### Notes
- The older class-based providers/*.py modules (github.py, tukui.py,
  wowinterface.py, wago.py, curseforge.py) are left in place untouched
  and are still used by tools/health_check.py and test_providers.py.
  Consolidating the two provider worlds is a separate later stage.
- The Wago helpers wago_add/wago_remove/wago_check_updates and the
  CurseForge install layer (install_curseforge, install_curseforge_
  dependencies, import_zip_file) remain in app.py — they manage local
  state and belong to a later persistence/install stage.

## [0.4.12] — 2026-05-23

Catalog cleanup.

### Fixed
- Removed two accidental duplicate catalog entries: 'omen_cf' and
  'leatrix_plus_cf' each pointed at the same curseforge_web download
  as their builtin counterpart ('omen', 'leatrix_plus'). The shipped
  catalog goes from 241 to 239 entries. The 28 intentional
  multi-source entries (same addon via different providers, e.g.
  ElvUI via tukui and curseforge_web) are unaffected.

### Added
- tests/test_catalog.py: two consistency checks — no two entries may
  share a name with the same provider, and all catalog ids must be
  unique. 111 tests total.

## [0.4.11] — 2026-05-23

Release-Korrektur zu 0.4.10.

### Fixed
- README-Versionsangaben (Banner, Install-Snippets) waren in 0.4.10
  versehentlich bei 0.4.9 geblieben. 0.4.10 wurde nie als AUR-Paket
  veröffentlicht; 0.4.11 ist der erste vollständige Stand der
  SPDX-Lizenz-Umstellung.

## [0.4.10] — 2026-05-23

Packaging fix.

### Fixed
- Replaced the deprecated `license = { text = "MIT" }` TOML table
  with the modern SPDX string `license = "MIT"` plus `license-files`,
  and removed the deprecated `License ::` classifier. setuptools
  warned these would stop working after 2027-Feb-18. Build now
  emits no deprecation warnings. Requires setuptools >= 77.

## [0.4.9] — 2026-05-22

Packaging fix. Corrects the GitHub repository URL across the project.
No code changes — `app.py` and all 109 tests are identical to 0.4.7.

### Fixed
- **Wrong GitHub URL everywhere.** PKGBUILD, `.SRCINFO`, README,
  CONTRIBUTING, `pyproject.toml` and the AUR guide all pointed at
  `github.com/wowusky/wowusky`. The actual repository is
  `github.com/borunsky/wowusky`. This was build-breaking, not
  cosmetic: the PKGBUILD `source=()` line builds the release-tarball
  URL from it, so `makepkg` would have failed with a 404. All 25
  occurrences across 6 files are corrected, including the historical
  release link references in this changelog.

### Note
The `sha256sums` in the PKGBUILD is still `SKIP`. It can only be
filled in after the v0.4.9 tag is pushed and the tarball exists on
GitHub — see step 2 of `AUR-RELEASE.md` (`updpkgsums`).



Packaging release. Makes the AUR submission actually publishable.
No code changes — `app.py` and all 109 tests are identical to 0.4.7.

### Fixed
- **PKGBUILD `pkgver` was stuck at 0.4.1.** It would have pulled the
  broken v0.4.1 tarball — the release that could not even be
  imported. Bumped to 0.4.8.
- **`.SRCINFO` was missing entirely.** The AUR requires this file;
  a submission without it is rejected. Added, in the format
  `makepkg --printsrcinfo` produces.
- **`check()` could fail in a clean build container** — it runs
  `pytest` but `python-pytest` was not declared. Added as
  `checkdepends`.
- PKGBUILD `LICENSE` install no longer swallows errors with
  `|| true`; the file exists and must be installed.

### Added
- **`AUR-RELEASE.md`**: step-by-step publishing guide — tagging,
  checksum generation with `updpkgsums`, local `makepkg -si` test,
  `.SRCINFO` regeneration, and the AUR push.

### Verified
- `python -m build --wheel --no-isolation` (the PKGBUILD `build()`
  step) runs and produces `wowusky-0.4.8-py3-none-any.whl`.
- `python -m installer` (the `package()` step) lays down the
  `wowusky` entry point and all modules correctly.
- All nine files the PKGBUILD installs (README, LICENSE, .desktop,
  SVG, five PNG icons) exist and are valid.

### Still required before the AUR goes live
Tagging `v0.4.8` on GitHub, creating the release, running
`updpkgsums` for the real checksum, a local `makepkg -si`, and the
AUR account/push. See `AUR-RELEASE.md`.



Bug-fix release. Fixes a regression introduced by the B11 fix in
v0.4.6, caught immediately in the next smoke-test run.

### Fixed
- **B12 — flavor shown as "unknown", catalog unfiltered.** The B11
  fix in v0.4.6 correctly left a fresh data directory unconfigured,
  so `get_active_profile()` returns `{}`. But `set_addons_path()`
  had an `if prof:` guard that — with an empty profile — skipped
  profile creation entirely. The path was "set" but no profile
  carried it: `get_current_flavor()` returned `None`, the flavor
  displayed as "unknown", and the catalog was shown without
  flavor filtering (all 241 entries across every flavor).
  `set_addons_path()` now creates a profile via
  `add_or_update_profile()` when none exists, and updates the
  existing one in place otherwise.

### Note
This was a regression in v0.4.6, not a pre-existing bug. The B11
fix changed an invariant (`load_profiles()` no longer always
returns a non-empty profile set) and `set_addons_path()` was the
one caller that silently relied on the old behaviour. The v0.4.6
test suite did not cover the "unconfigured → set path → profile
must exist" sequence; v0.4.7 adds it.

### Added
- **`tests/test_b12_set_addons_path.py`**: four regression tests —
  a profile is created from an unconfigured state, the flavor
  resolves afterwards, every flavor directory marker resolves to
  its key, and an existing profile is updated in place rather than
  duplicated. 109 tests total (was 105).



Bug-fix release. One issue (B11) found while running the v0.4.5
smoke test — the deeper root cause behind B3.

### Fixed
- **B11 — autodetection silently created a profile.** On a fresh data
  directory, `load_profiles()` ran `scan_wow_installations()`, took
  the first WoW install it found, wrote it into `profiles.json` and
  made it the active profile — all without asking. The GUI's
  "Connect WoW installation" dialog and the terminal path prompt
  were therefore skipped, because `get_addons_path()` already
  returned the autodetected path. This is why three separate smoke-
  test attempts kept hitting the real WoW install instead of the
  intended isolated directory; it would equally surprise a real
  first-time user. `load_profiles()` now returns an empty,
  unpersisted `{"active": None, "profiles": {}}` for an unconfigured
  directory. Autodetection is still used — but only by the path
  picker and terminal prompt, to *offer* choices the user confirms.
  Migration of a pre-0.4 single-profile `config.json` is unchanged,
  since that path was a deliberate earlier user choice.
- `get_active_profile_id()` keeps a `"default"` fallback so callers
  that build filenames from the id never see `None` in the brief
  unconfigured window.

### Note on B3
The v0.4.5 changelog listed B3 (a smoke-test run hitting the real
install) as "fixed by B10". That was only half right — B10 made the
data directory redirectable, but B11 is what actually forced the
real install back in. B3 is now genuinely resolved.

### Added
- **`tests/test_b11_no_autodetect.py`**: four regression tests — a
  fresh dir stays unconfigured and writes nothing, `get_addons_path()`
  is `None` when unconfigured, autodetection does not run when
  `profiles.json` already exists, and a legacy `config.json` is
  still migrated. 105 tests total (was 101).



Bug-fix release. Eight issues found during a hands-on smoke test of
the v0.4.4 GUI and terminal mode.

### Fixed
- **B10 — `app.py` ignored `XDG_DATA_HOME`.** The GUI re-derived its
  data directory with `os.path.expanduser("~/.local/share/wowusky")`,
  a hardcoded path that bypassed the XDG-aware `wowusky.core.paths`
  module entirely. The data location could not be redirected, which
  made isolated testing impossible and let the GUI and the
  documented core paths disagree. `app.py` now imports the path
  constants from `wowusky.core.paths`. `core.paths` gained `CONFIG_DIR`
  (alias of `DATA_DIR`) and `INSTALLED_FILE` (alias of
  `LEGACY_INSTALLED_FILE`) so the GUI can import every name it needs.
- **B1 — dry-run still downloaded addons.** The `is_dry_run()` checks
  only guarded filesystem writes; an install in dry-run mode fetched
  the full ZIP over the network before stopping. `install_addon` now
  returns early, before any provider or download call, in dry-run
  mode.
- **B2 — GitHub addons 404 on `master`-branch repos.** When the
  GitHub API was unavailable (commonly the 60-request/hour
  unauthenticated rate limit), `github_default_branch` blindly
  assumed `main`. Repos using `master` — e.g. ShadowedUnitFrames —
  then produced a 404 on download. The fallback now probes the
  actual branch archive URLs and uses whichever of `main`/`master`
  exists.
- **B6 — "Checking…" never resolved for WeakAuras Companion.** The
  Browse-tab button for `internal_wac` addons sat permanently on
  the disabled "Checking…" state, because locally-generated addons
  never get a remote version check. They now show "✓ Installed".
- **B9 — addons path stored in two places.** `set_addons_path` wrote
  the path into both `profiles.json` and a legacy `config.json`
  field, creating two sources of truth that could diverge.
  `profiles.json` is now authoritative; the legacy field is dropped
  from `config.json` when encountered. `get_addons_path` keeps a
  read-only fallback for pre-0.4.5 config files.
- **B4 — terminal install prompt swallowed invalid input.** Entering
  a non-number (or an out-of-range number) at the install prompt was
  silently ignored. It now prints an explicit error.
- **B5 — flavor name shown inconsistently.** The terminal printed the
  internal key (`anniversary`) while the GUI showed the display name
  (`TBC Anniversary`). The terminal now shows `Display Name [key]`,
  matching the GUI.

### Investigated, no change needed
- **B3** — a smoke-test run hit the real WoW install instead of an
  isolated directory. Root cause was B10; fixed by B10.
- **B7** — suspected missing confirmation before "Remove". The
  confirmation dialog already exists; no change.
- **B8** — project files and app data coexisting in
  `~/.local/share/wowusky`. A user-side mixup, mitigated now that
  B10 makes the data directory redirectable.

### Added
- **`tests/test_smoke_fixes_v045.py`**: six regression tests pinning
  B1, B9 and B10 so they cannot silently return. 101 tests total
  (was 95).

Documentation-and-honesty release. No runtime behaviour changes.

### Fixed
- **README `app.py` line count**: claimed `~4600`, real value is
  4852. Updated, and a new test enforces that the README stays
  within 50 lines of `wc -l wowusky/app.py`.
- **README test count**: claimed `79 tests`, real value at v0.4.3
  is 89. Bumped.
- **README install snippets** still referenced `wowusky-v0.4.0.zip`
  and the v0.4.0 wheel filename. Now tracks the current version,
  and a test enforces that they stay in sync with
  `wowusky.__version__`.
- **README banner** ("◆ wowusky vX.Y.Z") was stuck at v0.4.0 — now
  matches the package version and is covered by a test.
- **`app.py` module docstring** said the file "imports the shared
  logic" from `wowusky.providers`. It doesn't — `app.py` has zero
  imports from `wowusky.providers`. Rewritten to describe what
  the file actually does, plus an explicit note that the
  provider-registry integration is scheduled for v0.5. A test
  guards against the docstring drifting back out of sync with
  reality.
- **CHANGELOG line count for v0.4.0**: said `5179 → 4677`. Real
  value was 4852 even at the time. Corrected.
- **CHANGELOG link references** for `[0.4.1]`, `[0.4.2]`, `[0.4.3]`,
  `[0.4.4]` were missing from the footer. Added.
- **CHANGELOG `[0.4.0]` intro** rewritten to accurately describe
  which packages `app.py` actually imports from (core, catalog)
  and which it does not (providers), with a forward pointer to
  v0.5.

### Added
- **`tests/test_docs_consistency.py`**: six tests covering the
  README/CHANGELOG/code-docstring drift modes above. 95 tests
  total now (was 89).
- **README development section**: documents the new `--offline`
  flag for the health check and the per-push CI steps added in
  v0.4.2 / v0.4.3.

## [0.4.3] — 2026-05-21

CI hardening release. Closes the gaps that let the 0.4.1 provider
import bug ship green.

### Added
- **`wowusky.tools.health_check --offline`** mode: skips the network
  and only exercises provider lookup + ``resolve()`` for every
  catalog entry. Fast, deterministic, suitable for the per-push
  workflow.
- **`_INTERNAL_PROVIDERS`** registry inside the health check.
  Catalog entries served by internal flows (currently
  ``internal_wac`` for ``WeakAurasCompanion``) are reported as
  healthy with version ``"internal"`` instead of being flagged as
  ``unknown provider``.
- **`tests/test_health_check_offline.py`**: 10 tests covering the
  three failure modes (missing/unknown provider, unresolvable
  reference), the happy paths, a guard ensuring the offline path
  never opens a socket, and a sweep over the real shipped catalog.
- **CI step `Catalog health check (offline)`** in the lint-and-test
  workflow. Runs ``python -m wowusky.tools.health_check --offline``
  on every push. A manifest edit that introduces a typo'd provider
  name or unresolvable reference now fails CI before merge.

### Changed
- **`[tool.pytest.ini_options]` defaults centralised in
  `pyproject.toml`**: ``addopts = "-ra --strict-markers
  --strict-config"`` plus ``xfail_strict = true``. Local ``pytest``
  and CI now share the same strict configuration, so collection
  errors, unknown markers, and config typos can no longer pass as
  a silently green run.
- CI ``Tests`` step simplified to bare ``pytest -q`` since the
  flags are now in ``pyproject.toml``.

### Test count
- 89 tests collected, 89 passing (was 79 / 79 in 0.4.2).

## [0.4.2] — 2026-05-21

Bugfix release. Restores `wowusky.providers` importability, which was
broken in 0.4.1 and went undetected by CI.

### Fixed
- **`ModuleNotFoundError: No module named 'wowusky.providers.common'`**
  on every `import wowusky.providers`. All five provider modules
  (`curseforge`, `github`, `tukui`, `wago`, `wowinterface`) imported
  `HttpError` and `get_json` from a non-existent `providers.common`
  module; the symbols live in `wowusky.core.http`. The fix adds a
  thin re-export module at `wowusky/providers/common.py` so existing
  provider imports keep working and shared provider helpers have a
  documented home going forward.
- **`pytest` collection error in `tests/test_providers.py`** caused
  by the same import failure. With the shim in place all 79 tests
  collect and pass (vs. 56 collectable in 0.4.1).
- **`wowusky.tools.health_check` startup crash** — `from
  wowusky.providers import get_provider` failed for the same reason
  as above. The weekly health-check workflow would have opened an
  issue against every catalog entry instead of only broken ones.
- **Built wheel was unusable**: `pip install wowusky-0.4.1*.whl` then
  `python -m wowusky` died on the same provider import. The 0.4.2
  wheel imports cleanly end-to-end.

## [0.4.1] — 2026-05-21

Bugfix release for a launch failure reported by the first round of
testers.

### Fixed
- **`ModuleNotFoundError: No module named 'wowusky.catalog'`** when
  invoking ``python -m wowusky`` from inside the ``wowusky/`` package
  directory or via ``python3 wowusky/__main__.py`` directly. The fix:
  ``__main__.py`` now prepends the real package parent to ``sys.path``
  before its first internal import, so subpackages are importable
  regardless of where Python was launched from.
- **Root-level ``wowusky.py`` wrapper** updated for the same reason:
  it now self-inserts its directory into ``sys.path`` so
  ``python3 /full/path/to/wowusky.py`` works regardless of the
  caller's current working directory.
- **Source ZIP no longer ships byte-cache directories**
  (``__pycache__/``, ``*.pyc``) or stray ``build/`` artefacts.
  Those could collide with the user's Python version and roughly
  doubled the download size.
- Removed an empty placeholder directory ``wowusky/gui/tabs/`` that
  served no purpose at this stage.

## [0.4.0] — 2026-05-21

The "split the monolith" release. v0.3 had stub `core/` and `providers/`
directories that the rest of the code didn't actually use. v0.4 populates
those modules: `app.py` imports from `wowusky.core` and `wowusky.catalog`
and the duplicated flavor/TOC/HTTP/catalog literals are gone.

> **Note (added in v0.4.4):** the original wording of this entry claimed
> `app.py` imports from `wowusky.providers` as well. It does not. The
> provider registry is fully implemented and used by the health-check
> tool, but the GUI's install/update path still calls its own
> provider helpers. Migrating that path onto `wowusky.providers` is
> scheduled for v0.5. See the v0.4.4 entry for the README/docs
> corrections that followed from this.

### Added
- `wowusky/core/` modules: `paths`, `flavors`, `toc`, `http`, `versions`,
  `config`, `profiles`, `installed`, `backup`, `filesystem`, `zipper`,
  `logging_setup`. All documented and isolated-testable.
- `wowusky/providers/` implementations: Tukui, GitHub (with flavor-aware
  release-asset picker), WoWInterface, CurseForge (API + web fallback),
  Wago. A small provider registry replaces the previous free-function
  approach.
- Manifest-based catalog under `wowusky/catalog/manifests/`. User
  overrides via `~/.local/share/wowusky/manifests/*.json`.
- Per-profile installed database (`installed/<profile_id>.json`) and
  per-profile backup directories (`backups/<profile_id>/<addon_id>/`),
  pruned to the 3 most recent snapshots automatically.
- Backup + restore primitives (`wowusky.core.backup`) used before every
  install/update.
- `wowusky.tools.health_check` CLI: pings every catalog entry and exits
  non-zero on failures. Runs weekly in CI and opens an issue for broken
  entries.
- `pyproject.toml` configured for `python -m build`; produces both
  sdist and wheel cleanly.
- `LICENSE` (MIT), `CHANGELOG.md`, freedesktop entry, scalable SVG icon.
- Test suite expanded from 6 to 79 tests covering TOC parsing, flavor
  compatibility, profile lifecycle, manifest merging, ZIP smart-extract,
  backup pruning + rollback, provider resolve, version normalisation.

### Changed
- `app.py` reduced from 5179 → 4852 lines by removing duplicated
  `WOW_FLAVORS`, `FLAVOR_COMPATIBILITY`, TOC helpers, HTTP helpers and
  the 338-line inline `ADDON_CATALOG` literal plus the 195-tuple
  `EXTRA_CURSEFORGE_WEB_ADDONS` list.
- Version bumped from `0.3.0a0` to `0.4.0`. The User-Agent string now
  reads `wowusky/0.4.0` instead of the hard-coded `wowusky/0.3`.
- `PKGBUILD` rewritten to use `python -m build` + `python -m installer`
  and an upstream tarball URL. AUR-ready apart from `sha256sums`,
  which need `updpkgsums` after the first tag.
- CI matrix now covers Python 3.10, 3.11, 3.12 and additionally runs
  `ruff check`, `ruff format --check`, a build of the wheel and an
  import test of the installed wheel.

### Fixed
- **Variable shadowing in `core.backup.make_backup`**: the local name
  `existing` was reused for both "addon folders to back up" and "ZIP
  archives already in the backup dir". The second assignment masked
  the first, leaving the resulting archive empty. Renamed to
  `existing_folders` / `existing_archives`. Found by the new
  `test_make_backup_creates_archive_with_addon_contents` test.
- **Missing `_http` symbol in `app.py`** after the HTTP refactor:
  `wago_fetch_info` and `wago_fetch_encoded` still called the old
  helper. Replaced with an explicit re-export of `wowusky.core.http._open`.
  Found by `ruff F821`.
- **`log_file` typo in `app.py`** reset-state code path — should have
  been `app_log`. Fixed; found by `ruff F821`.
- **Duplicate `is_compatible` definition** in `filter_catalog_by_flavor`
  shadowed the imported core helper. The local function is now removed
  and the shared one is used.
- **Backup filename collisions** within a single second: archive names
  now disambiguate by appending `-1`, `-2`, … when a base timestamp+tag
  combination already exists in the backup directory.

### Migrated
- Pre-0.4 `~/.local/share/wowusky/installed.json` (single profile) is
  copied into `installed/<active_profile>.json` on first launch and the
  old file is renamed to `installed.json.migrated`.

## [0.3.0-alpha] — 2026-05-19

- Per-profile UI scaffolding, CurseForge browser-import workflow,
  community manifest seed, healthy GitHub fallback chain
  (release → tags → branch ZIP). Project structure prepared for the
  v0.4 refactor (stub `core/`, `providers/`, `gui/` directories).

## Earlier — pre-0.3

Single-file GUI prototype focused on a single WoW installation.
See git history for details.

[0.8.0]:         https://github.com/borunsky/wowusky/releases/tag/v0.8.0
[0.7.0]:         https://github.com/borunsky/wowusky/releases/tag/v0.7.0
[0.6.4]:         https://github.com/borunsky/wowusky/releases/tag/v0.6.4
[0.6.3]:         https://github.com/borunsky/wowusky/releases/tag/v0.6.3
[0.6.2]:         https://github.com/borunsky/wowusky/releases/tag/v0.6.2
[0.6.1]:         https://github.com/borunsky/wowusky/releases/tag/v0.6.1
[0.6.0]:         https://github.com/borunsky/wowusky/releases/tag/v0.6.0
[0.5.5]:         https://github.com/borunsky/wowusky/releases/tag/v0.5.5
[0.5.4]:         https://github.com/borunsky/wowusky/releases/tag/v0.5.4
[0.5.3]:         https://github.com/borunsky/wowusky/releases/tag/v0.5.3
[0.5.2]:         https://github.com/borunsky/wowusky/releases/tag/v0.5.2
[0.5.1]:         https://github.com/borunsky/wowusky/releases/tag/v0.5.1
[0.5.0]:         https://github.com/borunsky/wowusky/releases/tag/v0.5.0
[0.4.12]:         https://github.com/borunsky/wowusky/releases/tag/v0.4.12
[0.4.11]:         https://github.com/borunsky/wowusky/releases/tag/v0.4.11
[0.4.10]:         https://github.com/borunsky/wowusky/releases/tag/v0.4.10
[0.4.9]:         https://github.com/borunsky/wowusky/releases/tag/v0.4.9
[0.4.8]:         https://github.com/borunsky/wowusky/releases/tag/v0.4.8
[0.4.7]:         https://github.com/borunsky/wowusky/releases/tag/v0.4.7
[0.4.6]:         https://github.com/borunsky/wowusky/releases/tag/v0.4.6
[0.4.5]:         https://github.com/borunsky/wowusky/releases/tag/v0.4.5
[0.4.4]:         https://github.com/borunsky/wowusky/releases/tag/v0.4.4
[0.4.3]:         https://github.com/borunsky/wowusky/releases/tag/v0.4.3
[0.4.2]:         https://github.com/borunsky/wowusky/releases/tag/v0.4.2
[0.4.1]:         https://github.com/borunsky/wowusky/releases/tag/v0.4.1
[0.4.0]:         https://github.com/borunsky/wowusky/releases/tag/v0.4.0
[0.3.0-alpha]:   https://github.com/borunsky/wowusky/releases/tag/v0.3.0-alpha
