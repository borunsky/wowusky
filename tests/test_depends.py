"""Tests for catalog-level dependency resolution (wowusky.core.depends)."""

from __future__ import annotations

import pytest

from wowusky.core.depends import resolve_dependencies


def _catalog(*addons: dict) -> dict[str, dict]:
    return {a["id"]: a for a in addons}


def _resolve(target: dict, catalog: dict[str, dict], installed=()):
    installed_set = set(installed)
    return resolve_dependencies(
        target,
        find_addon=lambda i: catalog.get(i),
        is_installed=lambda i: i in installed_set,
    )


def test_no_depends_returns_empty():
    a = {"id": "a"}
    order, missing = _resolve(a, _catalog(a))
    assert order == []
    assert missing == []


def test_single_dependency_resolved():
    dep = {"id": "lib"}
    a = {"id": "a", "depends": ["lib"]}
    order, missing = _resolve(a, _catalog(a, dep))
    assert [x["id"] for x in order] == ["lib"]
    assert missing == []


def test_dependency_order_is_deps_first():
    base = {"id": "base"}
    mid = {"id": "mid", "depends": ["base"]}
    top = {"id": "top", "depends": ["mid"]}
    order, missing = _resolve(top, _catalog(base, mid, top))
    # base must come before mid (depth-first, dependency before dependent).
    assert [x["id"] for x in order] == ["base", "mid"]
    assert missing == []


def test_already_installed_dependency_is_skipped():
    dep = {"id": "lib"}
    a = {"id": "a", "depends": ["lib"]}
    order, missing = _resolve(a, _catalog(a, dep), installed=["lib"])
    assert order == []
    assert missing == []


def test_missing_dependency_reported_not_raised():
    a = {"id": "a", "depends": ["ghost"]}
    order, missing = _resolve(a, _catalog(a))
    assert order == []
    assert missing == ["ghost"]


def test_diamond_dependency_deduplicated():
    base = {"id": "base"}
    left = {"id": "left", "depends": ["base"]}
    right = {"id": "right", "depends": ["base"]}
    top = {"id": "top", "depends": ["left", "right"]}
    order, missing = _resolve(top, _catalog(base, left, right, top))
    ids = [x["id"] for x in order]
    assert ids.count("base") == 1
    # base precedes both left and right
    assert ids.index("base") < ids.index("left")
    assert ids.index("base") < ids.index("right")
    assert missing == []


def test_cycle_does_not_recurse_forever():
    a = {"id": "a", "depends": ["b"]}
    b = {"id": "b", "depends": ["a"]}
    order, missing = _resolve(a, _catalog(a, b))
    # b is collected once; the cycle back to a is broken by the visited set.
    assert [x["id"] for x in order] == ["b"]
    assert missing == []


def test_real_catalog_littlewigs_depends_on_bigwigs():
    from wowusky.catalog import load_catalog

    catalog = {a["id"]: a for a in load_catalog()}
    order, missing = _resolve(catalog["littlewigs"], catalog)
    assert "bigwigs" in [x["id"] for x in order]
    assert missing == []


@pytest.mark.parametrize("plugin", [
    "details_tiny_threat_cf",
    "details_compare2_cf",
    "details_streamer_cf",
])
def test_real_catalog_details_plugins_depend_on_details(plugin):
    from wowusky.catalog import load_catalog

    catalog = {a["id"]: a for a in load_catalog()}
    order, missing = _resolve(catalog[plugin], catalog)
    assert [x["id"] for x in order] == ["details_cf"]
    assert missing == []


# ── orchestrator wiring ──────────────────────────────────────────────

def test_orchestrator_installs_dependency_before_target(monkeypatch):
    """install_addon should install resolved deps (in order) before the target."""
    import wowusky.orchestrator as orch

    lib = {"id": "lib", "name": "Lib", "source": "github"}
    app = {"id": "app", "name": "App", "source": "github", "depends": ["lib"]}

    monkeypatch.setattr(orch, "find_addon_by_id",
                        lambda i: {"lib": lib, "app": app}.get(i))
    monkeypatch.setattr(orch, "load_installed", lambda: {})

    calls: list[str] = []
    monkeypatch.setattr(orch, "_install_single",
                        lambda a, p, log=print, progress=None: calls.append(a["id"]) or True)

    orch.install_addon(app, "/tmp/addons", log=lambda *_: None)
    assert calls == ["lib", "app"]


def test_orchestrator_skips_installed_dependency(monkeypatch):
    import wowusky.orchestrator as orch

    lib = {"id": "lib", "name": "Lib", "source": "github"}
    app = {"id": "app", "name": "App", "source": "github", "depends": ["lib"]}

    monkeypatch.setattr(orch, "find_addon_by_id",
                        lambda i: {"lib": lib, "app": app}.get(i))
    monkeypatch.setattr(orch, "load_installed", lambda: {"lib": {}})

    calls: list[str] = []
    monkeypatch.setattr(orch, "_install_single",
                        lambda a, p, log=print, progress=None: calls.append(a["id"]) or True)

    orch.install_addon(app, "/tmp/addons", log=lambda *_: None)
    assert calls == ["app"]


def test_orchestrator_install_deps_false_skips_resolution(monkeypatch):
    import wowusky.orchestrator as orch

    app = {"id": "app", "name": "App", "source": "github", "depends": ["lib"]}

    def _boom(_i):
        raise AssertionError("dependency resolution should not run")

    monkeypatch.setattr(orch, "find_addon_by_id", _boom)

    calls: list[str] = []
    monkeypatch.setattr(orch, "_install_single",
                        lambda a, p, log=print, progress=None: calls.append(a["id"]) or True)

    orch.install_addon(app, "/tmp/addons", log=lambda *_: None, install_deps=False)
    assert calls == ["app"]
