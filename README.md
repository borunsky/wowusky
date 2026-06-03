# wowusky

**Minimalist World of Warcraft addon manager for Linux.**

```
◆ wowusky v0.6.4    Browse  Installed  WeakAuras  Import  Log   ● TBC Anniversary ⚙
```

Standard-library Python · CachyOS/Arch-friendly · 241+ curated addons across
Tukui · GitHub · WoWInterface · WeakAuras/Wago · CurseForge.

---

<!-- WHATS-NEW:START -->
<!-- This section is generated from the latest CHANGELOG.md entry by
     .github/workflows/readme-version-sync.yml on each published release.
     Edit CHANGELOG.md, not the text between these markers. -->
## What's new in v0.6.4

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
<!-- WHATS-NEW:END -->

---

## Install

### Local install (CachyOS / Arch / any Linux)

```bash
unzip wowusky-v0.6.4.zip
cd wowusky-v0.6.4
chmod +x install.sh
./install.sh
```

The script:
- copies the source tree to `~/.local/share/wowusky/`
- creates a launcher at `~/.local/bin/wowusky`
- installs a desktop entry and icon for your menu
- migrates pre-0.4 config / installed lists

If `~/.local/bin` is not in your `PATH`, the installer reminds you.

### Run without installing

```bash
./run-local.sh
```

### From source as a wheel

```bash
pip install build
python -m build
pip install dist/wowusky-0.6.4-py3-none-any.whl
```

### From PyPI (after first tagged release)

```bash
pipx install wowusky
wowusky
```

---

## First run

1. Settings dialog opens on first launch.
2. Pick the WoW client you want to manage (Anniversary / Retail / Classic / …).
3. wowusky scans `Interface/AddOns/`, reads TOC headers, builds an inventory.
4. Browse-tab shows the 241-entry catalog filtered to the chosen flavor.

You can add more profiles later from the same Settings dialog. Switch
profiles from the header — each one has its own installed list, its own
backup history, and its own auto-update flag.

---

## CurseForge

CurseForge restricts API access for third-party tools. wowusky never
scrapes their site or proxies ZIPs. Instead:

- **`Open in CurseForge`** in the catalog opens the project page so you
  can download the ZIP yourself.
- **`Import latest from Downloads`** in the Import tab grabs the newest
  ZIP from `~/Downloads` and installs it.
- **Optional API key**: if you have an Eternal API key, enter it under
  Settings and direct lookups + updates become available for numeric
  CurseForge IDs.

---

## Project layout

```
wowusky/
├── wowusky/
│   ├── __init__.py
│   ├── __main__.py
│   ├── app.py              ← install orchestration + provider/core wiring (~493 lines)
│   ├── core/
│   │   ├── paths.py        ← XDG paths, per-profile locations
│   │   ├── flavors.py      ← WoW versions + compatibility rules
│   │   ├── toc.py          ← .toc parser
│   │   ├── http.py         ← cached HTTP with retry
│   │   ├── versions.py     ← version normalisation
│   │   ├── config.py       ← global config + legacy migration
│   │   ├── profiles.py     ← profile dataclass + CRUD
│   │   ├── installed.py    ← per-profile installed DB
│   │   ├── backup.py       ← rollback archives
│   │   ├── filesystem.py   ← WoW install detection (Steam/Wine/Lutris)
│   │   ├── zipper.py       ← smart GitHub-wrapper extraction
│   │   ├── state.py        ← manager-state persistence (config/profiles/installed/wago)
│   │   ├── scan.py         ← WoW install discovery + filesystem/DB reconcile
│   │   ├── wago.py         ← Wago.io tracking + WeakAurasCompanion generator
│   │   ├── resolver.py     ← provider page/label dispatch + CurseForge web URLs
│   │   └── logging_setup.py← rotating file logs + UI ring buffer
│   ├── providers/
│   │   ├── base.py         ← AddonRef + AddonProvider protocol
│   │   ├── tukui.py
│   │   ├── github.py       ← with flavor-aware asset picker
│   │   ├── wowinterface.py
│   │   ├── curseforge.py   ← API and web fallback
│   │   └── wago.py
│   ├── catalog/
│   │   ├── __init__.py     ← manifest loader (builtin + user overrides)
│   │   └── manifests/
│   │       ├── builtin.json          (42 curated addons)
│   │       ├── community-seed.json   (4 entries)
│   │       └── curseforge-seed.json  (195 CurseForge slugs)
│   ├── gui/
│   │   ├── main.py          ← run_gui: main window, sidebar, tab/trigger wiring
│   │   ├── context.py       ← AppContext dataclass (shared GUI state)
│   │   ├── fonts.py         ← font-family resolution + font-set builder
│   │   ├── theme.py         ← palettes + dark/light detection
│   │   ├── widgets.py       ← reusable Tk widgets + make_button + _safe_grab
│   │   ├── dialogs/
│   │   │   ├── settings.py      ← SettingsDialog (WoW path / settings modal)
│   │   │   └── addon_details.py ← AddonDetailsDialog (catalog addon detail)
│   │   └── tabs/
│   │       ├── log.py        ← LogTab (activity-log pane)
│   │       ├── backups.py    ← BackupsTab (full-backup manager)
│   │       ├── weakauras.py  ← WeakAurasTab (Wago.io aura tracker)
│   │       ├── installed.py  ← InstalledTab (installed-addon manager)
│   │       ├── browse.py     ← BrowseTab (catalog browser)
│   │       ├── importzip.py  ← ImportTab (manual ZIP import)
│   │       └── curseforge.py ← CurseForgeTab (CurseForge search)
│   └── tools/
│       └── health_check.py  ← CLI that pings every catalog entry
├── tests/                   ← 109 tests
├── packaging/
│   ├── wowusky.desktop
│   └── wowusky.svg
├── .github/workflows/
│   ├── ci.yml               ← lint + test + build on every push
│   └── health-check.yml     ← weekly provider health check
├── pyproject.toml
├── PKGBUILD                 ← Arch package recipe
├── ruff.toml
├── install.sh
└── README.md
```

---

## Data layout

```
~/.local/share/wowusky/
├── config.json              global settings (theme, API key, dry-run)
├── profiles.json            WoW installations + active profile
├── wago.json                tracked WeakAuras (account-wide)
├── installed/
│   └── <profile_id>.json    per-profile installed-addon database
├── backups/
│   └── <profile_id>/<addon_id>/<timestamp>.zip
├── manifests/               user-supplied catalog extensions / overrides
└── logs/                    rotating wowusky.log + 7-day backlog
```

---

## Development

```bash
git clone https://github.com/borunsky/wowusky
cd wowusky

# tests
pytest -q

# lint
ruff check wowusky tests

# build wheel
python -m build

# run health check
#   --offline: provider lookup + resolve only, no network (CI default)
#   no flag:   also pings every catalog entry against its real API
python -m wowusky.tools.health_check --offline
python -m wowusky.tools.health_check
```

CI runs ruff, an import smoke test, the offline catalog health check
and the test suite on Python 3.10/3.11/3.12, and builds the package
on every push. The full network health-check workflow runs Mondays
at 06:00 UTC and opens an issue for any broken catalog entries.

---

## Roadmap

The v0.4 refactor was the prerequisite. Now planned:

- **v0.5** — finish GUI extraction (move tab classes from `app.py` into
  `wowusky/gui/`), reach `app.py < 500 lines`.
- **v0.6** — dependency resolver (Ace3, LibSharedMedia etc. pulled
  automatically when an addon declares `"depends": [...]`).
- **v0.7** — CLI surface: `wowusky install elvui`, `wowusky list --updates`,
  `wowusky profile switch retail`.
- **v0.8** — optional systemd-user-service for daily update checks.

See [CHANGELOG.md](CHANGELOG.md) for what landed in each release and
[CONTRIBUTING.md](CONTRIBUTING.md) if you'd like to send a patch.

---

## Licence

MIT. See [LICENSE](LICENSE).

The catalog manifests are metadata only and do not redistribute any
addon code. wowusky downloads addons directly from each addon's
official source on demand.
