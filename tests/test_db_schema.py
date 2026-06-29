from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import stat

import pytest

from switchboard import cli


def test_init_creates_schema_version_one_and_tables(run_cli, temp_bus):
    result = run_cli("--bus", str(temp_bus), "init", "--project", "demo")
    assert result.returncode == 0, result.stderr

    with sqlite3.connect(temp_bus) as db:
        assert db.execute("pragma user_version").fetchone()[0] == 1
        tables = {
            row[0]
            for row in db.execute(
                "select name from sqlite_master where type = 'table'"
            )
        }
        thread_columns = {
            row[1] for row in db.execute("pragma table_info(threads)")
        }
        artifact_columns = {
            row[1] for row in db.execute("pragma table_info(artifacts)")
        }
        message_columns = {
            row[1] for row in db.execute("pragma table_info(messages)")
        }

    assert {"agents", "threads", "messages", "message_replies", "artifacts"} <= tables
    assert "events" not in tables
    assert {"status", "closed_at", "owner"}.isdisjoint(thread_columns)
    assert "kind" not in artifact_columns
    assert "priority" not in message_columns


def test_init_uses_private_posix_permissions(run_cli, temp_bus):
    result = run_cli("--bus", str(temp_bus), "init", "--project", "demo")
    assert result.returncode == 0, result.stderr

    if os.name == "posix":
        assert stat.S_IMODE(temp_bus.parent.stat().st_mode) == 0o700
        assert stat.S_IMODE(temp_bus.stat().st_mode) == 0o600


def test_init_rejects_unsafe_existing_parent_without_chmod(run_cli, tmp_path):
    if os.name != "posix":
        pytest.skip("POSIX permissions only")
    unsafe_parent = tmp_path / "unsafe-parent"
    unsafe_parent.mkdir(mode=0o755)
    unsafe_parent.chmod(0o755)
    bus_path = unsafe_parent / "bus.sqlite"

    result = run_cli("--bus", str(bus_path), "init", "--project", "demo")

    assert result.returncode != 0
    assert "private permissions" in result.stderr.lower()
    assert stat.S_IMODE(unsafe_parent.stat().st_mode) == 0o755
    assert not bus_path.exists()


def test_wal_and_busy_timeout_enabled(run_cli, temp_bus):
    result = run_cli("--bus", str(temp_bus), "init", "--project", "demo")
    assert result.returncode == 0, result.stderr

    with sqlite3.connect(temp_bus) as db:
        assert db.execute("pragma journal_mode").fetchone()[0].lower() == "wal"
        assert db.execute("pragma busy_timeout").fetchone()[0] >= 1000


def test_newer_schema_version_fails_clearly(run_cli, temp_bus):
    result = run_cli("--bus", str(temp_bus), "init", "--project", "demo")
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(temp_bus) as db:
        db.execute("pragma user_version = 99")

    result = run_cli("--bus", str(temp_bus), "doctor")

    assert result.returncode != 0
    assert "unsupported schema version" in result.stderr.lower()


def test_doctor_missing_bus_fails_without_creating_file(run_cli, temp_bus):
    result = run_cli("--bus", str(temp_bus), "doctor")

    assert result.returncode != 0
    assert "does not exist" in result.stderr.lower()
    assert not temp_bus.exists()


def test_doctor_uninitialized_bus_fails_with_schema_message(run_cli, temp_bus):
    sqlite3.connect(temp_bus).close()
    if os.name == "posix":
        temp_bus.chmod(0o600)

    result = run_cli("--bus", str(temp_bus), "doctor")

    assert result.returncode != 0
    assert "schema version" in result.stderr.lower()


def test_doctor_rejects_unsafe_parent_permissions(run_cli, temp_bus):
    if os.name != "posix":
        pytest.skip("POSIX permissions only")
    assert run_cli("--bus", str(temp_bus), "init", "--project", "demo").returncode == 0
    temp_bus.parent.chmod(0o755)

    result = run_cli("--bus", str(temp_bus), "doctor")

    assert result.returncode != 0
    assert "private permissions" in result.stderr.lower()


def test_doctor_rejects_unsafe_database_permissions(run_cli, temp_bus):
    if os.name != "posix":
        pytest.skip("POSIX permissions only")
    assert run_cli("--bus", str(temp_bus), "init", "--project", "demo").returncode == 0
    temp_bus.chmod(0o644)

    result = run_cli("--bus", str(temp_bus), "doctor")

    assert result.returncode != 0
    assert "private permissions" in result.stderr.lower()


def test_global_project_before_init_is_preserved(monkeypatch):
    calls = {}

    def fake_resolve_bus_path(bus, project, cwd):
        calls["project"] = project
        return Path("bus.sqlite")

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr(cli, "resolve_bus_path", fake_resolve_bus_path)
    monkeypatch.setattr(cli, "initialize_bus", lambda path, project_id: FakeConnection())

    result = cli.main(["--project", "demo", "init"])

    assert result == 0
    assert calls["project"] == "demo"


def test_migrate_returns_not_implemented(run_cli, temp_bus):
    result = run_cli("--bus", str(temp_bus), "migrate")

    assert result.returncode != 0
    assert "ERR_NOT_IMPLEMENTED" in result.stderr
