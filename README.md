# wowusky

**Minimalist World of Warcraft addon manager for Linux.**

```
◆ wowusky v0.6.0    Browse  Installed  WeakAuras  Import  Log   ● TBC Anniversary ⚙
```

Standard-library Python · CachyOS/Arch-friendly · 241+ curated addons across
Tukui · GitHub · WoWInterface · WeakAuras/Wago · CurseForge.

---

## What's new in v0.4

This release is the long-promised refactor. The 5000-line monolith has been
split into reusable modules, and the project now has the bones of a real
maintained package.

### Architecture
- **Modular layout** under `wowusky/core/`, `wowusky/providers/`,
  `wowusky/catalog/`. app.py is down from 5179 to 3385 lines as provider and core logic moves into wowusky/providers/ and wowusky/core/
  shed its duplicated `WOW_FLAVORS`, TOC helpers, HTTP helpers, and
  the inlined 241-entry catalog literal in favour of importing from
  `wowusky.core` and `wowusky.catalog`.
  - **What still ships in `app.py`**: the Tk GUI, the addon
    install/update orchestration, and a self-contained set of
    provider helpers that the GUI calls directly. The new
    `wowusky.providers` package (Tukui, GitHub, WoWInterface,
    CurseForge, Wago) ships as a complete, tested registry and is
    used by `wowusky.tools.health_check` today; migrating the GUI's
    install path onto it is scheduled for v0.5.
- **Per-profile installed.json** plus a new `profiles.json` for multi-version
  setups. A pre-0.4 single-profile install is migrated automatically.
- **Backup & rollback**: every install/update archives the old folders into
  a per-profile, per-addon ZIP under `~/.local/share/wowusky/backups/`,
  pruned to the 3 most recent.
- **Centralised HTTP layer** with response cache and exponential retry,
  used by `wowusky.core` and `wowusky.providers`.

### Catalog
- **Manifest-based**: the 241 entries (42 builtin + 4 community seed + 195
  CurseForge slugs) now live in `wowusky/catalog/manifests/*.json` instead
  of being inlined in Python. User overrides live under
  `~/.local/share/wowusky/manifests/`.

### Quality
- **Test suite expanded from 6 → 109 tests** covering TOC parsing, flavor
  compatibility, profile lifecycle, manifest merging, ZIP smart-extract,
  backup pruning/rollback, provider resolve, version comparisons, and the
  offline catalog health check.
- **Ruff in CI** with a strict ruleset for the new modules and per-file
  ignores for the legacy GUI. Caught three real bugs during introduction
  (variable shadowing in `make_backup`, missing `_http` import after
  refactor, undefined `log_file` typo).
- **Import smoke and offline catalog health check** run on every push
  (since v0.4.2 / v0.4.3) so a missing module or a typo'd provider name
  in a manifest fails CI immediately.
- **Weekly provider health-check** workflow opens automated issues for
  broken catalog entries.
- **Build + install verification** runs on every push (Python 3.10/3.11/3.12).
- **Proper PKGBUILD** for AUR submission, MIT license file, desktop entry,
  scalable SVG icon.

---

## Install

### Local install (CachyOS / Arch / any Linux)

```bash
unzip wowusky-v0.6.0.zip
cd wowusky-v0.6.0
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
pip install dist/wowusky-0.6.0-py3-none-any.whl
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
│   ├── app.py              ← Tk GUI + install orchestration (~3385 lines)
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
│   │   ├── context.py       ← AppContext dataclass (shared GUI state)
│   │   ├── fonts.py         ← font-family resolution + font-set builder
│   │   ├── theme.py         ← palettes + dark/light detection
│   │   ├── widgets.py       ← reusable Tk widgets + make_button + _safe_grab
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
