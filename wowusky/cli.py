"""Command-line interface for wowusky.

Dispatched from ``__main__.py`` when ``sys.argv`` contains arguments.
All output is plain text — no colours, no progress bars.
"""

from __future__ import annotations

import argparse
import json as _json
import sys

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Set from the global --quiet flag in run_cli. When true, decorative and
# progress output is suppressed; warnings/errors and explicit results stay.
_QUIET = False


def _die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def _say(msg: str = "") -> None:
    """Print informational output unless --quiet is in effect."""
    if not _QUIET:
        print(msg)


def _print_json(data) -> None:
    print(_json.dumps(data, indent=2, ensure_ascii=False))


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
    return "  ".join(c.ljust(w) for c, w in zip(cols, widths, strict=False))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_install(args: argparse.Namespace) -> None:
    from wowusky.orchestrator import find_addon_by_id, install_addon
    ap = _addons_path()
    install_deps = not args.no_deps
    dry = getattr(args, "dry_run", False)

    log = (lambda m: None) if _QUIET else print
    for addon_id in args.addon_id:
        addon = find_addon_by_id(addon_id)
        if addon is None:
            print(f"  ✗ {addon_id}: not found in catalog")
            continue
        if dry:
            _say(f"  (dry-run) would install {addon['name']}")
            continue
        try:
            install_addon(addon, ap, log=log, install_deps=install_deps)
            _say(f"  ✓ {addon['name']} installed")
        except Exception as exc:
            print(f"  ✗ {addon['name']}: {exc}")


def cmd_uninstall(args: argparse.Namespace) -> None:
    from wowusky.orchestrator import uninstall_addon
    ap = _addons_path()

    log = (lambda m: None) if _QUIET else print
    for addon_id in args.addon_id:
        try:
            uninstall_addon(addon_id, ap, log=log)
            _say(f"  ✓ {addon_id} uninstalled")
        except Exception as exc:
            print(f"  ✗ {addon_id}: {exc}")


def cmd_update(args: argparse.Namespace) -> None:
    if getattr(args, "all_profiles", False):
        if args.addon_id:
            _die("--all-profiles cannot be combined with explicit addon ids.")
        _update_all_profiles(args)
        return
    _update_one_profile(args)


def _update_one_profile(args: argparse.Namespace) -> int:
    """Update the active profile. Returns the number of addons updated."""
    from wowusky.orchestrator import find_addon_by_id, get_latest_version, install_addon
    ap = _addons_path()
    installed = _installed()
    dry = getattr(args, "dry_run", False)
    install_deps = not getattr(args, "no_deps", False)
    log = (lambda m: None) if _QUIET else print

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
                _say(f"  = {addon['name']} {current} (up to date)")
            continue
        if dry:
            ver_info = f"{current} -> {latest}" if latest else current
            _say(f"  (dry-run) would update {addon['name']} {ver_info}")
            continue
        try:
            install_addon(addon, ap, log=log, install_deps=install_deps)
            _say(f"  ✓ {addon['name']} updated")
            updated += 1
        except Exception as exc:
            print(f"  ✗ {addon['name']}: {exc}")

    if not args.addon_id:
        _say(f"\n{updated} addon(s) updated.")
    return updated


def _update_all_profiles(args: argparse.Namespace) -> None:
    """Update every configured profile, restoring the active one afterwards."""
    from wowusky.core.state import (
        get_active_profile_id,
        load_profiles,
        set_active_profile,
    )
    data = load_profiles()
    profiles = data.get("profiles", {})
    if not profiles:
        print("No profiles configured.")
        return
    original = get_active_profile_id()
    total = 0
    try:
        for pid, prof in profiles.items():
            name = prof.get("name") or pid
            set_active_profile(pid)
            _say(f"⟩ profile: {name}")
            # Each profile takes its own auto-backup before mutating.
            _maybe_auto_backup(args)
            total += _update_one_profile(args)
    finally:
        set_active_profile(original)
    _say(f"\n{total} addon(s) updated across {len(profiles)} profile(s).")


def cmd_status(args: argparse.Namespace) -> None:
    from wowusky.orchestrator import find_addon_by_id, get_latest_version
    installed = _installed()
    as_json = getattr(args, "json", False)

    if not installed:
        if as_json:
            _print_json([])
        else:
            print("No addons installed.")
        return

    rows: list[tuple[str, str, str, str]] = []
    json_rows: list[dict] = []
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
        json_rows.append({
            "id": aid,
            "name": name,
            "installed": current,
            "latest": latest,
            "update_available": flag == "↑",
            "in_catalog": addon is not None,
        })

    if as_json:
        _print_json(json_rows)
        return

    w_id = max(len(r[1]) for r in rows)
    w_name = max(len(r[2]) for r in rows)
    w_ver = max(len(r[3]) for r in rows)

    print(_fmt_row(["  ", "id".ljust(w_id), "name".ljust(w_name), "installed".ljust(w_ver), "latest"], [2, w_id, w_name, w_ver, 10]))
    print("  " + "-" * (w_id + w_name + w_ver + 20))
    for flag, aid, name, current, latest in rows:
        print(f"  {flag} {aid.ljust(w_id)}  {name.ljust(w_name)}  {current.ljust(w_ver)}  {latest}")


def cmd_search(args: argparse.Namespace) -> None:
    query = args.query.lower()
    as_json = getattr(args, "json", False)
    catalog = _catalog()
    results = [
        a for a in catalog
        if query in a["id"].lower()
        or query in a.get("name", "").lower()
        or query in a.get("description", "").lower()
    ]
    if as_json:
        _print_json([
            {
                "id": a["id"],
                "name": a.get("name", ""),
                "provider": a.get("provider") or a.get("source") or "",
                "category": a.get("category", ""),
                "description": a.get("description", ""),
            }
            for a in sorted(results, key=lambda x: x["id"])
        ])
        return
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
    as_json = getattr(args, "json", False)
    orphans = [aid for aid in installed if find_addon_by_id(aid) is None]
    if as_json:
        _print_json([
            {"id": aid, "name": installed[aid].get("name") or aid}
            for aid in sorted(orphans)
        ])
        return
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


def _fmt_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}GB"


def _fmt_time(mtime: float) -> str:
    import time
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))


# ---------------------------------------------------------------------------
# Backup (full profile)
# ---------------------------------------------------------------------------

def cmd_backup(args: argparse.Namespace) -> None:
    sub = getattr(args, "backup_cmd", None) or "list"
    if sub == "create":
        _backup_create(args)
    elif sub == "auto":
        _backup_auto(args)
    elif sub == "restore":
        _backup_restore(args)
    else:
        _backup_list(args)


def _backup_auto(args: argparse.Namespace) -> None:
    from wowusky.core.backup import auto_full_backup
    _addons_path()  # validate a profile is configured
    keep = getattr(args, "keep", None) or 5
    try:
        path = auto_full_backup(keep=keep, log=print)
        print(f"  ✓ {path}")
    except Exception as exc:
        _die(str(exc))


def _backup_create(args: argparse.Namespace) -> None:
    from wowusky.core.backup import create_full_backup
    _addons_path()  # validate a profile is configured
    try:
        path = create_full_backup(log=print)
        print(f"  ✓ {path}")
    except Exception as exc:
        _die(str(exc))


def _backup_list(args: argparse.Namespace) -> None:
    from wowusky.core.backup import list_full_backups
    backups = list_full_backups()
    if getattr(args, "json", False):
        _print_json([
            {"index": i, "name": b["name"], "path": b["path"],
             "mtime": b["mtime"], "size": b["size"]}
            for i, b in enumerate(backups)
        ])
        return
    if not backups:
        print("No full backups for the active profile.")
        return
    print(f"{len(backups)} full backup(s) (newest first):\n")
    for i, b in enumerate(backups):
        print(f"  [{i}] {b['name']}  {_fmt_time(b['mtime'])}  {_fmt_size(b['size'])}")


def _resolve_full_backup(selector: str) -> str | None:
    """Resolve a backup selector (index, name, or path) to a ZIP path."""
    import os

    from wowusky.core.backup import list_full_backups
    if os.path.isfile(selector):
        return selector
    backups = list_full_backups()
    if selector.isdigit():
        idx = int(selector)
        if 0 <= idx < len(backups):
            return backups[idx]["path"]
        return None
    for b in backups:
        if b["name"] == selector:
            return b["path"]
    return None


def _backup_restore(args: argparse.Namespace) -> None:
    from wowusky.core.backup import restore_full_backup
    _addons_path()
    path = _resolve_full_backup(args.backup)
    if path is None:
        _die(f"Backup '{args.backup}' not found. Use 'backup list' to see available backups.")
    try:
        restore_full_backup(path, log=print)
    except Exception as exc:
        _die(str(exc))


# ---------------------------------------------------------------------------
# Rollback (per-addon backup)
# ---------------------------------------------------------------------------

def cmd_rollback(args: argparse.Namespace) -> None:
    from wowusky.core.backup import (
        list_addon_backups,
        rollback_addon,
        rollback_addon_to_backup,
    )
    addon_id = args.addon_id

    if args.list:
        backups = list_addon_backups(addon_id)
        if not backups:
            print(f"No backups for '{addon_id}'.")
            return
        print(f"{len(backups)} backup(s) for {addon_id} (newest first):\n")
        for i, b in enumerate(backups):
            print(f"  [{i}] {b['name']}  v{b['version']}  {_fmt_time(b['mtime'])}  {_fmt_size(b['size'])}")
        return

    ap = _addons_path()
    if args.backup:
        path = _resolve_addon_backup(addon_id, args.backup)
        if path is None:
            _die(f"Backup '{args.backup}' not found for '{addon_id}'. "
                 f"Use 'rollback {addon_id} --list' to see available backups.")
        ok = rollback_addon_to_backup(addon_id, path, ap, log=print)
    else:
        ok = rollback_addon(addon_id, ap, log=print)
    if not ok:
        sys.exit(1)


def _resolve_addon_backup(addon_id: str, selector: str) -> str | None:
    import os

    from wowusky.core.backup import list_addon_backups
    if os.path.isfile(selector):
        return selector
    backups = list_addon_backups(addon_id)
    if selector.isdigit():
        idx = int(selector)
        if 0 <= idx < len(backups):
            return backups[idx]["path"]
        return None
    for b in backups:
        if b["name"] == selector:
            return b["path"]
    return None


# ---------------------------------------------------------------------------
# WeakAuras (Wago.io tracking)
# ---------------------------------------------------------------------------

def cmd_weakauras(args: argparse.Namespace) -> None:
    sub = getattr(args, "wa_cmd", None) or "list"
    dispatch = {
        "list": _wa_list,
        "add": _wa_add,
        "remove": _wa_remove,
        "update": _wa_update,
        "import": _wa_import,
        "search": _wa_search,
        "companion": _wa_companion,
    }
    dispatch[sub](args)


def _wa_list(args: argparse.Namespace) -> None:
    from wowusky.core.state import load_wago
    auras = (load_wago() or {}).get("auras", {})
    if getattr(args, "json", False):
        _print_json([
            {
                "slug": slug,
                "name": e.get("name") or slug,
                "version": e.get("version"),
                "latest_version": e.get("latest_version"),
                "update_available": (e.get("latest_version") is not None
                                     and str(e.get("latest_version")) != str(e.get("version"))),
            }
            for slug, e in sorted(auras.items())
        ])
        return
    if not auras:
        print("No tracked WeakAuras. Add one with 'weakauras add <slug>'.")
        return
    rows = []
    for slug, e in sorted(auras.items()):
        ver = str(e.get("version", "?"))
        latest = e.get("latest_version")
        flag = "↑" if latest is not None and str(latest) != ver else " "
        rows.append((flag, slug, e.get("name") or slug, ver, str(latest) if latest is not None else "-"))
    w_slug = max(len(r[1]) for r in rows)
    w_name = max(len(r[2]) for r in rows)
    for flag, slug, name, ver, latest in rows:
        print(f"  {flag} {slug.ljust(w_slug)}  {name.ljust(w_name)}  v{ver} -> v{latest}")


def _wa_add(args: argparse.Namespace) -> None:
    from wowusky.core.wago import wago_add
    entry = wago_add(args.slug, name=args.name, note=args.note)
    print(f"  ✓ tracking {entry.get('name') or args.slug} (v{entry.get('version')})")


def _wa_remove(args: argparse.Namespace) -> None:
    from wowusky.core.wago import wago_remove
    if wago_remove(args.slug):
        print(f"  ✓ stopped tracking {args.slug}")
    else:
        print(f"  ✗ {args.slug}: not tracked")


def _wa_update(args: argparse.Namespace) -> None:
    from wowusky.core.wago import wago_check_updates
    updates = wago_check_updates()
    if not updates:
        print("All tracked WeakAuras are up to date.")
        return
    print(f"{len(updates)} aura(s) have updates available:")
    for slug in updates:
        print(f"  ↑ {slug}")
    print("\nUpdates are applied in WoW via WeakAurasCompanion; "
          "run 'weakauras companion' to regenerate it.")


def _wa_import(args: argparse.Namespace) -> None:
    from wowusky.core.wago import import_existing_weakauras_from_savedvariables
    result = import_existing_weakauras_from_savedvariables(log=print)
    print(f"  ✓ imported {result.get('added', 0)} new, "
          f"{result.get('existing', 0)} already tracked, "
          f"{result.get('failed', 0)} failed")


def _wa_search(args: argparse.Namespace) -> None:
    results = None
    from wowusky.core.wago import wago_search
    data = wago_search(args.query, limit=20)
    if isinstance(data, dict):
        results = data.get("data") or data.get("results")
    elif isinstance(data, list):
        results = data
    if not results:
        print(f"No results for '{args.query}'.")
        return
    for r in results:
        slug = r.get("slug") or r.get("_id") or "?"
        name = r.get("name") or ""
        print(f"  {slug}  {name}")


def _wa_companion(args: argparse.Namespace) -> None:
    from wowusky.orchestrator import generate_wac_companion
    ap = _addons_path()
    try:
        generate_wac_companion(ap)
        print("  ✓ WeakAurasCompanion regenerated.")
    except Exception as exc:
        _die(str(exc))


def cmd_health(args: argparse.Namespace) -> None:
    from wowusky.catalog import load_catalog
    from wowusky.tools.health_check import check_addon, check_addon_offline

    catalog = load_catalog()
    offline = getattr(args, "offline", False)
    as_json = getattr(args, "json", False)
    limit = getattr(args, "limit", None)
    if limit:
        catalog = catalog[:limit]

    check_fn = check_addon_offline if offline else check_addon
    results = []
    ok = 0
    for entry in catalog:
        if not as_json and not _QUIET:
            print(f"  checking {entry.get('id', '?'):<40}", end="\r", flush=True)
        r = check_fn(entry)
        if "error" not in r:
            ok += 1
        results.append(r)

    if not as_json and not _QUIET:
        print(" " * 60, end="\r")

    failed = len(results) - ok
    if as_json:
        _print_json({"total": len(results), "ok": ok, "failed": failed, "results": results})
        return

    mode = "offline" if offline else "online"
    print(f"\n{ok}/{len(results)} catalog entries healthy ({mode})" +
          (f", {failed} failed." if failed else "."))
    for r in results:
        if "error" in r:
            print(f"  ✗ {r['id']}: {r['error']}")
    if failed:
        sys.exit(1)


def _fmt_schedule_status(st: dict) -> str:
    if not st.get("available"):
        return "  systemd user instance not available — scheduled updates unsupported here."
    if not st.get("installed"):
        return "  scheduled updates: not installed (run `wowusky schedule enable`)."
    state = "enabled" if st.get("enabled") else "disabled"
    active = "active" if st.get("active") else "inactive"
    lines = [f"  scheduled updates: {state}, {active} · interval {st.get('interval', '?')}"]
    if st.get("next_run"):
        lines.append(f"    next run: {st['next_run']}")
    return "\n".join(lines)


def cmd_schedule(args: argparse.Namespace) -> None:
    from wowusky.core import schedule as _schedule

    action = getattr(args, "schedule_action", None) or "status"
    as_json = getattr(args, "json", False)

    if action == "enable":
        res = _schedule.enable(getattr(args, "interval", None) or "daily")
        if not res.get("ok"):
            _die(res.get("error", "failed to enable scheduled updates"))
        if as_json:
            _print_json(res)
        else:
            _say("  ✓ Scheduled updates enabled.")
            _say(_fmt_schedule_status(res))
        return

    if action == "disable":
        res = _schedule.disable()
        if not res.get("ok"):
            _die(res.get("error", "failed to disable scheduled updates"))
        if as_json:
            _print_json(res)
        else:
            _say("  ✓ Scheduled updates disabled.")
        return

    # status (default)
    st = _schedule.status()
    if as_json:
        _print_json(st)
    else:
        _say(_fmt_schedule_status(st))


def cmd_sync(args: argparse.Namespace) -> None:
    from wowusky.core import profile_bundle as _pb
    from wowusky.core import sync as _sync

    action = getattr(args, "sync_cmd", None) or "status"
    as_json = getattr(args, "json", False)

    if action == "set-repo":
        _sync.set_repo_path(args.path)
        st = _sync.status()
        _print_json(st) if as_json else _say(f"  ✓ Sync repo set to {st.get('repo_path')}")
        return

    if action == "push":
        res = _sync.push(log=_say)
        if not res.get("ok"):
            _die(res.get("error", "sync push failed"))
        _print_json(res) if as_json else _say(
            "  ✓ Pushed." if res.get("pushed") else f"  ✓ {res.get('message', 'nothing to push')}")
        return

    if action == "pull":
        res = _sync.pull(log=_say)
        if not res.get("ok"):
            _die(res.get("error", "sync pull failed"))
        applied = _pb.import_bundle_apply(res["bundle"])
        if as_json:
            _print_json({**res, "applied": applied})
        else:
            _say(f"  ✓ Pulled and applied: {applied['imported']} addons, "
                 f"{applied['auras_added']} auras, {applied['settings_applied']} settings.")
        return

    # status (default)
    st = _sync.status()
    if as_json:
        _print_json(st)
    elif not st.get("available"):
        _say("  git is not installed — sync unavailable.")
    elif not st.get("configured"):
        _say("  No sync repo configured. Use 'wowusky sync set-repo <path>'.")
    else:
        _say(f"  Sync repo: {st['repo_path']}")
        _say(f"  git repo:  {'yes' if st.get('is_repo') else 'no'}")
        _say(f"  bundle:    {'present' if st.get('has_bundle') else 'none'}")


def cmd_export(args: argparse.Namespace) -> None:
    import json as _json

    from wowusky.core.addonset import export_addon_set
    from wowusky.core.state import load_profiles

    profile_arg = getattr(args, "profile", None)
    profile_id = None
    if profile_arg:
        profiles = load_profiles().get("profiles", {})
        for pid, prof in profiles.items():
            if pid == profile_arg or (prof.get("name") or "").lower() == profile_arg.lower():
                profile_id = pid
                break
        if profile_id is None:
            _die(f"Profile '{profile_arg}' not found.")

    snap = export_addon_set(profile_id)
    output = _json.dumps(snap, indent=2, ensure_ascii=False)
    with open(args.file, "w") as fh:
        fh.write(output)

    count = snap.get("count", 0)
    name = snap["profile"].get("name", "profile")
    _say(f"  ✓ Exported {count} addon(s) from '{name}' to {args.file}")


def cmd_import_set(args: argparse.Namespace) -> None:
    import json as _json

    from wowusky.core.addonset import import_addon_set_apply, import_addon_set_preview
    from wowusky.core.state import load_profiles

    try:
        with open(args.file) as fh:
            data = _json.load(fh)
    except (FileNotFoundError, _json.JSONDecodeError) as exc:
        _die(str(exc))

    profile_arg = getattr(args, "profile", None)
    profile_id = None
    if profile_arg:
        profiles = load_profiles().get("profiles", {})
        for pid, prof in profiles.items():
            if pid == profile_arg or (prof.get("name") or "").lower() == profile_arg.lower():
                profile_id = pid
                break
        if profile_id is None:
            _die(f"Profile '{profile_arg}' not found.")

    as_json = getattr(args, "json", False)

    try:
        preview = import_addon_set_preview(data, profile_id)
    except ValueError as exc:
        _die(str(exc))

    new_count = sum(1 for p in preview if p["status"] == "new")
    conflict_count = sum(1 for p in preview if p["status"] == "conflict")
    same_count = sum(1 for p in preview if p["status"] == "same")

    if as_json:
        _print_json({
            "preview": preview,
            "new": new_count,
            "conflicts": conflict_count,
            "same": same_count,
        })
        return

    if not _QUIET:
        src = (data.get("profile") or {}).get("name", "?")
        print(f"\nImporting addon set from '{src}': "
              f"{new_count} new, {conflict_count} conflict(s), {same_count} already installed\n")
        if conflict_count:
            print("Conflicts (your version → import version):")
            for p in preview:
                if p["status"] == "conflict":
                    print(f"  {p['id']:<30}  {p['installed_version']!s:<12} → {p['version']}")
            print()

    yes = getattr(args, "yes", False)
    if not yes and not _QUIET:
        try:
            ans = input("Apply import? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            ans = ""
        if ans not in ("y", "yes"):
            print("Aborted.")
            return

    skip = [p["id"] for p in preview if p["status"] == "conflict"] if getattr(args, "skip_conflicts", False) else []
    result = import_addon_set_apply(data, profile_id, skip)
    _say(f"  ✓ Imported {result['imported']} addon(s), skipped {result['skipped']}.")


def cmd_version(args: argparse.Namespace) -> None:
    from wowusky import __version__
    print(f"wowusky {__version__}")


# ---------------------------------------------------------------------------
# Shell completion
# ---------------------------------------------------------------------------

_BASH_COMPLETION = r"""# wowusky bash completion — generated by `wowusky completion bash`.
# Install:  wowusky completion bash > ~/.local/share/bash-completion/completions/wowusky
_wowusky_completion() {
    local cur prev
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    local commands="install uninstall update status search orphans import \
backup rollback weakauras wa profile set health export import-set schedule version help completion"
    if [ "$COMP_CWORD" -eq 1 ]; then
        COMPREPLY=( $(compgen -W "$commands" -- "$cur") )
        return
    fi
    case "${COMP_WORDS[1]}" in
        backup)        COMPREPLY=( $(compgen -W "create list restore" -- "$cur") );;
        profile)       COMPREPLY=( $(compgen -W "list switch" -- "$cur") );;
        weakauras|wa)  COMPREPLY=( $(compgen -W "list add remove update import search companion" -- "$cur") );;
        schedule)      COMPREPLY=( $(compgen -W "status enable disable" -- "$cur") );;
        set)           COMPREPLY=( $(compgen -W "curseforge-key" -- "$cur") );;
        completion)    COMPREPLY=( $(compgen -W "bash zsh" -- "$cur") );;
        help)          COMPREPLY=( $(compgen -W "$commands" -- "$cur") );;
    esac
}
complete -F _wowusky_completion wowusky
"""

_ZSH_COMPLETION = r"""#compdef wowusky
# wowusky zsh completion — generated by `wowusky completion zsh`.
# Install:  wowusky completion zsh > "${fpath[1]}/_wowusky"  (then restart zsh)
_wowusky() {
    local -a commands
    commands=(install uninstall update status search orphans import \
backup rollback weakauras wa profile set health export import-set schedule version help completion)
    if (( CURRENT == 2 )); then
        _describe 'command' commands
        return
    fi
    case $words[2] in
        backup)       _values 'subcommand' create list restore;;
        profile)      _values 'subcommand' list switch;;
        weakauras|wa) _values 'subcommand' list add remove update import search companion;;
        schedule)     _values 'subcommand' status enable disable;;
        set)          _values 'setting' curseforge-key;;
        completion)   _values 'shell' bash zsh;;
    esac
}
_wowusky "$@"
"""


def cmd_completion(args: argparse.Namespace) -> None:
    if args.shell == "bash":
        print(_BASH_COMPLETION)
    elif args.shell == "zsh":
        print(_ZSH_COMPLETION)
    else:
        _die(f"Unsupported shell '{args.shell}'. Supported: bash, zsh")


def cmd_help(args: argparse.Namespace) -> None:
    from wowusky import __version__
    topic = getattr(args, "topic", None)

    COMMANDS = {
        "install": {
            "syntax":   "wowusky install <id> [<id>...] [-n] [--no-deps]",
            "desc":     "Install one or more addons from the catalog by their id.",
            "flags": [
                ("-n, --dry-run", "Show what would be installed without making changes."),
                ("--no-deps",     "Skip automatic installation of catalog dependencies."),
            ],
            "examples": [
                ("wowusky install elvui",                       "Install ElvUI."),
                ("wowusky install bigwigs littlewigs",          "Install two addons at once."),
                ("wowusky install details_cf --no-deps",        "Install without pulling in deps."),
                ("wowusky install weakauras -n",                "Preview what would happen."),
            ],
        },
        "uninstall": {
            "syntax":   "wowusky uninstall <id> [<id>...]",
            "desc":     "Remove one or more installed addons and their folders.",
            "flags":    [],
            "examples": [
                ("wowusky uninstall elvui",           "Remove ElvUI."),
                ("wowusky uninstall bigwigs littlewigs", "Remove two addons at once."),
            ],
        },
        "update": {
            "syntax":   "wowusky update [<id>...] [-n] [--no-deps] [--all-profiles]",
            "desc":     "Update installed addons. Without ids, updates every installed catalog addon.",
            "flags": [
                ("-n, --dry-run",   "Show what would be updated without making changes."),
                ("--no-deps",       "Skip dependency updates."),
                ("--all-profiles",  "Update every configured profile, not just the active one."),
            ],
            "examples": [
                ("wowusky update",                "Update all installed addons."),
                ("wowusky update elvui",          "Update only ElvUI."),
                ("wowusky update -n",             "Preview available updates."),
                ("wowusky update --all-profiles", "Update every profile in turn."),
                ("wowusky update -q",             "Update quietly (for cron jobs)."),
            ],
        },
        "status": {
            "syntax":   "wowusky status",
            "desc":     "Show all installed addons with their installed version and latest available version.\n"
                        "  An ↑ marker means an update is available.",
            "flags":    [],
            "examples": [
                ("wowusky status", "List all installed addons and their update state."),
            ],
        },
        "search": {
            "syntax":   "wowusky search <query>",
            "desc":     "Search the catalog by addon id, name, or description.",
            "flags":    [],
            "examples": [
                ("wowusky search raid",    "Find all raid-related addons."),
                ("wowusky search elvui",   "Look up ElvUI by name."),
                ("wowusky search bigwigs", "Search by id."),
            ],
        },
        "orphans": {
            "syntax":   "wowusky orphans",
            "desc":     "List addons that are installed but no longer appear in the catalog.\n"
                        "  These can be removed with 'uninstall' or kept as-is.",
            "flags":    [],
            "examples": [
                ("wowusky orphans", "Show orphaned addons."),
            ],
        },
        "import": {
            "syntax":   "wowusky import [<file.zip>]",
            "desc":     "Import an addon from a ZIP file.\n"
                        "  Without a path, picks the newest ZIP from ~/Downloads automatically.",
            "flags":    [],
            "examples": [
                ("wowusky import",                          "Import newest ZIP from ~/Downloads."),
                ("wowusky import ~/Downloads/MyAddon.zip",  "Import a specific file."),
            ],
        },
        "profile": {
            "syntax":   "wowusky profile list\n"
                        "  wowusky profile switch <name|id>",
            "desc":     "Manage WoW installation profiles.\n"
                        "  Each profile has its own installed list, backup history, and settings.\n"
                        "  The active profile is marked with * in the list.",
            "flags":    [],
            "examples": [
                ("wowusky profile list",           "Show all profiles (* = active)."),
                ("wowusky profile switch retail",  "Switch to the 'retail' profile."),
                ("wowusky profile switch tbc",     "Switch to the TBC profile."),
            ],
        },
        "set": {
            "syntax":   "wowusky set curseforge-key <key>\n"
                        "  wowusky set curseforge-key",
            "desc":     "Configure wowusky settings.\n\n"
                        "  curseforge-key   Store your CurseForge Eternal API key.\n"
                        "                   Enables direct addon lookups and updates for\n"
                        "                   numeric CurseForge ids. Omit the value to clear.",
            "flags":    [],
            "examples": [
                ("wowusky set curseforge-key abc123def456",  "Save a CurseForge API key."),
                ("wowusky set curseforge-key",               "Remove the stored key."),
            ],
        },
        "backup": {
            "syntax":   "wowusky backup create\n"
                        "  wowusky backup list\n"
                        "  wowusky backup restore <index|name|path>",
            "desc":     "Manage full profile backups (Interface/AddOns + WTF settings).\n"
                        "  'restore' overwrites the current AddOns and WTF with the backup's contents.",
            "flags":    [],
            "examples": [
                ("wowusky backup create",      "Create a full profile backup now."),
                ("wowusky backup list",        "List backups with their index."),
                ("wowusky backup restore 0",   "Restore the newest backup (index 0)."),
                ("wowusky backup restore wowusky-full-retail-20260603-120000.zip", "Restore by name."),
            ],
        },
        "rollback": {
            "syntax":   "wowusky rollback <addon-id> [<index|name>]\n"
                        "  wowusky rollback <addon-id> --list",
            "desc":     "Restore a single addon from its automatic per-addon backups.\n"
                        "  Without a selector, restores the most recent backup for that addon.",
            "flags": [
                ("--list",          "List available backups for the addon instead of restoring."),
                ("--backup <sel>",  "Restore a specific backup by index, name, or path."),
            ],
            "examples": [
                ("wowusky rollback elvui",            "Restore ElvUI's newest backup."),
                ("wowusky rollback elvui --list",     "List ElvUI's backups."),
                ("wowusky rollback elvui --backup 2", "Restore ElvUI backup at index 2."),
            ],
        },
        "weakauras": {
            "syntax":   "wowusky weakauras list|update|import|companion\n"
                        "  wowusky weakauras add <slug> [--name N] [--note T]\n"
                        "  wowusky weakauras remove <slug>\n"
                        "  wowusky weakauras search <query>",
            "desc":     "Track Wago.io WeakAuras and generate the WeakAurasCompanion addon.\n"
                        "  list       Show tracked auras (↑ = update available).\n"
                        "  add        Start tracking an aura by its Wago slug.\n"
                        "  remove     Stop tracking an aura.\n"
                        "  update     Check Wago.io for newer versions.\n"
                        "  import     Import auras already present in your WeakAuras SavedVariables.\n"
                        "  search     Search Wago.io for auras.\n"
                        "  companion  Regenerate the WeakAurasCompanion addon in your AddOns folder.",
            "flags":    [],
            "examples": [
                ("wowusky weakauras list",            "List tracked auras."),
                ("wowusky weakauras add abcDEF123",   "Track an aura by slug."),
                ("wowusky weakauras update",          "Check for aura updates."),
                ("wowusky weakauras import",          "Import from SavedVariables."),
                ("wowusky weakauras companion",       "Regenerate WeakAurasCompanion."),
            ],
        },
        "health": {
            "syntax":   "wowusky health [--offline] [--json]",
            "desc":     "Check every catalog entry against its provider.\n"
                        "  --offline skips network calls and only verifies that each entry\n"
                        "  resolves to a known provider reference. Default mode also pings\n"
                        "  the provider API to fetch the latest version.",
            "flags": [
                ("--offline", "Provider-resolve only; no network calls."),
                ("--json",    "Machine-readable JSON output."),
                ("--limit N", "Check only the first N entries (for debugging)."),
            ],
            "examples": [
                ("wowusky health --offline", "Fast offline check of all catalog entries."),
                ("wowusky health",           "Full online check (fetches latest versions)."),
                ("wowusky health --json",    "JSON output for scripting."),
            ],
        },
        "export": {
            "syntax":   "wowusky export <file.json> [--profile name|id]",
            "desc":     "Export the installed addon list for the active (or given) profile\n"
                        "  to a portable JSON file that can be imported on another machine.",
            "flags": [
                ("--profile name|id", "Profile to export (default: active profile)."),
            ],
            "examples": [
                ("wowusky export my-addons.json",                    "Export the active profile."),
                ("wowusky export retail.json --profile retail",      "Export a specific profile."),
            ],
        },
        "import-set": {
            "syntax":   "wowusky import-set <file.json> [--profile name|id] [-y] [--skip-conflicts]",
            "desc":     "Import an addon set from a JSON export file into a profile.\n"
                        "  Writes DB entries only — use 'update' afterwards to download the\n"
                        "  actual addon files. Conflicts (same addon, different version) are\n"
                        "  shown interactively unless --yes is given.",
            "flags": [
                ("--profile name|id",  "Target profile (default: active profile)."),
                ("-y, --yes",          "Apply without a confirmation prompt."),
                ("--skip-conflicts",   "Skip addons whose version conflicts with what is installed."),
            ],
            "examples": [
                ("wowusky import-set my-addons.json",                       "Interactive import."),
                ("wowusky import-set my-addons.json -y",                    "Import without prompting."),
                ("wowusky import-set retail.json --profile retail -y",      "Import into a specific profile."),
                ("wowusky import-set my-addons.json --skip-conflicts",      "Import new addons, skip conflicts."),
            ],
        },
        "schedule": {
            "syntax":   "wowusky schedule status\n"
                        "  wowusky schedule enable [--interval hourly|daily|weekly]\n"
                        "  wowusky schedule disable",
            "desc":     "Manage a systemd *user* timer that runs 'wowusky update -q' on a\n"
                        "  schedule, so addons stay current without a running GUI. Requires a\n"
                        "  systemd user instance (degrades gracefully where unavailable).",
            "flags": [
                ("--interval hourly|daily|weekly", "How often to check (enable only; default: daily)."),
            ],
            "examples": [
                ("wowusky schedule status",            "Show the timer's current state."),
                ("wowusky schedule enable",            "Enable daily scheduled updates."),
                ("wowusky schedule enable --interval weekly", "Check weekly instead."),
                ("wowusky schedule disable",           "Remove the scheduled-update timer."),
            ],
        },
        "completion": {
            "syntax":   "wowusky completion bash\n"
                        "  wowusky completion zsh",
            "desc":     "Print a shell completion script to stdout.\n"
                        "  bash:  wowusky completion bash > ~/.local/share/bash-completion/completions/wowusky\n"
                        "  zsh:   wowusky completion zsh  > \"${fpath[1]}/_wowusky\"  (then restart zsh)",
            "flags":    [],
            "examples": [
                ("wowusky completion bash", "Print the bash completion script."),
                ("wowusky completion zsh",  "Print the zsh completion script."),
            ],
        },
        "version": {
            "syntax":   "wowusky version",
            "desc":     "Print the installed wowusky version and exit.",
            "flags":    [],
            "examples": [
                ("wowusky version", f"Prints: wowusky {__version__}"),
            ],
        },
    }

    if topic and topic in COMMANDS:
        c = COMMANDS[topic]
        print(f"\nUsage:  {c['syntax']}\n")
        print(f"  {c['desc']}\n")
        if c["flags"]:
            print("Options:")
            w = max(len(f) for f, _ in c["flags"])
            for flag, desc in c["flags"]:
                print(f"  {flag.ljust(w)}  {desc}")
            print()
        print("Examples:")
        w = max(len(ex) for ex, _ in c["examples"])
        for ex, note in c["examples"]:
            print(f"  {ex.ljust(w)}  # {note}")
        print()
        return

    if topic:
        print(f"Unknown command '{topic}'. Available commands are listed below.\n")

    print(f"wowusky {__version__} — minimalist WoW addon manager for Linux\n")
    print("Usage:  wowusky <command> [arguments]\n")
    print("Commands:\n")

    rows = [
        ("install   <id>...",            "Install catalog addon(s) by id"),
        ("uninstall <id>...",            "Remove installed addon(s)"),
        ("update    [<id>...]",          "Update addons (all if no ids given)"),
        ("status",                       "List installed addons and available updates"),
        ("search    <query>",            "Search the catalog by name, id or description"),
        ("orphans",                      "List installed addons absent from the catalog"),
        ("import    [file.zip]",         "Import a ZIP (defaults to newest in ~/Downloads)"),
        ("backup    create|list|restore", "Manage full profile backups (AddOns + WTF)"),
        ("rollback  <id> [sel]",         "Restore a single addon from its backups"),
        ("weakauras list|add|update|…",  "Track Wago.io WeakAuras + companion"),
        ("profile   list|switch <name>", "Manage WoW installation profiles"),
        ("set       curseforge-key [v]", "Configure wowusky settings"),
        ("health    [--offline]",        "Check catalog entries against their providers"),
        ("export    <file.json>",        "Export the active profile's addon list"),
        ("import-set <file.json>",       "Import an addon list from a JSON export"),
        ("schedule  status|enable|disable", "Manage the systemd scheduled-update timer"),
        ("completion bash|zsh",          "Print a shell completion script"),
        ("version",                      "Print version and exit"),
        ("help      [<command>]",        "Show this help, or detailed help for one command"),
    ]
    w = max(len(r[0]) for r in rows)
    for cmd_col, desc in rows:
        print(f"  {cmd_col.ljust(w)}  {desc}")

    print()
    print("Flags available on install / update:")
    print("  -n, --dry-run   Show what would happen without making changes.")
    print("  --no-deps       Skip automatic catalog dependency installation.")
    print("  --all-profiles  (update only) Update every configured profile.")
    print()
    print("Global flags:")
    print("  --no-backup     Skip the automatic full backup taken before the command runs.")
    print("  -q, --quiet     Suppress progress/info output; keep warnings, errors, results.")
    print("  --json          Machine-readable JSON output (status, search, orphans, list).")
    print()
    print("Auto-backup: a full profile backup runs automatically before every command")
    print("that touches your WoW install. Use --no-backup to skip it for one run.")
    print()
    print("Examples:")
    examples = [
        ("wowusky install elvui bigwigs",    "Install two addons"),
        ("wowusky update -n",                "Preview available updates"),
        ("wowusky search raid",              "Search catalog for raid addons"),
        ("wowusky profile switch retail",    "Switch active WoW profile"),
        ("wowusky set curseforge-key KEY",   "Store CurseForge API key"),
        ("wowusky help install",             "Detailed help for 'install'"),
    ]
    we = max(len(e) for e, _ in examples)
    for ex, note in examples:
        print(f"  {ex.ljust(we)}  # {note}")
    print()


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wowusky",
        description="Minimalist World of Warcraft addon manager.",
        add_help=True,
    )
    # Global flags, shared with every subcommand via `parents=` so they may
    # appear either before or after the subcommand name.
    g = argparse.ArgumentParser(add_help=False)
    g.add_argument("--no-backup", action="store_true",
                   help="Skip the automatic full backup taken before the command runs.")
    g.add_argument("-q", "--quiet", action="store_true",
                   help="Suppress progress/info output; keep warnings, errors and results.")
    g.add_argument("--json", action="store_true",
                   help="Machine-readable JSON output (status, search, orphans, backup/wa list).")
    p.add_argument("--no-backup", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("-q", "--quiet", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    sub = p.add_subparsers(dest="command", metavar="<command>")

    # install
    sp = sub.add_parser("install", parents=[g], help="Install one or more catalog addons by id.")
    sp.add_argument("addon_id", nargs="+", metavar="id")
    sp.add_argument("-n", "--dry-run", action="store_true", help="Show what would be installed.")
    sp.add_argument("--no-deps", action="store_true", help="Skip automatic dependency installation.")
    sp.set_defaults(func=cmd_install)

    # uninstall
    sp = sub.add_parser("uninstall", parents=[g], help="Uninstall one or more addons by id.")
    sp.add_argument("addon_id", nargs="+", metavar="id")
    sp.set_defaults(func=cmd_uninstall)

    # update
    sp = sub.add_parser("update", parents=[g], help="Update installed addons (all if no ids given).")
    sp.add_argument("addon_id", nargs="*", metavar="id")
    sp.add_argument("-n", "--dry-run", action="store_true", help="Show what would be updated.")
    sp.add_argument("--no-deps", action="store_true", help="Skip automatic dependency updates.")
    sp.add_argument("--all-profiles", action="store_true",
                    help="Update every configured profile, not just the active one.")
    sp.set_defaults(func=cmd_update)

    # status
    sp = sub.add_parser("status", parents=[g], help="Show installed addons and available updates.")
    sp.set_defaults(func=cmd_status)

    # search
    sp = sub.add_parser("search", parents=[g], help="Search the catalog by name, id or description.")
    sp.add_argument("query", metavar="query")
    sp.set_defaults(func=cmd_search)

    # orphans
    sp = sub.add_parser("orphans", parents=[g], help="List installed addons not present in the catalog.")
    sp.set_defaults(func=cmd_orphans)

    # import
    sp = sub.add_parser("import", parents=[g], help="Import a ZIP file (defaults to newest in ~/Downloads).")
    sp.add_argument("file", nargs="?", default=None, metavar="file.zip")
    sp.set_defaults(func=cmd_import)

    # backup
    sp_bk = sub.add_parser("backup", parents=[g], help="Manage full profile backups.")
    bk_sub = sp_bk.add_subparsers(dest="backup_cmd", metavar="<subcommand>")
    bk_sub.add_parser("create", parents=[g], help="Create a full profile backup now.").set_defaults(func=cmd_backup)
    sp_bk_auto = bk_sub.add_parser("auto", parents=[g],
                                   help="Create a full backup and prune to the newest --keep.")
    sp_bk_auto.add_argument("--keep", type=int, default=5, help="How many full backups to retain.")
    sp_bk_auto.set_defaults(func=cmd_backup)
    bk_sub.add_parser("list", parents=[g], help="List full profile backups.").set_defaults(func=cmd_backup)
    sp_bk2 = bk_sub.add_parser("restore", parents=[g], help="Restore a full profile backup.")
    sp_bk2.add_argument("backup", metavar="index|name|path")
    sp_bk2.set_defaults(func=cmd_backup)
    sp_bk.set_defaults(func=cmd_backup)

    # rollback
    sp = sub.add_parser("rollback", parents=[g], help="Restore a single addon from its backups.")
    sp.add_argument("addon_id", metavar="addon-id")
    sp.add_argument("backup", nargs="?", default=None, metavar="index|name",
                    help="Backup selector. Defaults to the newest backup.")
    sp.add_argument("--list", action="store_true", help="List the addon's backups instead of restoring.")
    sp.add_argument("--backup", dest="backup", metavar="sel",
                    help="Restore a specific backup by index, name, or path.")
    sp.set_defaults(func=cmd_rollback)

    # weakauras
    sp_wa = sub.add_parser("weakauras", parents=[g], aliases=["wa"],
                           help="Track Wago.io WeakAuras + companion.")
    wa_sub = sp_wa.add_subparsers(dest="wa_cmd", metavar="<subcommand>")
    wa_sub.add_parser("list", parents=[g], help="List tracked auras.").set_defaults(func=cmd_weakauras)
    sp_wa2 = wa_sub.add_parser("add", parents=[g], help="Track an aura by its Wago slug.")
    sp_wa2.add_argument("slug", metavar="slug")
    sp_wa2.add_argument("--name", default=None, help="Override the display name.")
    sp_wa2.add_argument("--note", default=None, help="Attach a note.")
    sp_wa2.set_defaults(func=cmd_weakauras)
    sp_wa3 = wa_sub.add_parser("remove", parents=[g], help="Stop tracking an aura.")
    sp_wa3.add_argument("slug", metavar="slug")
    sp_wa3.set_defaults(func=cmd_weakauras)
    wa_sub.add_parser("update", parents=[g], help="Check Wago.io for newer versions.").set_defaults(func=cmd_weakauras)
    wa_sub.add_parser("import", parents=[g], help="Import auras from SavedVariables.").set_defaults(func=cmd_weakauras)
    wa_sub.add_parser("companion", parents=[g], help="Regenerate WeakAurasCompanion.").set_defaults(func=cmd_weakauras)
    sp_wa4 = wa_sub.add_parser("search", parents=[g], help="Search Wago.io for auras.")
    sp_wa4.add_argument("query", metavar="query")
    sp_wa4.set_defaults(func=cmd_weakauras)
    sp_wa.set_defaults(func=cmd_weakauras)

    # profile
    sp_prof = sub.add_parser("profile", parents=[g], help="Manage WoW profiles.")
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
    sp = sub.add_parser("set", parents=[g], help="Configure wowusky settings.")
    sp.add_argument("setting", metavar="setting", choices=["curseforge-key"],
                    help="Setting name. Available: curseforge-key")
    sp.add_argument("value", metavar="value", nargs="?", default="",
                    help="New value. Omit or pass empty string to clear.")
    sp.set_defaults(func=cmd_set)

    # health
    sp = sub.add_parser("health", parents=[g], help="Check every catalog entry for provider issues.")
    sp.add_argument("--offline", action="store_true", help="Skip network calls (provider-resolve only).")
    sp.add_argument("--limit", type=int, default=None, metavar="N", help="Check only the first N entries (debug).")
    sp.set_defaults(func=cmd_health)

    # export
    sp = sub.add_parser("export", parents=[g], help="Export the active profile's addon list to a JSON file.")
    sp.add_argument("file", metavar="file.json")
    sp.add_argument("--profile", default=None, metavar="name|id", help="Profile to export (default: active).")
    sp.set_defaults(func=cmd_export)

    # import-set
    sp = sub.add_parser("import-set", parents=[g], help="Import an addon set from a JSON export file.")
    sp.add_argument("file", metavar="file.json")
    sp.add_argument("--profile", default=None, metavar="name|id", help="Target profile (default: active).")
    sp.add_argument("-y", "--yes", action="store_true", help="Apply without confirmation prompt.")
    sp.add_argument("--skip-conflicts", action="store_true",
                    help="Skip addons whose version conflicts with what is already installed.")
    sp.set_defaults(func=cmd_import_set)

    # schedule
    sp_sched = sub.add_parser("schedule", parents=[g],
                              help="Manage the systemd user timer for scheduled updates.")
    sched_sub = sp_sched.add_subparsers(dest="schedule_action")
    sched_sub.add_parser("status", parents=[g],
                         help="Show scheduled-update timer status.").set_defaults(func=cmd_schedule)
    sp_se = sched_sub.add_parser("enable", parents=[g], help="Install + enable the update timer.")
    sp_se.add_argument("--interval", choices=["hourly", "daily", "weekly"], default="daily",
                       help="How often to check for updates (default: daily).")
    sp_se.set_defaults(func=cmd_schedule)
    sched_sub.add_parser("disable", parents=[g],
                         help="Disable + remove the update timer.").set_defaults(func=cmd_schedule)
    sp_sched.set_defaults(func=cmd_schedule)

    # sync (#66)
    sp_sync = sub.add_parser("sync", parents=[g],
                             help="Sync the active profile via a git repository.")
    sync_sub = sp_sync.add_subparsers(dest="sync_cmd")
    sync_sub.add_parser("status", parents=[g],
                        help="Show sync repo status.").set_defaults(func=cmd_sync)
    sp_sy = sync_sub.add_parser("set-repo", parents=[g], help="Set the local sync repo path.")
    sp_sy.add_argument("path", metavar="path")
    sp_sy.set_defaults(func=cmd_sync)
    sync_sub.add_parser("push", parents=[g],
                        help="Export the profile bundle and push it.").set_defaults(func=cmd_sync)
    sync_sub.add_parser("pull", parents=[g],
                        help="Pull and apply the latest profile bundle.").set_defaults(func=cmd_sync)
    sp_sync.set_defaults(func=cmd_sync)

    # version
    sp = sub.add_parser("version", help="Print the wowusky version and exit.")
    sp.set_defaults(func=cmd_version)

    # help
    sp = sub.add_parser("help", help="Show help, or detailed help for one command.")
    sp.add_argument("topic", nargs="?", default=None, metavar="command")
    sp.set_defaults(func=cmd_help)

    # completion
    sp = sub.add_parser("completion", help="Print a shell completion script (bash or zsh).")
    sp.add_argument("shell", choices=["bash", "zsh"], metavar="shell",
                    help="Shell to generate completion for: bash or zsh.")
    sp.set_defaults(func=cmd_completion)

    return p


# Commands that never touch the WoW install (no profile needed, no data at
# risk), so the automatic backup is pointless and is skipped for them.
_NO_BACKUP_COMMANDS = {"version", "help", "search", "set", "completion", "health", "export", "schedule", None}


def _maybe_auto_backup(args: argparse.Namespace) -> None:
    """Run a full profile backup before the command, unless skipped.

    Skipped when --no-backup is given, for informational/offline commands,
    or when no profile/addons path is configured yet.
    """
    if getattr(args, "no_backup", False):
        return
    command = getattr(args, "command", None)
    if command in _NO_BACKUP_COMMANDS:
        return
    # Listing-only operations don't risk data, but we still honour the
    # "backup before every run" choice for anything that can mutate the
    # install. 'status'/'orphans'/'*list' are read-only — skip those too.
    if command in ("status", "orphans"):
        return
    if getattr(args, "backup_cmd", None) == "list" or getattr(args, "wa_cmd", None) in ("list", "search"):
        return
    if getattr(args, "profile_cmd", None) == "list":
        return
    if getattr(args, "list", False):  # rollback --list
        return
    from wowusky.core.state import get_addons_path
    if not get_addons_path():
        return
    from wowusky.core.backup import create_full_backup
    quiet_log = _QUIET or getattr(args, "json", False)
    try:
        if quiet_log:
            create_full_backup(log=lambda m: None)
        else:
            create_full_backup(
                log=lambda m: print(f"  {m.strip()}" if m.strip().startswith("✓") else m)
            )
    except Exception as exc:
        if not quiet_log:
            print(f"  ⚠ auto-backup skipped: {exc}")


def run_cli(argv: list[str] | None = None) -> None:
    global _QUIET
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        cmd_help(args)
        sys.exit(0)
    # --json implies quiet so the JSON payload is the only thing on stdout.
    _QUIET = bool(getattr(args, "quiet", False) or getattr(args, "json", False))
    # Normalise the 'wa' alias so help/lookup see the canonical name.
    if getattr(args, "command", None) == "wa":
        args.command = "weakauras"
    _maybe_auto_backup(args)
    args.func(args)
