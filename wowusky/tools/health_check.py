"""Provider health check.

Walks the merged catalog and asks each provider to look up the current
version of the addon. Anything that fails is reported.

Designed to run as a scheduled CI job:

    python -m wowusky.tools.health_check
    python -m wowusky.tools.health_check --json > report.json

The ``--offline`` flag skips the network and only exercises the local
resolve path (provider instantiation + ``provider.resolve()``). It is
fast, deterministic, and suitable for the per-push lint-and-test
workflow — it catches catalog entries that point at an unknown
provider or that no provider can produce an ``AddonRef`` for, without
depending on third-party API availability.

Exit code is non-zero when at least one entry failed, so CI can act on it.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from wowusky.catalog import load_catalog
from wowusky.providers import get_provider

# Providers whose catalog entries are populated by an internal flow
# (e.g. the Wago import path generates WeakAurasCompanion locally) and
# therefore have no external API to query. They are reported as
# "internal" instead of being flagged as broken.
_INTERNAL_PROVIDERS = frozenset({"internal_wac"})


def check_addon_offline(addon: dict) -> dict[str, Any]:
    """Local-only health check: provider lookup + resolve.

    Performs no network I/O. Catches three concrete failure modes
    that have all bitten this project at least once:

      * a catalog entry with no ``provider`` / ``source`` field,
      * a catalog entry pointing at a provider name that isn't
        registered (typo or removed provider),
      * a catalog entry whose reference no provider can turn into
        an :class:`AddonRef` (missing repo/slug/id).
    """
    aid = addon.get("id", "<no-id>")
    pname = addon.get("provider") or addon.get("source") or ""
    if not pname:
        return {"id": aid, "provider": "", "error": "no provider field"}

    if pname in _INTERNAL_PROVIDERS:
        return {"id": aid, "provider": pname, "resolved": "internal"}

    try:
        provider = get_provider(pname)
    except KeyError:
        return {"id": aid, "provider": pname, "error": "unknown provider"}

    ref_input = (
        addon.get("repo")
        or addon.get("curseforge_slug")
        or addon.get("wowi_id")
        or addon.get("slug")
        or aid
    )

    try:
        ref = provider.resolve(str(ref_input))
    except Exception as e:                       # noqa: BLE001 — log everything
        return {"id": aid, "provider": pname, "error": f"resolve raised: {e}"}

    if ref is None:
        return {"id": aid, "provider": pname,
                "error": f"resolve returned None for {ref_input!r}"}

    return {"id": aid, "provider": pname, "resolved": ref.ref}


def check_addon(addon: dict) -> dict[str, Any]:
    """Try to resolve and look up the latest version of one addon.

    Returns a dict with at least ``id``, ``provider`` and either
    ``version`` (success) or ``error`` (failure).
    """
    # Re-use the offline path for the local checks, then add the
    # network step on top.
    local = check_addon_offline(addon)
    if "error" in local:
        return local

    aid = local["id"]
    pname = local["provider"]

    # Internal-only providers have no external API to query — the
    # offline resolve already established their presence.
    if pname in _INTERNAL_PROVIDERS:
        return {"id": aid, "provider": pname, "version": "internal"}

    provider = get_provider(pname)

    # We need the AddonRef again — resolve is cheap and deterministic.
    ref_input = (
        addon.get("repo")
        or addon.get("curseforge_slug")
        or addon.get("wowi_id")
        or addon.get("slug")
        or aid
    )
    ref = provider.resolve(str(ref_input))

    # Providers that don't expose a programmatic version (curseforge_web)
    # are considered healthy if resolve succeeded — we can't go further.
    if pname == "curseforge_web":
        return {"id": aid, "provider": pname, "version": "manual"}

    try:
        version = provider.latest_version(ref)
    except Exception as e:                       # noqa: BLE001
        return {"id": aid, "provider": pname, "error": f"version raised: {e}"}

    if version is None:
        return {"id": aid, "provider": pname, "error": "no version returned"}
    return {"id": aid, "provider": pname, "version": str(version)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true",
                        help="machine-readable JSON summary on stdout")
    parser.add_argument("--limit", type=int, default=0,
                        help="only check the first N entries (debugging)")
    parser.add_argument("--offline", action="store_true",
                        help="skip network calls; only exercise provider "
                             "lookup and resolve (suitable for per-push CI)")
    args = parser.parse_args(argv)

    catalog = load_catalog()
    if args.limit:
        catalog = catalog[: args.limit]

    runner = check_addon_offline if args.offline else check_addon
    mode = "offline" if args.offline else "online"

    ok:     list[dict] = []
    failed: list[dict] = []
    for entry in catalog:
        result = runner(entry)
        if "error" in result:
            failed.append(result)
        else:
            ok.append(result)

    if args.json:
        json.dump({"mode": mode,
                   "total": len(catalog), "ok_count": len(ok),
                   "failed_count": len(failed),
                   "ok": ok, "failed": failed},
                  sys.stdout, indent=2)
    else:
        print(f"checked {len(catalog)} addons ({mode})")
        print(f"  ok:     {len(ok)}")
        print(f"  failed: {len(failed)}")
        for f in failed:
            print(f"    {f['id']:30s} [{f['provider']:14s}] {f['error']}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
