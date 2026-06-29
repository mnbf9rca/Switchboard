from __future__ import annotations

import os
import sqlite3
import stat


def test_backup_uses_readable_sqlite_copy(run_cli, temp_bus, tmp_path):
    assert run_cli("--bus", str(temp_bus), "init", "--project", "demo").returncode == 0
    thread = run_cli(
        "--bus",
        str(temp_bus),
        "start-thread",
        "--project",
        "demo",
        "--title",
        "backup source",
    )
    assert thread.returncode == 0, thread.stderr

    backup = tmp_path / "backup.sqlite"
    result = run_cli("--bus", str(temp_bus), "backup", "--out", str(backup))

    assert result.returncode == 0, result.stderr
    assert backup.exists()
    if os.name == "posix":
        assert stat.S_IMODE(backup.stat().st_mode) == 0o600
    with sqlite3.connect(backup) as db:
        assert db.execute("pragma integrity_check").fetchone()[0] == "ok"
        assert db.execute("pragma user_version").fetchone()[0] == 1
        titles = [row[0] for row in db.execute("select title from threads")]
    assert titles == ["backup source"]

    with sqlite3.connect(temp_bus) as db:
        assert db.execute("pragma integrity_check").fetchone()[0] == "ok"


def test_backup_does_not_chmod_existing_output_directory(run_cli, temp_bus, tmp_path):
    if os.name != "posix":
        return
    assert run_cli("--bus", str(temp_bus), "init", "--project", "demo").returncode == 0
    output_dir = tmp_path / "public"
    output_dir.mkdir(mode=0o755)
    output_dir.chmod(0o755)

    result = run_cli("--bus", str(temp_bus), "backup", "--out", str(output_dir / "bus.sqlite"))

    assert result.returncode == 0, result.stderr
    assert stat.S_IMODE(output_dir.stat().st_mode) == 0o755


def test_restore_validates_backup_and_refuses_active_target(run_cli, temp_bus, tmp_path):
    assert run_cli("--bus", str(temp_bus), "init", "--project", "demo").returncode == 0
    original = run_cli(
        "--bus",
        str(temp_bus),
        "start-thread",
        "--project",
        "demo",
        "--title",
        "original",
    )
    assert original.returncode == 0, original.stderr
    backup = tmp_path / "backup.sqlite"
    assert run_cli("--bus", str(temp_bus), "backup", "--out", str(backup)).returncode == 0

    replacement_bus = tmp_path / "replacement" / "bus.sqlite"
    assert run_cli("--bus", str(replacement_bus), "init", "--project", "demo").returncode == 0
    replacement = run_cli(
        "--bus",
        str(replacement_bus),
        "start-thread",
        "--project",
        "demo",
        "--title",
        "replacement",
    )
    assert replacement.returncode == 0, replacement.stderr

    garbage = tmp_path / "garbage.sqlite"
    garbage.write_text("not a sqlite database", encoding="utf-8")
    bad = run_cli("--bus", str(replacement_bus), "restore", "--from", str(garbage))
    assert bad.returncode != 0
    assert "backup" in bad.stderr.lower()
    with sqlite3.connect(replacement_bus) as db:
        assert [row[0] for row in db.execute("select title from threads")] == [
            "replacement"
        ]

    wrong_schema = tmp_path / "wrong-schema.sqlite"
    with sqlite3.connect(wrong_schema) as db:
        db.execute("create table unexpected(id text)")
        db.execute("pragma user_version = 1")
    malformed = run_cli(
        "--bus",
        str(replacement_bus),
        "restore",
        "--from",
        str(wrong_schema),
    )
    assert malformed.returncode != 0
    assert "schema" in malformed.stderr.lower()
    with sqlite3.connect(replacement_bus) as db:
        assert [row[0] for row in db.execute("select title from threads")] == [
            "replacement"
        ]
    assert not list(replacement_bus.parent.glob(f".{replacement_bus.name}.tmp.*"))

    weak_schema = tmp_path / "weak-schema.sqlite"
    with sqlite3.connect(weak_schema) as db:
        db.executescript(
            """
            create table agents(id text, display_name text, harness text, role text, created_at text, last_seen_at text);
            create table threads(id text, project_id text, title text, created_at text, updated_at text);
            create table messages(id text, thread_id text, seq integer, from_agent text, to_agent text, subject text, body_md text, created_at text, acked_at text);
            create table message_replies(message_id text, reply_to_message_id text);
            create table artifacts(id text, thread_id text, message_id text, path text, git_ref text, description text, created_at text);
            pragma user_version = 1;
            """
        )
    weak = run_cli(
        "--bus",
        str(replacement_bus),
        "restore",
        "--from",
        str(weak_schema),
    )
    assert weak.returncode != 0
    assert "schema" in weak.stderr.lower()

    locked = sqlite3.connect(replacement_bus, timeout=0.1)
    try:
        locked.execute("begin immediate")
        refused = run_cli("--bus", str(replacement_bus), "restore", "--from", str(backup))
    finally:
        locked.rollback()
        locked.close()
    assert refused.returncode != 0
    assert "exclusive" in refused.stderr.lower() or "locked" in refused.stderr.lower()
    with sqlite3.connect(replacement_bus) as db:
        assert [row[0] for row in db.execute("select title from threads")] == [
            "replacement"
        ]
    assert not list(replacement_bus.parent.glob(f".{replacement_bus.name}.tmp.*"))

    restored = run_cli("--bus", str(replacement_bus), "restore", "--from", str(backup))
    assert restored.returncode == 0, restored.stderr
    with sqlite3.connect(replacement_bus) as db:
        assert db.execute("pragma integrity_check").fetchone()[0] == "ok"
        assert [row[0] for row in db.execute("select title from threads")] == [
            "original"
        ]
    assert not list(replacement_bus.parent.glob(f".{replacement_bus.name}.tmp.*"))


def test_doctor_reports_core_db_health_only(run_cli, temp_bus):
    assert run_cli("--bus", str(temp_bus), "init", "--project", "demo").returncode == 0

    result = run_cli("--bus", str(temp_bus), "doctor")

    assert result.returncode == 0, result.stderr
    output = result.stdout.lower()
    for expected in (
        "db opens",
        "schema version",
        "integrity",
        "wal",
        "permissions",
    ):
        assert expected in output
    for forbidden in (
        "claim",
        "stale",
        "review",
        "checkpoint",
        "message category",
        "lifecycle",
        "workflow",
    ):
        assert forbidden not in output


def test_doctor_rejects_garbage_database_without_traceback(run_cli, temp_bus):
    temp_bus.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp_bus.write_text("not sqlite", encoding="utf-8")
    if os.name == "posix":
        temp_bus.chmod(0o600)

    result = run_cli("--bus", str(temp_bus), "doctor")

    assert result.returncode != 0
    assert "valid sqlite" in result.stderr.lower()
    assert "Traceback" not in result.stderr
