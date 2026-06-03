"""Regression tests for the v0.4.5 bug-fix batch.

Each test pins one concrete bug found during the v0.4.4 smoke test so
it cannot silently come back. Bugs that are purely about interactive
terminal output (B4) or GUI rendering (B5 display, B6 button state)
are covered only where they have a testable seam.
"""

from __future__ import annotations

import importlib
import os

import wowusky.core.paths as paths

# ── B10: app.py must honour XDG_DATA_HOME ───────────────────────────

def test_b10_paths_follow_xdg_data_home(monkeypatch, tmp_path):
    """core.paths must derive DATA_DIR from XDG_DATA_HOME at import."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    reloaded = importlib.reload(paths)
    try:
        assert tmp_path / "wowusky" == reloaded.DATA_DIR
        assert reloaded.CONFIG_DIR == reloaded.DATA_DIR
        assert tmp_path / "wowusky" / "config.json" == reloaded.CONFIG_FILE
        # INSTALLED_FILE is the legacy alias and must point at the same
        # place as LEGACY_INSTALLED_FILE.
        assert reloaded.INSTALLED_FILE == reloaded.LEGACY_INSTALLED_FILE
    finally:
        # Restore module state for other tests.
        monkeypatch.undo()
        importlib.reload(paths)


def test_b10_app_exposes_all_path_constants():
    """app.py must re-export every path name the GUI code uses."""
    import wowusky.app as app
    for name in ("CONFIG_DIR", "CONFIG_FILE", "INSTALLED_FILE",
                 "PROFILES_FILE", "INSTALLED_DIR", "BACKUP_DIR",
                 "LOG_DIR", "WAGO_FILE", "MANIFEST_DIR"):
        assert hasattr(app, name), f"app.py no longer exposes {name}"
        # All must be plain strings (the GUI uses os.path APIs on them).
        assert isinstance(getattr(app, name), str)


def test_b10_app_paths_match_core_paths():
    """app.py path constants must equal the core.paths source of truth."""
    import wowusky.app as app
    assert str(paths.CONFIG_DIR)    == app.CONFIG_DIR
    assert str(paths.CONFIG_FILE)   == app.CONFIG_FILE
    assert str(paths.PROFILES_FILE) == app.PROFILES_FILE
    assert str(paths.INSTALLED_DIR) == app.INSTALLED_DIR


def test_b10_no_hardcoded_expanduser_data_dir():
    """app.py must not re-derive its data dir with expanduser('~/...')."""
    src = (os.path.dirname(os.path.dirname(__file__)))
    app_py = os.path.join(src, "wowusky", "app.py")
    with open(app_py, encoding="utf-8") as fh:
        text = fh.read()
    # The specific anti-pattern that caused B10.
    assert 'expanduser(f"~/.local/share/{APP_NAME}")' not in text
    assert "expanduser('~/.local/share/" not in text


# ── B1: dry-run must not download ───────────────────────────────────

def test_b1_dry_run_install_does_no_network(monkeypatch, tmp_path):
    """install_addon in dry-run mode must return before downloading."""
    import wowusky.app as app
    import wowusky.orchestrator as orchestrator

    # install_addon lives in wowusky.orchestrator (re-exported from app);
    # patch the orchestrator module so the function's own namespace sees them.
    monkeypatch.setattr(orchestrator, "is_dry_run", lambda: True)

    def boom(*_a, **_kw):
        raise AssertionError("dry-run install attempted a network call")

    monkeypatch.setattr(orchestrator, "http_download", boom)
    monkeypatch.setattr(orchestrator, "get_download_url", boom)
    monkeypatch.setattr(orchestrator, "get_latest_version", lambda _a: "1.2.3")

    addon = {"id": "x", "name": "Test Addon", "source": "github",
             "folders": ["X"], "repo": "owner/repo"}

    logs: list[str] = []
    result = app.install_addon(addon, str(tmp_path), log=logs.append)

    assert result is True
    assert any("dry-run" in line for line in logs)


# ── B9: addons_path lives only in profiles.json ─────────────────────

def test_b9_set_addons_path_does_not_write_config(monkeypatch, tmp_path):
    """set_addons_path must not mirror the path into config.json."""
    import wowusky.app as app

    saved_config: dict = {}

    def fake_load_config():
        return dict(saved_config)

    def fake_save_config(c):
        saved_config.clear()
        saved_config.update(c)

    monkeypatch.setattr(app, "load_config", fake_load_config)
    monkeypatch.setattr(app, "save_config", fake_save_config)
    monkeypatch.setattr(app, "get_active_profile", lambda: {})
    # No active profile → only the config branch runs.

    app.set_addons_path("/some/wow/_retail_/Interface/AddOns")

    assert "addons_path" not in saved_config, (
        "set_addons_path still writes the legacy addons_path field "
        "into config.json (B9)"
    )
