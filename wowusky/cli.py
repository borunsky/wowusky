"""Command-line interface for wowusky.

Dispatched from ``__main__.py`` when ``sys.argv`` contains arguments.
All output is plain text — no colours, no progress bars.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def _addons_path() -> str:
    from wowusky.core.state import get_addons_path
    p = get_addons_path()
    if not p:
        _die(
            "No WoW addons directory configured. "
            "Run the GUI once to set up a profile, or use 'profile switch'."
        )
    return p


def _catalog() -> list[dict]:
    from wowusky.catalog import load_catalog
    return load_catalog()


def _installed() -> dict:
    from wowusky.core.state import load_installed
    return load_installed() or {}


def _fmt_row(cols: list[str], widths: list[int]) -> str:
    return "  ".join(c.ljust(w) for c, w in zip(cols, widths))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_install(args: argparse.Namespace) -> None:
    from wowusky.orchestrator import find_addon_by_id, install_addon
    ap = _addons_path()
    install_deps = not args.no_deps
    dry = getattr(args, "dry_run", False)

    for addon_id in args.addon_id:
        addon = find_addon_by_id(addon_id)
        if addon is None:
            print(f"  ✗ {addon_id}: not found in catalog")
            continue
        if dry:
            print(f"  (dry-run) would install {addon['name']}")
            continue
        try:
            install_addon(addon, ap, log=print, install_deps=install_deps)
            print(f"  ✓ {addon['name']} installed")
        except Exception as exc:
            print(f"  ✗ {addon['name']}: {exc}")


def cmd_uninstall(args: argparse.Namespace) -> None:
    from wowusky.orchestrator import uninstall_addon
    ap = _addons_path()

    for addon_id in args.addon_id:
        try:
            uninstall_addon(addon_id, ap, log=print)
            print(f"  ✓ {addon_id} uninstalled")
        except Exception as exc:
            print(f"  ✗ {addon_id}: {exc}")


def cmd_update(args: argparse.Namespace) -> None:
    from wowusky.orchestrator import find_addon_by_id, get_latest_version, install_addon
    ap = _addons_path()
    installed = _installed()
    dry = getattr(args, "dry_run", False)
    install_deps = not getattr(args, "no_deps", False)

    targets: list[dict] = []
    if args.addon_id:
        for addon_id in args.addon_id:
            addon = find_addon_by_id(addon_id)
            if addon is None:
                print(f"  ✗ {addon_id}: not found in catalog")
            else:
                targets.append(addon)
    else:
        catalog = _catalog()
        cat_by_id = {a["id"]: a for a in catalog}
        for aid in installed:
            if aid in cat_by_id:
                targets.append(cat_by_id[aid])

    updated = 0
    for addon in targets:
        aid = addon["id"]
        entry = installed.get(aid, {})
        current = entry.get("version") or ""
        try:
            latest = get_latest_version(addon)
        except Exception:
            latest = None
        if latest and current and latest == current:
            if args.addon_id:
                print(f"  = {addon['name']} {current} (up to date)")
            continue
        if dry:
            ver_info = f"{current} -> {latest}" if latest else current
            print(f"  (dry-run) would update {addon['name']} {ver_info}")
            continue
        try:
            install_addon(addon, ap, log=print, install_deps=install_deps)
            print(f"  ✓ {addon['name']} updated")
            updated += 1
        except Exception as exc:
            print(f"  ✗ {addon['name']}: {exc}")

    if not args.addon_id:
        print(f"\n{updated} addon(s) updated.")


def cmd_status(args: argparse.Namespace) -> None:
    from wowusky.orchestrator import find_addon_by_id, get_latest_version
    installed = _installed()

    if not installed:
        print("No addons installed.")
        return

    rows: list[tuple[str, str, str, str]] = []
    for aid, entry in sorted(installed.items()):
        name = entry.get("name") or aid
        current = entry.get("version") or "?"
        addon = find_addon_by_id(aid)
        if addon:
            try:
                latest = get_latest_version(addon) or "?"
            except Exception:
                latest = "?"
            flag = "↑" if latest != "?" and latest != current else " "
        else:
            latest = "-"
            flag = " "
        rows.append((flag, aid, name, current, latest))

    w_id = max(len(r[1]) for r in rows)
    w_name = max(len(r[2]) for r in rows)
    w_ver = max(len(r[3]) for r in rows)

    print(_fmt_row(["  ", "id".ljust(w_id), "name".ljust(w_name), "installed".ljust(w_ver), "latest"], [2, w_id, w_name, w_ver, 10]))
    print("  " + "-" * (w_id + w_name + w_ver + 20))
    for flag, aid, name, current, latest in rows:
        print(f"  {flag} {aid.ljust(w_id)}  {name.ljust(w_name)}  {current.ljust(w_ver)}  {latest}")


def cmd_search(args: argparse.Namespace) -> None:
    query = args.query.lower()
    catalog = _catalog()
    results = [
        a for a in catalog
        if query in a["id"].lower()
        or query in a.get("name", "").lower()
        or query in a.get("description", "").lower()
    ]
    if not results:
        print(f"No results for '{args.query}'.")
        return

    w_id = max(len(a["id"]) for a in results)
    w_name = max(len(a.get("name", "")) for a in results)
    print(_fmt_row(["id".ljust(w_id), "name".ljust(w_name), "provider"], [w_id, w_name, 12]))
    print("-" * (w_id + w_name + 20))
    for a in sorted(results, key=lambda x: x["id"]):
        prov = a.get("provider") or a.get("source") or "?"
        print(_fmt_row([a["id"], a.get("name", ""), prov], [w_id, w_name, 12]))


def cmd_orphans(args: argparse.Namespace) -> None:
    from wowusky.orchestrator import find_addon_by_id
    installed = _installed()
    orphans = [aid for aid in installed if find_addon_by_id(aid) is None]
    if not orphans:
        print("No orphaned addons found.")
        return
    print(f"{len(orphans)} orphaned addon(s) (installed but not in catalog):")
    for aid in sorted(orphans):
        name = installed[aid].get("name") or aid
        print(f"  {aid}  {name}")


def cmd_import(args: argparse.Namespace) -> None:
    from wowusky.app import import_zip_file, newest_download_zip
    ap = _addons_path()
    path = args.file
    if path is None:
        path = newest_download_zip()
        if path is None:
            _die("No ZIP file found in ~/Downloads.")
        print(f"Importing {path}")
    try:
        import_zip_file(str(path), ap, log=print)
        print("  ✓ Import complete.")
    except Exception as exc:
        _die(str(exc))


def cmd_profile_list(args: argparse.Namespace) -> None:
    from wowusky.core.state import get_active_profile_id, load_profiles
    data = load_profiles()
    profiles = data.get("profiles", {})
    active = get_active_profile_id()
    if not profiles:
        print("No profiles configured.")
        return
    for pid, prof in profiles.items():
        marker = "*" if pid == active else " "
        name = prof.get("name") or pid
        path = prof.get("addons_path") or ""
        print(f"  {marker} {pid}  {name}  ({path})")


def cmd_profile_switch(args: argparse.Namespace) -> None:
    from wowusky.core.state import load_profiles, set_active_profile
    data = load_profiles()
    profiles = data.get("profiles", {})
    # Match by id or name
    target = None
    for pid, prof in profiles.items():
        if pid == args.name or (prof.get("name") or "").lower() == args.name.lower():
            target = pid
            break
    if target is None:
        _die(f"Profile '{args.name}' not found. Use 'profile list' to see available profiles.")
    set_active_profile(target)
    print(f"Active profile set to '{target}'.")


def cmd_set(args: argparse.Namespace) -> None:
    from wowusky.core.state import set_curseforge_api_key
    if args.setting == "curseforge-key":
        key = args.value
        set_curseforge_api_key(key)
        if key:
            print("CurseForge API key saved.")
        else:
            print("CurseForge API key removed.")
    else:
        _die(f"Unknown setting '{args.setting}'. Available settings: curseforge-key")


def cmd_version(args: argparse.Namespace) -> None:
    from wowusky import __version__
    print(f"wowusky {__version__}")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wowusky",
        description="Minimalist World of Warcraft addon manager.",
    )
    sub = p.add_subparsers(dest="command", metavar="<command>")

    # install
    sp = sub.add_parser("install", help="Install one or more catalog addons by id.")
    sp.add_argument("addon_id", nargs="+", metavar="id")
    sp.add_argument("-n", "--dry-run", action="store_true", help="Show what would be installed.")
    sp.add_argument("--no-deps", action="store_true", help="Skip automatic dependency installation.")
    sp.set_defaults(func=cmd_install)

    # uninstall
    sp = sub.add_parser("uninstall", help="Uninstall one or more addons by id.")
    sp.add_argument("addon_id", nargs="+", metavar="id")
    sp.set_defaults(func=cmd_uninstall)

    # update
    sp = sub.add_parser("update", help="Update installed addons (all if no ids given).")
    sp.add_argument("addon_id", nargs="*", metavar="id")
    sp.add_argument("-n", "--dry-run", action="store_true", help="Show what would be updated.")
    sp.add_argument("--no-deps", action="store_true", help="Skip automatic dependency updates.")
    sp.set_defaults(func=cmd_update)

    # status
    sp = sub.add_parser("status", help="Show installed addons and available updates.")
    sp.set_defaults(func=cmd_status)

    # search
    sp = sub.add_parser("search", help="Search the catalog by name, id or description.")
    sp.add_argument("query", metavar="query")
    sp.set_defaults(func=cmd_search)

    # orphans
    sp = sub.add_parser("orphans", help="List installed addons not present in the catalog.")
    sp.set_defaults(func=cmd_orphans)

    # import
    sp = sub.add_parser("import", help="Import a ZIP file (defaults to newest in ~/Downloads).")
    sp.add_argument("file", nargs="?", default=None, metavar="file.zip")
    sp.set_defaults(func=cmd_import)

    # profile
    sp_prof = sub.add_parser("profile", help="Manage WoW profiles.")
    prof_sub = sp_prof.add_subparsers(dest="profile_cmd", metavar="<subcommand>")

    sp2 = prof_sub.add_parser("list", help="List all configured profiles.")
    sp2.set_defaults(func=cmd_profile_list)

    sp2 = prof_sub.add_parser("switch", help="Switch the active profile.")
    sp2.add_argument("name", metavar="name|id")
    sp2.set_defaults(func=cmd_profile_switch)

    sp_prof.set_defaults(func=lambda a: (
        cmd_profile_list(a) if not a.profile_cmd
        else p.parse_args(["profile", "--help"])
    ))

    # set
    sp = sub.add_parser("set", help="Configure wowusky settings.")
    sp.add_argument("setting", metavar="setting", choices=["curseforge-key"],
                    help="Setting name. Available: curseforge-key")
    sp.add_argument("value", metavar="value", nargs="?", default="",
                    help="New value. Omit or pass empty string to clear.")
    sp.set_defaults(func=cmd_set)

    # version
    sp = sub.add_parser("version", help="Print the wowusky version and exit.")
    sp.set_defaults(func=cmd_version)

    return p


def run_cli(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(0)
    args.func(args)
