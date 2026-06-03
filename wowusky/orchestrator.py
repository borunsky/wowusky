"""wowusky install / provider orchestration facade.

This module owns the addon install/update orchestration and the thin
facades around the :mod:`wowusky.core` and :mod:`wowusky.providers`
helpers that the GUI (in :mod:`wowusky.gui.main`) and the terminal UI
call into. It was carved out of ``wowusky.app`` (Etappe H) so that
``app.py`` shrinks to a small entry-point + re-export surface.

Everything here depends only on :mod:`wowusky.core`,
:mod:`wowusky.providers` and :mod:`wowusky.catalog` — never on
``wowusky.app`` — so importing this module carries no risk of an import
cycle. ``app.py`` re-imports the public names from here, which keeps the
``from wowusky.app import *`` surface the GUI body relies on intact.
"""

from __future__ import annotations

import contextlib
import logging
import os
import time
import webbrowser
from logging.handlers import RotatingFileHandler

from wowusky import APP_NAME, __version__
from wowusky.catalog import load_catalog as _load_manifest_catalog
from wowusky.core import http as _ws_http
from wowusky.core import resolver as _resolver
from wowusky.core.backup import backup_addon_folders
from wowusky.core.depends import resolve_dependencies
from wowusky.core.flavors import WOW_FLAVORS, is_compatible
from wowusky.core.installer import (
    build_import_entry,
)
from wowusky.core.installer import (
    install_addon as _core_install_addon,
)
from wowusky.core.installer import (
    uninstall_addon as _core_uninstall_addon,
)
from wowusky.core.paths import LOG_DIR as _LOG_DIR_PATH
from wowusky.core.state import (
    ensure_config_dir,
    get_active_profile,
    get_active_profile_id,
    get_addons_path,
    get_curseforge_api_key,
    is_dry_run,
    load_installed,
    load_wago,
    save_installed,
)
from wowusky.core.wago import generate_wac_companion as _core_generate_wac
from wowusky.core.zipper import extract_addon_zip
from wowusky.providers import curseforge_fns as _cf_fns
from wowusky.providers import github_fns as _github_fns
from wowusky.providers.curseforge_fns import (
    curseforge_manual_latest,
    curseforge_url_from_installed,
    curseforge_version_from_installed,
)
from wowusky.providers.curseforge_fns import (
    install_curseforge as _cf_install_curseforge,
)
from wowusky.providers.curseforge_fns import (
    install_curseforge_dependencies as _cf_install_deps,
)
from wowusky.providers.github_fns import github_url, github_version
from wowusky.providers.tukui_fns import tukui_url, tukui_version
from wowusky.providers.wowi_fns import wowi_url, wowi_version

LOG_DIR      = str(_LOG_DIR_PATH)
http_download = _ws_http.download


# ── catalog ──────────────────────────────────────────────────────────

def _load_addon_catalog_with_compat(_loader=None) -> list[dict]:
    """Load the manifest catalog and adapt it to the legacy shape used by
    the GUI code.

    The old inline catalog used ``source`` and provider-specific fields
    (``api_url``, ``download_url``, ``repo``, ``wowi_id``). The new
    manifest schema uses ``provider`` and the same field names. We
    forward both spellings so neither side has to change in lockstep.

    ``_loader`` is an optional callable that returns the raw manifest list;
    defaults to :func:`wowusky.catalog.load_catalog`. Tests may inject a
    fake loader to test the compat logic in isolation.
    """
    loader = _loader if _loader is not None else _load_manifest_catalog
    out: list[dict] = []
    for a in loader():
        entry = dict(a)
        # provider ↔ source duality
        if "source" not in entry:
            entry["source"] = entry.get("provider", "")
        # Reconstruct tukui api_url/download_url if missing
        if entry["source"] == "tukui" and "api_url" not in entry:
            slug = entry.get("slug") or entry["id"]
            entry.setdefault("api_url",
                             f"https://api.tukui.org/v1/addon/{slug}")
            entry.setdefault("download_url",
                             f"https://api.tukui.org/v1/download/dev/{slug}/main")
        out.append(entry)
    return out


ADDON_CATALOG = _load_addon_catalog_with_compat()


# ── logging ──────────────────────────────────────────────────────────

def _setup_file_logging():
    ensure_config_dir()
    logger = logging.getLogger(APP_NAME)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    path = os.path.join(LOG_DIR, time.strftime("wowusky-%Y-%m-%d.log"))
    handler = RotatingFileHandler(path, maxBytes=512 * 1024, backupCount=7, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


LOGGER = None


def app_log(message, level="info"):
    global LOGGER
    if LOGGER is None:
        LOGGER = _setup_file_logging()
    getattr(LOGGER, level, LOGGER.info)(str(message))


# ── flavor ───────────────────────────────────────────────────────────

def get_current_flavor():
    """Returns flavor key (anniversary, vanilla, etc.) of active profile."""
    prof = get_active_profile()
    if prof.get("flavor") and prof.get("flavor") != "custom":
        return prof.get("flavor")
    p = get_addons_path()
    if not p:
        return None
    for flv_dir, (_name, key, _) in WOW_FLAVORS.items():
        if flv_dir in p:
            return key
    return None


# Wire the active-flavor / API-key lookups into the provider modules that
# need them. These were monkeypatched from app.py before the facade moved
# here; setting them on the shared module objects keeps the resolve path
# flavor-aware regardless of which UI imported the module first.
_cf_fns.get_current_flavor = lambda: get_current_flavor()
_cf_fns.get_curseforge_api_key = lambda: get_curseforge_api_key()
_github_fns.get_current_flavor = lambda: get_current_flavor()


# ── internal WeakAurasCompanion "provider" ───────────────────────────

def internal_wac_version(a):
    """WeakAurasCompanion is generated locally — version = number of auras."""
    wago = load_wago()
    return f"{len(wago.get('auras', {}))} auras"


def internal_wac_url(a):
    return None  # never downloaded


# ── CurseForge web URLs (flavor-aware resolver facades) ──────────────

def curseforge_search_url(query=""):
    return _resolver.curseforge_search_url(query, get_current_flavor())


def curseforge_files_url(slug_or_url=""):
    return _resolver.curseforge_files_url(slug_or_url, get_current_flavor())


def curseforge_manual_url(entry):
    """Thin wrapper — delegates to the flavor-aware resolver helper."""
    return _resolver.curseforge_manual_url(entry, get_current_flavor())


# ── browser / Downloads helpers ──────────────────────────────────────

def open_in_browser(url):
    if not url:
        return False
    try:
        webbrowser.open(url)
        return True
    except Exception:
        return False


def downloads_dir():
    cfg = os.environ.get("XDG_DOWNLOAD_DIR")
    if cfg:
        return os.path.expanduser(cfg)
    return os.path.expanduser("~/Downloads")


def scan_download_zips(limit=25):
    d = downloads_dir()
    if not os.path.isdir(d):
        return []
    files = []
    for name in os.listdir(d):
        if name.lower().endswith(".zip"):
            path = os.path.join(d, name)
            with contextlib.suppress(OSError):
                files.append((os.path.getmtime(path), path))
    files.sort(reverse=True)
    return [p for _, p in files[:limit]]


def newest_download_zip():
    zips = scan_download_zips(limit=1)
    return zips[0] if zips else ""


def import_zip_file(zip_path, addons_path, name=None, source="manual", log=print, curseforge_slug=None, curseforge_url=None):
    """Import a manual / CurseForge ZIP and record it in the active profile.

    Extraction and entry-building live in ``wowusky.core.installer``; this
    wrapper only adds the profile-aware ``installed.json`` write.
    """
    addon_id, entry = build_import_entry(
        zip_path, addons_path, name=name, source=source,
        curseforge_slug=curseforge_slug, curseforge_url=curseforge_url, log=log,
    )
    inst = load_installed()
    inst[addon_id] = entry
    save_installed(inst)
    return addon_id


# ── CurseForge install (profile I/O wired in) ────────────────────────

def install_curseforge(ref_or_mod, addons_path, log=print, progress=None, install_deps=True):
    """Thin wrapper — wires profile I/O into the core CurseForge install."""
    return _cf_install_curseforge(
        ref_or_mod, addons_path,
        http_download=http_download,
        load_installed=load_installed,
        save_installed=save_installed,
        log=log, progress=progress, install_deps=install_deps,
    )


def install_curseforge_dependencies(file_data, addons_path, log=print, seen=None):
    """Thin wrapper — wires profile I/O into the dependency installer."""
    return _cf_install_deps(
        file_data, addons_path,
        http_download=http_download,
        load_installed=load_installed,
        save_installed=save_installed,
        log=log, seen=seen,
    )


# ── provider dispatch (version / download URL) ───────────────────────

SOURCES = {
    "tukui":        (tukui_version, tukui_url),
    "github":       (github_version, github_url),
    "wowi":         (wowi_version, wowi_url),
    "internal_wac": (internal_wac_version, internal_wac_url),
    "curseforge":   (lambda a: curseforge_version_from_installed(a), lambda a: curseforge_url_from_installed(a)),
    "curseforge_web": (lambda a: "manual", lambda a: ""),
    "curseforge_manual": (lambda a: curseforge_manual_latest(a), lambda a: curseforge_manual_url(a)),
}


def get_latest_version(a):
    try:
        return SOURCES[a["source"]][0](a)
    except Exception:
        return None


def get_download_url(a):
    return SOURCES[a["source"]][1](a)


# ── WeakAurasCompanion generation ────────────────────────────────────

def generate_wac_companion(addons_path):
    """Thin wrapper — resolves the active flavor's TOC interface, then
    delegates to :func:`wowusky.core.wago.generate_wac_companion`."""
    interface = 120001  # default retail
    flavor = get_current_flavor()
    for _flv_dir, (_n, k, iface) in WOW_FLAVORS.items():
        if k == flavor:
            interface = iface
            break
    return _core_generate_wac(addons_path, interface=interface, app_version=__version__)


# ── provider status / manual fallbacks ───────────────────────────────

def addon_provider_page(addon):
    return _resolver.addon_provider_page(addon, get_current_flavor())


def provider_action_label(addon, installed=False):
    return _resolver.provider_action_label(addon, installed)


# ── install / uninstall (profile/config state wired in) ──────────────

def install_addon(addon, addons_path, log=print, progress=None, install_deps=True):
    """Install *addon*, pulling in any missing catalog dependencies first.

    Catalog entries may declare ``"depends": ["id", ...]``; those entries
    are resolved against the loaded catalog and installed (in dependency
    order) before the target. Already-installed dependencies are skipped,
    cycles are handled, and dependency ids not present in the catalog are
    logged and skipped. Pass ``install_deps=False`` to install only the
    target (used internally so resolved dependencies don't re-resolve).
    """
    if install_deps:
        deps, missing = resolve_dependencies(
            addon,
            find_addon=find_addon_by_id,
            is_installed=lambda aid: aid in load_installed(),
        )
        for dep_id in missing:
            log(f"  ⚠ dependency not in catalog, skipping: {dep_id}")
            app_log(f"dependency missing from catalog: {dep_id} (needed by {addon.get('id')})")
        for dep in deps:
            log(f"⟩ dependency of {addon['name']}: {dep['name']}")
            _install_single(dep, addons_path, log=log, progress=progress)
    return _install_single(addon, addons_path, log=log, progress=progress)


def _install_single(addon, addons_path, log=print, progress=None):
    """Thin wrapper — wires profile/config state into the core install logic."""
    def _generate_wac(ap):
        ok = generate_wac_companion(ap)
        if ok:
            log(f"  ✓ generated with {len(load_wago().get('auras', {}))} auras\n")
        return ok
    return _core_install_addon(
        addon, addons_path,
        profile_id=get_active_profile_id(),
        get_latest_version=get_latest_version,
        get_download_url=get_download_url,
        load_installed=load_installed,
        save_installed=save_installed,
        backup_addon_folders=backup_addon_folders,
        http_download=http_download,
        is_dry_run=is_dry_run,
        app_log=app_log,
        addon_provider_page=addon_provider_page,
        open_in_browser=open_in_browser,
        generate_wac_companion=_generate_wac,
        log=log,
        progress=progress,
    )


def extract_zip(zip_path, addons_path, addon=None, log=None):
    """Thin wrapper around :func:`wowusky.core.zipper.extract_addon_zip`.

    The ``addon`` / ``log`` parameters are retained for the existing GUI
    call sites; extraction logic now lives in ``wowusky.core.zipper`` as
    the single source of truth (shared with ``health_check`` and tests).
    """
    return extract_addon_zip(zip_path, addons_path)


def uninstall_addon(addon_id, addons_path, log=print):
    """Thin wrapper — wires profile/config state into the core uninstall logic."""
    return _core_uninstall_addon(
        addon_id, addons_path,
        load_installed=load_installed,
        save_installed=save_installed,
        backup_addon_folders=backup_addon_folders,
        is_dry_run=is_dry_run,
        app_log=app_log,
        profile_id=get_active_profile_id(),
        log=log,
    )


# ── catalog queries ──────────────────────────────────────────────────

def find_addon_by_id(aid):
    return next((a for a in ADDON_CATALOG if a["id"] == aid), None)


def get_categories():
    return sorted({a["category"] for a in ADDON_CATALOG})


def filter_catalog_by_flavor(addons, current_flavor):
    """Filter catalog to only show addons compatible with current flavor.

    Uses the shared :func:`wowusky.core.flavors.is_compatible` helper so
    the rules match what the GUI displays elsewhere.
    """
    if not current_flavor:
        return addons
    return [a for a in addons
            if is_compatible(a.get("flavors", ["all"]), current_flavor)]
