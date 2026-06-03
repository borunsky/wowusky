# wowusky

**Minimalist World of Warcraft addon manager for Linux.**

```
◆ wowusky v0.8.0    Browse  Installed  WeakAuras  Import  Log   ● TBC Anniversary ⚙
```

Standard-library Python · CachyOS/Arch-friendly · 241+ curated addons across
Tukui · GitHub · WoWInterface · WeakAuras/Wago · CurseForge.

---

<!-- WHATS-NEW:START -->
<!-- This section is generated from the latest CHANGELOG.md entry by
     .github/workflows/readme-version-sync.yml on each published release.
     Edit CHANGELOG.md, not the text between these markers. -->
## What's new in v0.8.0

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
<!-- WHATS-NEW:END -->

---

## Install

### Local install (CachyOS / Arch / any Linux)

```bash
unzip wowusky-v0.8.0.zip
cd wowusky-v0.8.0
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
pip install dist/wowusky-0.8.0-py3-none-any.whl
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
- **Next** — TBD. See [issues](https://github.com/borunsky/wowusky/issues)
  or open one with a request.

See [CHANGELOG.md](CHANGELOG.md) for what landed in each release and
[CONTRIBUTING.md](CONTRIBUTING.md) if you'd like to send a patch.

---

## Licence

MIT. See [LICENSE](LICENSE).

The catalog manifests are metadata only and do not redistribute any
addon code. wowusky downloads addons directly from each addon's
official source on demand.
