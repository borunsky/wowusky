"""CurseForge provider — function-based implementation.

The PURE PROVIDER functions for CurseForge, extracted verbatim from
app.py during the v0.5 provider extraction (Etappe A). Behaviour is
pinned by tests/test_characterize_providers.py — 15 tests covering
slug parsing, the web-fallback functions, header building, and the
flavor-matching logic.

NOT moved here (deliberately): the install layer (install_curseforge,
install_curseforge_dependencies, import_zip_file), the API-call layer
(curseforge_json, curseforge_mod_from_ref, curseforge_get_files,
curseforge_pick_file), and all *_url / *_search / *_manual helpers.
Per the migration dossier, those belong to later stages.
"""

from __future__ import annotations

import re

from wowusky import APP_NAME, __version__

CURSEFORGE_URL_RX = re.compile(
    r'curseforge\.com/wow/addons/([a-zA-Z0-9_-]+)')

CF_FLAVOR_TEXT = {
    "retail":      ("retail", "mainline", "the war within", "dragonflight", "war within"),
    "ptr":         ("ptr", "retail", "mainline"),
    "anniversary": ("anniversary", "tbc", "burning crusade", "classic", "bcc"),
    "vanilla":     ("classic era", "classic", "vanilla", "sod", "season of discovery"),
    "mop_classic": ("mists", "mop", "mists of pandaria", "classic"),
}

CF_VERSION_TYPE_HINTS = {
    "retail": 517,
    "ptr": 517,
    "anniversary": 67408,
    "vanilla": 67408,
    "mop_classic": 73246,
}


def get_curseforge_api_key():
    """Imported back from app.py at runtime — see app.py injection.

    Falls back to the env-var / empty string outside the GUI.
    """
    import os
    return os.environ.get("CURSEFORGE_API_KEY", "")


def get_current_flavor():
    """Imported back from app.py at runtime — see app.py injection.

    Falls back to "retail" when called outside the GUI (e.g. health_check).
    """
    return "retail"


def cf_slug_from_ref(ref):
    ref = (ref or "").strip()
    if not ref:
        return ""
    m = CURSEFORGE_URL_RX.search(ref)
    if m:
        return m.group(1)
    if ref.isdigit():
        return ""
    return ref.strip("/").split("/")[-1]


def curseforge_headers():
    key = get_curseforge_api_key()
    if not key:
        raise RuntimeError(
            "CurseForge API key missing. Add it in Settings or set CURSEFORGE_API_KEY.")
    return {
        "Accept": "application/json",
        "x-api-key": key,
        "User-Agent": f"{APP_NAME}/{__version__}",
    }


def curseforge_web_version(a):
    return "manual"


def curseforge_web_url(a):
    return "https://www.curseforge.com/wow/addons/" + a.get("curseforge_slug", a.get("id", ""))


def _cf_file_versions(file_data):
    versions = []
    versions.extend(str(v).lower() for v in file_data.get("gameVersions", []) if v)
    for v in file_data.get("sortableGameVersions", []) or []:
        for key in ("gameVersion", "gameVersionName", "gameVersionPadded"):
            if v.get(key):
                versions.append(str(v[key]).lower())
        if v.get("gameVersionTypeId"):
            versions.append(f"type:{v['gameVersionTypeId']}")
    return versions


def curseforge_file_matches_flavor(file_data):
    flavor = get_current_flavor() or "retail"
    versions = _cf_file_versions(file_data)
    text_hints = CF_FLAVOR_TEXT.get(flavor, ())
    type_hint = CF_VERSION_TYPE_HINTS.get(flavor)
    if type_hint and f"type:{type_hint}" in versions:
        return True
    if not versions:
        return True
    joined = " ".join(versions)
    return any(h in joined for h in text_hints)


# ---------------------------------------------------------------------------
# API call layer
# ---------------------------------------------------------------------------

CURSEFORGE_API_BASE = "https://api.curseforge.com/v1"
CURSEFORGE_GAME_ID = 1  # World of Warcraft


def curseforge_json(path, params=None, cache=True):
    """Hit the CurseForge Core API and return the parsed JSON dict.

    Uses :func:`wowusky.core.http.get_json` with the auth headers from
    :func:`curseforge_headers`. Raises descriptive ``RuntimeError`` for
    common 401/403 failures so the GUI can surface them without a
    traceback.
    """
    import urllib.error
    import urllib.parse

    from wowusky.core.http import get_json, retry

    url = CURSEFORGE_API_BASE + path
    if params:
        clean = {k: v for k, v in params.items() if v not in (None, "")}
        if clean:
            url += "?" + urllib.parse.urlencode(clean)

    def load():
        try:
            # get_json has its own cache; pass cache=False so we control it via
            # the retry wrapper without double-caching.
            return retry(lambda: get_json(url, headers=curseforge_headers(), cache=False))
        except urllib.error.HTTPError as e:
            if e.code == 403:
                raise RuntimeError(
                    "CurseForge API returned 403 Forbidden. "
                    "Der API-Key ist nicht fuer die Core/Third-Party API freigeschaltet "
                    "oder wurde gesperrt. ZIP-Import oder 'Open on CurseForge' verwenden."
                ) from e
            if e.code == 401:
                raise RuntimeError(
                    "CurseForge API key rejected (401). Bitte Key in Settings pruefen."
                ) from e
            raise

    # Use core.http's module-level cache (same dict the rest of the app uses).
    from wowusky.core.http import CACHE_TTL, _cache  # noqa: PLC2701
    if cache:
        import time
        item = _cache.get(url)
        if item and time.time() - item[0] < CACHE_TTL:
            return item[1]
        data = load()
        _cache[url] = (time.time(), data)
        return data
    return load()


def curseforge_api_diagnose():
    """Return (ok, message) for the configured CurseForge Core API key."""
    try:
        data = curseforge_json("/games", cache=False)
        games = data.get("data", []) if isinstance(data, dict) else []
        return True, f"API key OK. {len(games)} games returned."
    except Exception as e:
        return False, str(e)


def curseforge_search(query="", page_size=40):
    query = (query or "").strip()
    params = {
        "gameId": CURSEFORGE_GAME_ID,
        "pageSize": page_size,
        "sortField": 2,
        "sortOrder": "desc",
    }
    if query:
        params["searchFilter"] = query
    return curseforge_json("/mods/search", params).get("data", [])


def curseforge_mod_from_ref(ref):
    """Accept a CurseForge project id, full URL, or addon slug/search text."""
    ref = (ref or "").strip()
    if not ref:
        raise RuntimeError("CurseForge project URL, slug, or numeric project id missing.")
    if ref.isdigit():
        return curseforge_json(f"/mods/{ref}").get("data")
    m = CURSEFORGE_URL_RX.search(ref)
    slug = m.group(1) if m else ref.strip("/").split("/")[-1]
    data = curseforge_json("/mods/search", {
        "gameId": CURSEFORGE_GAME_ID,
        "slug": slug,
        "pageSize": 1,
    }).get("data", [])
    if not data:
        data = curseforge_search(slug.replace("-", " "), page_size=1)
    if not data:
        raise RuntimeError(f"CurseForge addon not found: {ref}")
    return data[0]


def curseforge_get_files(mod_id):
    flavor = get_current_flavor() or "retail"
    version_type = CF_VERSION_TYPE_HINTS.get(flavor)
    params: dict = {"pageSize": 50}
    if version_type:
        params["gameVersionTypeId"] = version_type
    files = curseforge_json(f"/mods/{mod_id}/files", params).get("data", [])
    if not files:
        files = curseforge_json(f"/mods/{mod_id}/files", {"pageSize": 50}).get("data", [])
    return [f for f in files if f.get("isAvailable", True) and not f.get("isServerPack")]


def curseforge_pick_file(mod):
    files = curseforge_get_files(mod["id"])
    if not files:
        raise RuntimeError("No downloadable CurseForge file found for this addon.")
    matching = [f for f in files if curseforge_file_matches_flavor(f)]
    candidates = matching or files

    def file_key(f):
        return (f.get("releaseType") == 1, f.get("fileDate", ""), int(f.get("id") or 0))

    return sorted(candidates, key=file_key, reverse=True)[0]


def curseforge_download_url(mod_id, file):
    url = file.get("downloadUrl")
    if url:
        return url
    data = curseforge_json(f"/mods/{mod_id}/files/{file['id']}/download-url", cache=False)
    return data.get("data")


def curseforge_mod_summary(mod):
    logo = mod.get("logo") or {}
    return {
        "id":        mod.get("id"),
        "name":      mod.get("name") or "Unknown",
        "summary":   mod.get("summary") or "",
        "downloads": mod.get("downloadCount") or 0,
        "thumbnail": logo.get("thumbnailUrl") or logo.get("url") or "",
        "url":       (mod.get("links") or {}).get("websiteUrl") or "",
        "slug":      mod.get("slug") or "",
    }


def curseforge_version_from_installed(entry):
    mod_id = entry.get("curseforge_mod_id") or entry.get("project_id")
    if not mod_id:
        return None
    try:
        mod = curseforge_json(f"/mods/{mod_id}").get("data")
        file = curseforge_pick_file(mod)
        return file.get("displayName") or file.get("fileName") or str(file.get("id"))
    except Exception:
        return None


def curseforge_url_from_installed(entry):
    mod_id = entry.get("curseforge_mod_id") or entry.get("project_id")
    if not mod_id:
        return None
    mod = curseforge_json(f"/mods/{mod_id}").get("data")
    file = curseforge_pick_file(mod)
    return curseforge_download_url(mod_id, file)


def curseforge_manual_url(entry, files_url_fn=None, search_url_fn=None):
    """Best-effort download/files URL for a manually imported CurseForge addon.

    ``files_url_fn`` and ``search_url_fn`` are optional callables (injected by
    app.py) that build flavor-aware web URLs. Falls back to plain addon page.
    """
    import urllib.parse

    slug = entry.get("curseforge_slug") or cf_slug_from_ref(entry.get("url", ""))
    if slug:
        if files_url_fn:
            return files_url_fn(slug)
        return f"https://www.curseforge.com/wow/addons/{urllib.parse.quote(slug)}/files/all"
    if search_url_fn:
        return search_url_fn(entry.get("name", ""))
    return entry.get("url") or (
        "https://www.curseforge.com/wow/search?search="
        + urllib.parse.quote(entry.get("name", ""))
    )


def curseforge_manual_latest(entry):
    """Best-effort latest version for manually imported CurseForge addons."""
    mod_id = entry.get("curseforge_mod_id") or entry.get("project_id")
    slug = entry.get("curseforge_slug")
    if not get_curseforge_api_key():
        return None
    try:
        mod = curseforge_json(f"/mods/{mod_id}").get("data") if mod_id else curseforge_mod_from_ref(slug)
        file = curseforge_pick_file(mod)
        return file.get("displayName") or file.get("fileName") or str(file.get("id"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Install layer
# ---------------------------------------------------------------------------

def install_curseforge_dependencies(
    file_data, addons_path, *, http_download, load_installed, save_installed,
    log=print, seen=None,
):
    if seen is None:
        seen = set()
    deps = file_data.get("dependencies", []) or []
    required = [d for d in deps if d.get("relationType") == 3 and d.get("modId")]
    for dep in required:
        mod_id = dep["modId"]
        if mod_id in seen:
            continue
        seen.add(mod_id)
        try:
            dep_mod = curseforge_json(f"/mods/{mod_id}").get("data")
            if dep_mod:
                log(f"  dependency: {dep_mod.get('name', mod_id)}")
                install_curseforge(
                    dep_mod, addons_path,
                    http_download=http_download,
                    load_installed=load_installed,
                    save_installed=save_installed,
                    log=log,
                    install_deps=False,
                )
        except Exception as e:
            log(f"  dependency skipped: {mod_id} ({e})")


def install_curseforge(
    ref_or_mod, addons_path, *,
    http_download, load_installed, save_installed,
    log=print, progress=None, install_deps=True,
):
    """Download and install a CurseForge addon.

    ``http_download``, ``load_installed``, and ``save_installed`` are
    injected so this function can be unit-tested without a live profile.
    """
    import contextlib
    import os
    import tempfile

    from wowusky.core.zipper import extract_addon_zip

    mod = ref_or_mod if isinstance(ref_or_mod, dict) else curseforge_mod_from_ref(ref_or_mod)
    file = curseforge_pick_file(mod)
    url = curseforge_download_url(mod["id"], file)
    if not url:
        raise RuntimeError("CurseForge did not return a download URL for this file.")

    name = mod.get("name") or str(mod.get("id"))
    version = file.get("displayName") or file.get("fileName") or str(file.get("id"))
    log(f"⟩ CurseForge: {name}")
    log(f"  file: {version}")

    if install_deps:
        install_curseforge_dependencies(
            file, addons_path,
            http_download=http_download,
            load_installed=load_installed,
            save_installed=save_installed,
            log=log,
        )

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        http_download(url, tmp_path, progress=progress)
        log(f"  done ({os.path.getsize(tmp_path) // 1024} KB)")
        addon_id = f"curse_{mod['id']}"
        folders = extract_addon_zip(tmp_path, addons_path)
        inst = load_installed()
        inst[addon_id] = {
            "name":               name,
            "version":            version,
            "folders":            folders,
            "source":             "curseforge",
            "curseforge_mod_id":  mod["id"],
            "curseforge_file_id": file.get("id"),
            "url":                (mod.get("links") or {}).get("websiteUrl"),
        }
        save_installed(inst)
        log(f"  ✓ {name}\n")
        return True
    finally:
        with contextlib.suppress(Exception):
            os.unlink(tmp_path)

