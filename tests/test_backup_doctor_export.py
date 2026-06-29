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


def test_status_reports_stored_thread_records_without_workflow_inference(
    run_cli, temp_bus, tmp_path
):
    body_one = tmp_path / "one.md"
    body_one.write_text("first body\n", encoding="utf-8")
    body_two = tmp_path / "two.md"
    body_two.write_text("second body\n", encoding="utf-8")
    assert run_cli("--bus", str(temp_bus), "init", "--project", "demo").returncode == 0
    thread_id = _field(
        run_cli(
            "--bus",
            str(temp_bus),
            "start-thread",
            "--project",
            "demo",
            "--title",
            "Status Thread",
        ).stdout,
        "thread",
    )
    first_id = _field(
        run_cli(
            "--bus",
            str(temp_bus),
            "post",
            "--thread",
            thread_id,
            "--from",
            "planner",
            "--to",
            "implementer",
            "--subject",
            "Ready for review",
            "--body-file",
            str(body_one),
        ).stdout,
        "message",
    )
    second_id = _field(
        run_cli(
            "--bus",
            str(temp_bus),
            "post",
            "--thread",
            thread_id,
            "--from",
            "implementer",
            "--to",
            "planner",
            "--subject",
            "Reply",
            "--body-file",
            str(body_two),
            "--reply-to",
            first_id,
        ).stdout,
        "message",
    )
    ack_first = run_cli("--bus", str(temp_bus), "ack", first_id, "--agent", "implementer")
    assert ack_first.returncode == 0, ack_first.stderr
    artifact_id = _field(
        run_cli(
            "--bus",
            str(temp_bus),
            "artifact",
            "add",
            "--thread",
            thread_id,
            "--message",
            second_id,
            "--path",
            "docs/status.md",
            "--git-ref",
            "abc123",
            "--description",
            "status doc",
        ).stdout,
        "artifact",
    )

    result = run_cli("--bus", str(temp_bus), "status", "--thread", thread_id)

    assert result.returncode == 0, result.stderr
    output = result.stdout
    assert f"thread: {thread_id}" in output
    assert "project: demo" in output
    assert "title: Status Thread" in output
    assert "unread_messages:" in output
    assert f"message: {second_id}" in output
    assert "recent_messages:" in output
    assert "seq: 1" in output
    assert "seq: 2" in output
    assert "reply_links:" in output
    assert f"message: {second_id}" in output
    assert f"replies_to: {first_id}" in output
    assert "artifacts:" in output
    assert artifact_id in output
    assert "docs/status.md" in output
    assert "Ready for review" in output
    for forbidden_label in (
        "owner:",
        "complete:",
        "accepted:",
        "lifecycle:",
        "category:",
        "claim:",
        "workflow:",
        "stale:",
    ):
        assert forbidden_label not in output.lower()


def test_export_writes_thread_markdown_with_redacted_metadata(run_cli, temp_bus, tmp_path):
    body = tmp_path / "body.md"
    body.write_text("secret implementation details\n```nested fence\n", encoding="utf-8")
    assert run_cli("--bus", str(temp_bus), "init", "--project", "demo").returncode == 0
    thread_id = _field(
        run_cli(
            "--bus",
            str(temp_bus),
            "start-thread",
            "--project",
            "demo",
            "--title",
            "Export Thread",
        ).stdout,
        "thread",
    )
    message_id = _field(
        run_cli(
            "--bus",
            str(temp_bus),
            "post",
            "--thread",
            thread_id,
            "--from",
            "planner",
            "--to",
            "implementer",
            "--subject",
            "Export",
            "--body-file",
            str(body),
        ).stdout,
        "message",
    )
    ack = run_cli("--bus", str(temp_bus), "ack", message_id, "--agent", "implementer")
    assert ack.returncode == 0, ack.stderr
    acked_at = _field(ack.stdout, "acked_at")
    artifact_id = _field(
        run_cli(
            "--bus",
            str(temp_bus),
            "artifact",
            "add",
            "--thread",
            thread_id,
            "--message",
            message_id,
            "--path",
            "build/result.txt",
            "--description",
            "result file",
        ).stdout,
        "artifact",
    )

    result = run_cli(
        "--bus",
        str(temp_bus),
        "export",
        "--thread",
        thread_id,
        "--redacted",
    )

    assert result.returncode == 0, result.stderr
    export_path = temp_bus.parent / "exports" / f"{thread_id}.md"
    assert f"export: {export_path}" in result.stdout
    exported = export_path.read_text(encoding="utf-8")
    assert f"# Export Thread ({thread_id})" in exported
    assert f"- project: demo" in exported
    assert f"- message: {message_id}" in exported
    assert "- seq: 1" in exported
    assert "- from: planner" in exported
    assert "- to: implementer" in exported
    assert "- subject: Export" in exported
    assert f"- acked_at: {acked_at}" in exported
    assert "- body: omitted" in exported
    assert "secret implementation details" not in exported
    assert "## Unread Messages" in exported
    assert "No unread messages." in exported
    assert "## Recent Messages" in exported
    assert "## Reply References" in exported
    assert "No reply references." in exported
    assert artifact_id in exported
    assert "build/result.txt" in exported
    assert not list(export_path.parent.glob(f".{thread_id}.md.tmp.*"))

    full = run_cli("--bus", str(temp_bus), "export", "--thread", thread_id)
    assert full.returncode == 0, full.stderr
    exported_full = export_path.read_text(encoding="utf-8")
    assert "secret implementation details" in exported_full
    assert "````markdown\nsecret implementation details\n```nested fence\n````" in exported_full


def test_status_and_export_do_not_create_missing_bus(run_cli, tmp_path):
    missing_bus = tmp_path / "missing.sqlite"

    status = run_cli(
        "--bus",
        str(missing_bus),
        "status",
        "--thread",
        "thread_missing",
    )
    export = run_cli(
        "--bus",
        str(missing_bus),
        "export",
        "--thread",
        "thread_missing",
    )

    assert status.returncode != 0
    assert export.returncode != 0
    assert "does not exist" in status.stderr
    assert "does not exist" in export.stderr
    assert not missing_bus.exists()


def _field(output: str, name: str) -> str:
    prefix = f"{name}: "
    for line in output.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :]
    raise AssertionError(f"missing {name!r} in output:\n{output}")
