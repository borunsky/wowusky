"""Tests for wowusky.core.schedule — the systemd user-timer wrapper.

systemd is mocked: we never touch a real user bus. Unit-file writing is
exercised against a tmp XDG_CONFIG_HOME.
"""

from __future__ import annotations

from wowusky.core import schedule


def test_status_unavailable_when_no_systemd(monkeypatch):
    monkeypatch.setattr(schedule, "available", lambda: False)
    assert schedule.status() == {"available": False, "installed": False}


def test_status_available_not_installed(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(schedule, "available", lambda: True)
    st = schedule.status()
    assert st == {"available": True, "installed": False}


def test_enable_writes_units_and_calls_systemctl(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(schedule, "available", lambda: True)
    monkeypatch.setattr(schedule, "_wowusky_exec", lambda: "/usr/bin/wowusky")
    calls = []

    def fake_systemctl(*args):
        calls.append(args)
        return 0, ""

    monkeypatch.setattr(schedule, "_systemctl", fake_systemctl)
    # status() after enable calls _show; keep it simple.
    monkeypatch.setattr(schedule, "_show", lambda prop: "enabled" if prop == "UnitFileState" else "")

    res = schedule.enable("weekly")
    assert res["ok"] is True
    # unit files written
    with open(schedule.timer_path()) as fh:
        timer = fh.read()
    assert "OnCalendar=weekly" in timer
    with open(schedule.service_path()) as fh:
        assert "/usr/bin/wowusky update -q" in fh.read()
    # enabled --now invoked
    assert ("enable", "--now", schedule.TIMER_NAME) in calls


def test_enable_rejects_when_unavailable(monkeypatch):
    monkeypatch.setattr(schedule, "available", lambda: False)
    res = schedule.enable()
    assert res["ok"] is False
    assert "not available" in res["error"]


def test_disable_removes_units(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(schedule, "available", lambda: True)
    monkeypatch.setattr(schedule, "_systemctl", lambda *a: (0, ""))
    # seed unit files
    schedule._write_units("daily")
    assert schedule.os.path.isfile(schedule.timer_path())
    res = schedule.disable()
    assert res["ok"] is True
    assert not schedule.os.path.isfile(schedule.timer_path())
    assert not schedule.os.path.isfile(schedule.service_path())


def test_read_interval_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    schedule._write_units("weekly")
    assert schedule._read_interval() == "weekly"
