# wowusky

**Minimalist World of Warcraft addon manager for Linux.**

```
◆ wowusky v0.14.0    Browse  Installed  WeakAuras  Import  Log   ● TBC Anniversary ⚙
```

Standard-library Python · CachyOS/Arch-friendly · 241+ curated addons across
Tukui · GitHub · WoWInterface · WeakAuras/Wago · CurseForge.

---

<!-- WHATS-NEW:START -->
<!-- This section is generated from the latest CHANGELOG.md entry by
     .github/workflows/readme-version-sync.yml on each published release.
     Edit CHANGELOG.md, not the text between these markers. -->
## What's new in v0.9.5

### Added
- **Dependency preview in the detail panel**: addons that declare catalog
  dependencies now show a "Also installs N dependencies" hint in the Install
  CTA area, and the Dependencies section in the scroll body labels each dep
  as *installed* (accent-colored) or *required* — unknown ids are flagged as
  *not in catalog*. Backed by the new `addon.deps` bridge method and
  `orchestrator.dependency_preview()`.
- **Bulk update / remove on the Installed tab**: every row now has a checkbox;
  a header checkbox selects/deselects all visible rows. When rows are selected
  a context bar appears in the toolbar with **Update (N)** (only for rows that
  have a pending update) and **Remove** bulk actions. Backed by the new
  `installed.removeMany` bridge method.
- **Scheduled-update timer (systemd)**: a new `wowusky schedule` CLI command
  (`status` / `enable [--interval hourly|daily|weekly]` / `disable`) installs
  and manages a systemd *user* timer that runs `wowusky update -q` on a
  schedule. The desktop Settings screen gains a **Scheduled Updates** section
  that shows the current timer state and lets you enable, reconfigure, or
  remove the timer — all in-app. Backed by `wowusky/core/schedule.py` and
  three new bridge methods (`schedule.status`, `schedule.enable`,
  `schedule.disable`). Degrades gracefully where systemd is unavailable.
- **Import from Downloads (desktop)**: the Settings screen gains an **Import
  from Downloads** section that scans `~/Downloads` for `.zip` files, guesses
  the catalog match for each (by fuzzy-matching the filename against addon ids
  and names), and installs them with one click. Multiple ZIPs are shown
  newest-first. Backed by `orchestrator.scan_download_zips_annotated()` +
  `guess_catalog_match()` and two new bridge methods (`downloads.scan`,
  `downloads.import`).
<!-- WHATS-NEW:END -->

---

## Install

### Local install (CachyOS / Arch / any Linux)

```bash
unzip wowusky-v0.14.0.zip
cd wowusky-v0.14.0
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
pip install dist/wowusky-0.14.0-py3-none-any.whl
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
│   ├── cli.py              ← CLI surface (install/update/status/search/…)
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
├── tests/                   ← 349 tests
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

- ~~**v0.5/v0.6.4** — finish GUI extraction, reach `app.py < 500 lines`.~~ ✅ done
- ~~**v0.7.0** — dependency resolver: catalog entries declare
  `"depends": [...]` and wowusky installs them automatically, in order,
  before the addon itself.~~ ✅ done
- ~~**v0.8.0** — CLI surface: `wowusky install elvui`, `wowusky update`,
  `wowusky profile switch retail`, `wowusky set curseforge-key <key>`,
  `--json`/`--quiet`, shell completion, and a systemd user timer for daily
  update checks.~~ ✅ done
- ~~**v0.9.0** — *Portability & diagnostics*: addon-set export/import (GUI +
  CLI `export` / `import-set`, with per-addon conflict resolution) and the
  `wowusky health` command plus a Health tab.~~ ✅ done
- ~~**v0.9.4** — auto-update on launch + in-app "updates available" indicator
  (wires up the per-profile `auto_update` flag), and CurseForge/GitHub ZIP
  version selection in the addon detail panel.~~ ✅ done
- ~~**v0.9.5** — *Workflow polish*: dependency preview in detail panel, bulk
  update/remove on the Installed tab, systemd scheduled-update timer (CLI +
  Settings screen), and sturdier Import from Downloads with multi-ZIP listing
  and auto catalog matching.~~ ✅ done
- **Later** — see [issues](https://github.com/borunsky/wowusky/issues)
  or open one with a request.

See [CHANGELOG.md](CHANGELOG.md) for what landed in each release and
[CONTRIBUTING.md](CONTRIBUTING.md) if you'd like to send a patch.

---

## Licence

MIT. See [LICENSE](LICENSE).

The catalog manifests are metadata only and do not redistribute any
addon code. wowusky downloads addons directly from each addon's
official source on demand.
