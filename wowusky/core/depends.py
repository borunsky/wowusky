"""Catalog-level dependency resolution.

A catalog addon may declare other catalog entries it needs via a
``"depends": ["id1", "id2"]`` field in its manifest. When the user installs
such an addon, wowusky should install the missing dependencies first.

This module is the pure, I/O-free core of that resolution: given a target
addon and two lookup callbacks, :func:`resolve_dependencies` returns the
dependency addon dicts in install order (dependencies before dependents),
deduplicated, cycle-safe, and with already-installed entries skipped. The
orchestrator wires the real catalog/profile lookups in and performs the
actual installs.

This is distinct from CurseForge's *runtime* dependency data (handled by
``providers.curseforge_fns.install_curseforge_dependencies``), which comes
from the CurseForge API at download time rather than the local catalog.
"""

from __future__ import annotations

from collections.abc import Callable

# A result is two lists: addons to install (in order) and unknown dep ids.
DependencyResult = tuple[list[dict], list[str]]


def resolve_dependencies(
    addon: dict,
    *,
    find_addon: Callable[[str], dict | None],
    is_installed: Callable[[str], bool],
) -> DependencyResult:
    """Resolve the transitive catalog dependencies of *addon*.

    Returns ``(install_order, missing)`` where:

    * ``install_order`` is the list of dependency addon dicts to install,
      ordered so every dependency precedes the addon that needs it. The
      target *addon* itself is **not** included. Entries already reported
      as installed by *is_installed* are omitted.
    * ``missing`` is the list of declared dependency ids that *find_addon*
      could not resolve (not in the catalog), in encounter order.

    Cycles are handled gracefully — each id is visited at most once.
    """
    install_order: list[dict] = []
    missing: list[str] = []
    visited: set[str] = set()
    # Seed with the target id so a dependency cycle that points back at the
    # target never lists the target as its own dependency.
    target_id = addon.get("id")
    added: set[str] = {target_id} if target_id else set()

    def visit(node: dict) -> None:
        for dep_id in node.get("depends", []) or []:
            if dep_id in visited:
                continue
            visited.add(dep_id)
            dep = find_addon(dep_id)
            if dep is None:
                missing.append(dep_id)
                continue
            # Depth-first: install the dependency's own dependencies first.
            visit(dep)
            if not is_installed(dep_id) and dep_id not in added:
                install_order.append(dep)
                added.add(dep_id)

    visit(addon)
    return install_order, missing
