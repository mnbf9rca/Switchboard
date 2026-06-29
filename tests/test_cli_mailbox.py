from __future__ import annotations

import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from conftest import _agent_comm_script
from agent_comm.paths import resolve_bus_path


def test_register_start_thread_and_post_round_trip(run_cli, temp_bus, tmp_path):
    body_file = tmp_path / "body.md"
    body = "First line\r\n\r\n- keep markdown exactly\r\n"
    body_file.write_bytes(body.encode("utf-8"))

    assert run_cli("--bus", str(temp_bus), "init", "--project", "bootstrap").returncode == 0
    register = run_cli(
        "--bus",
        str(temp_bus),
        "register",
        "--agent",
        "planner",
        "--display-name",
        "Planning Agent",
        "--harness",
        "codex",
        "--role",
        "lead",
    )
    assert register.returncode == 0
    assert "planner" in register.stdout

    thread = run_cli(
        "--bus",
        str(temp_bus),
        "start-thread",
        "--project",
        "demo-project",
        "--title",
        "Handoff",
    )
    assert thread.returncode == 0
    thread_id = _field(thread.stdout, "thread")

    post = run_cli(
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
        "Build it",
        "--body-file",
        str(body_file),
    )
    assert post.returncode == 0
    message_id = _field(post.stdout, "message")

    with sqlite3.connect(temp_bus) as db:
        db.row_factory = sqlite3.Row
        saved_thread = db.execute("select * from threads where id = ?", (thread_id,)).fetchone()
        saved_message = db.execute("select * from messages where id = ?", (message_id,)).fetchone()

    assert saved_thread["project_id"] == "demo-project"
    assert saved_message["body_md"].encode("utf-8") == body_file.read_bytes()
    assert saved_message["subject"] == "Build it"


def test_implemented_commands_use_usage_errors(run_cli, temp_bus):
    assert run_cli("--bus", str(temp_bus), "init", "--project", "demo").returncode == 0

    register = run_cli("--bus", str(temp_bus), "register")
    assert register.returncode != 0
    assert "ERR_NOT_IMPLEMENTED" not in register.stdout
    assert "--agent" in register.stderr

    artifact = run_cli("--bus", str(temp_bus), "artifact")
    assert artifact.returncode != 0
    assert "usage:" in artifact.stderr


def test_repeated_reply_to_flags_are_stored(run_cli, temp_bus, tmp_path):
    body_file = tmp_path / "body.md"
    body_file.write_text("reply body")

    assert run_cli("--bus", str(temp_bus), "init", "--project", "demo").returncode == 0
    thread_id = _field(
        run_cli(
            "--bus",
            str(temp_bus),
            "start-thread",
            "--project",
            "demo",
            "--title",
            "Thread",
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
            "a",
            "--to",
            "b",
            "--subject",
            "One",
            "--body-file",
            str(body_file),
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
            "b",
            "--to",
            "a",
            "--subject",
            "Two",
            "--body-file",
            str(body_file),
            "--reply-to",
            first_id,
            "--reply-to",
            first_id,
        ).stdout,
        "message",
    )

    with sqlite3.connect(temp_bus) as db:
        rows = db.execute(
            "select message_id, reply_to_message_id from message_replies"
        ).fetchall()

    assert rows == [(second_id, first_id)]


def test_post_rejects_non_utf8_body_file_without_traceback(run_cli, temp_bus, tmp_path):
    body_file = tmp_path / "body.md"
    body_file.write_bytes(b"\xff")

    assert run_cli("--bus", str(temp_bus), "init", "--project", "demo").returncode == 0
    thread_id = _field(
        run_cli(
            "--bus",
            str(temp_bus),
            "start-thread",
            "--project",
            "demo",
            "--title",
            "Thread",
        ).stdout,
        "thread",
    )

    result = run_cli(
        "--bus",
        str(temp_bus),
        "post",
        "--thread",
        thread_id,
        "--from",
        "a",
        "--to",
        "b",
        "--subject",
        "Invalid body",
        "--body-file",
        str(body_file),
    )

    assert result.returncode != 0
    assert "ERROR:" in result.stderr
    assert "Traceback" not in result.stderr


def test_inbox_show_ack_and_wait_do_not_auto_ack(run_cli, temp_bus, tmp_path):
    body_file = tmp_path / "body.md"
    body_file.write_text("body for inbox\n")

    assert run_cli("--bus", str(temp_bus), "init", "--project", "demo").returncode == 0
    thread_id = _field(
        run_cli(
            "--bus",
            str(temp_bus),
            "start-thread",
            "--project",
            "demo",
            "--title",
            "Inbox",
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
            "Unread",
            "--body-file",
            str(body_file),
        ).stdout,
        "message",
    )

    inbox = run_cli("--bus", str(temp_bus), "inbox", "--agent", "implementer")
    assert inbox.returncode == 0
    assert message_id in inbox.stdout
    assert "Unread" in inbox.stdout

    wait = run_cli("--bus", str(temp_bus), "wait", "--agent", "implementer", "--timeout", "0")
    assert wait.returncode == 0
    assert message_id in wait.stdout
    assert _acked_at(temp_bus, message_id) is None

    show = run_cli("--bus", str(temp_bus), "show", message_id)
    assert show.returncode == 0
    assert "body for inbox\n" in show.stdout
    assert _acked_at(temp_bus, message_id) is None

    wrong_ack = run_cli("--bus", str(temp_bus), "ack", message_id, "--agent", "planner")
    assert wrong_ack.returncode != 0
    assert "recipient" in wrong_ack.stderr

    ack = run_cli("--bus", str(temp_bus), "ack", message_id, "--agent", "implementer")
    assert ack.returncode == 0
    assert _acked_at(temp_bus, message_id) is not None
    assert message_id not in run_cli("--bus", str(temp_bus), "inbox", "--agent", "implementer").stdout


def test_wait_timeout_reports_failure(run_cli, temp_bus):
    assert run_cli("--bus", str(temp_bus), "init", "--project", "demo").returncode == 0

    result = run_cli(
        "--bus",
        str(temp_bus),
        "wait",
        "--agent",
        "implementer",
        "--timeout",
        "0",
    )

    assert result.returncode != 0
    assert "timed out" in result.stderr


def test_wait_follow_polls_until_message_arrives(run_cli, temp_bus, tmp_path):
    body_file = tmp_path / "body.md"
    body_file.write_text("late body")

    assert run_cli("--bus", str(temp_bus), "init", "--project", "demo").returncode == 0
    thread_id = _field(
        run_cli(
            "--bus",
            str(temp_bus),
            "start-thread",
            "--project",
            "demo",
            "--title",
            "Wait",
        ).stdout,
        "thread",
    )

    wait_process = subprocess.Popen(
        [
            str(_agent_comm_script(Path(sys.executable))),
            "--bus",
            str(temp_bus),
            "wait",
            "--agent",
            "implementer",
            "-f",
            "--timeout",
            "2",
        ],
        cwd=tmp_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        time.sleep(0.2)
        post = run_cli(
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
            "Late",
            "--body-file",
            str(body_file),
        )
        assert post.returncode == 0
        message_id = _field(post.stdout, "message")
        stdout, stderr = wait_process.communicate(timeout=3)
    finally:
        if wait_process.poll() is None:
            wait_process.terminate()

    assert wait_process.returncode == 0, stderr
    assert message_id in stdout
    assert _acked_at(temp_bus, message_id) is None


def test_artifact_add_links_thread_and_optional_message(run_cli, temp_bus, tmp_path):
    body_file = tmp_path / "body.md"
    body_file.write_text("body")

    assert run_cli("--bus", str(temp_bus), "init", "--project", "demo").returncode == 0
    thread_id = _field(
        run_cli(
            "--bus",
            str(temp_bus),
            "start-thread",
            "--project",
            "demo",
            "--title",
            "Artifacts",
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
            "Artifact",
            "--body-file",
            str(body_file),
        ).stdout,
        "message",
    )

    artifact = run_cli(
        "--bus",
        str(temp_bus),
        "artifact",
        "add",
        "--thread",
        thread_id,
        "--message",
        message_id,
        "--path",
        "docs/handoff.md",
        "--git-ref",
        "abc123",
        "--description",
        "handoff document",
    )
    assert artifact.returncode == 0
    artifact_id = _field(artifact.stdout, "artifact")

    with sqlite3.connect(temp_bus) as db:
        db.row_factory = sqlite3.Row
        row = db.execute("select * from artifacts where id = ?", (artifact_id,)).fetchone()

    assert row["thread_id"] == thread_id
    assert row["message_id"] == message_id
    assert row["path"] == "docs/handoff.md"
    assert row["git_ref"] == "abc123"
    assert row["description"] == "handoff document"

    show = run_cli("--bus", str(temp_bus), "show", message_id)
    assert show.returncode == 0
    assert artifact_id in show.stdout
    assert "docs/handoff.md" in show.stdout


def test_show_missing_bus_fails_without_creating_mailbox(run_cli, tmp_path):
    missing_bus = tmp_path / "missing.sqlite"

    result = run_cli("--bus", str(missing_bus), "show", "msg_missing")

    assert result.returncode != 0
    assert "mailbox does not exist; send a message first" in result.stderr
    assert not missing_bus.exists()


def test_send_inline_auto_initializes_registers_and_posts(run_cli, temp_bus):
    result = run_cli(
        "--bus",
        str(temp_bus),
        "send",
        "--as",
        "planner-main",
        "--to",
        "implementer-feature-a",
        "--title",
        "Coordination test",
        "Please acknowledge this test.",
    )

    assert result.returncode == 0, result.stderr
    thread_id = _field(result.stdout, "thread")
    message_id = _field(result.stdout, "message")

    thread = _row(temp_bus, "threads", thread_id)
    message = _row(temp_bus, "messages", message_id)

    assert thread["title"] == "Coordination test"
    assert message["thread_id"] == thread_id
    assert message["from_agent"] == "planner-main"
    assert message["to_agent"] == "implementer-feature-a"
    assert message["subject"] == "Coordination test"
    assert message["body_md"] == "Please acknowledge this test."
    assert message["acked_at"] is None
    assert "agent_created: planner-main" in result.stdout
    assert "agent_created: implementer-feature-a" in result.stdout

    with sqlite3.connect(temp_bus) as db:
        agents = {
            row[0]
            for row in db.execute("select id from agents order by id").fetchall()
        }
    assert agents == {"implementer-feature-a", "planner-main"}


def test_send_requires_exactly_one_body_source(run_cli, temp_bus, tmp_path):
    body_file = tmp_path / "body.md"
    body_file.write_text("from file", encoding="utf-8")

    missing = run_cli(
        "--bus",
        str(temp_bus),
        "send",
        "--as",
        "planner-main",
        "--to",
        "implementer-feature-a",
    )
    assert missing.returncode != 0
    assert "body source" in missing.stderr
    assert not temp_bus.exists()

    duplicate = run_cli(
        "--bus",
        str(temp_bus),
        "send",
        "--as",
        "planner-main",
        "--to",
        "implementer-feature-a",
        "--body-file",
        str(body_file),
        "inline body",
    )
    assert duplicate.returncode != 0
    assert "body source" in duplicate.stderr


def test_send_supports_body_file_stdin_artifacts_and_in_thread(
    run_cli, temp_bus, tmp_path, cli_env
):
    artifact_path = tmp_path / "plan.md"
    artifact_path.write_text("# Plan\n", encoding="utf-8")
    body_file = tmp_path / "body.md"
    body_file.write_text("from file", encoding="utf-8")

    first = run_cli(
        "--bus",
        str(temp_bus),
        "send",
        "--as",
        "planner-main",
        "--to",
        "implementer-feature-a",
        "--body-file",
        str(body_file),
        "--artifact",
        str(artifact_path),
    )
    assert first.returncode == 0, first.stderr
    thread_id = _field(first.stdout, "thread")
    first_message_id = _field(first.stdout, "message")

    artifact = _row(temp_bus, "artifacts", _field(first.stdout, "artifact"))
    assert artifact["thread_id"] == thread_id
    assert artifact["message_id"] == first_message_id
    assert artifact["path"] == str(artifact_path)

    script = _agent_comm_script(Path(sys.executable))
    second = subprocess.run(
        [
            str(script),
            "--bus",
            str(temp_bus),
            "send",
            "--as",
            "planner-main",
            "--to",
            "implementer-feature-a",
            "--in-thread",
            thread_id,
            "--stdin",
        ],
        cwd=tmp_path,
        env=cli_env,
        input="from stdin",
        text=True,
        capture_output=True,
        check=False,
    )
    assert second.returncode == 0, second.stderr
    second_message_id = _field(second.stdout, "message")
    assert _field(second.stdout, "thread") == thread_id
    assert _row(temp_bus, "messages", second_message_id)["body_md"] == "from stdin"
    assert _count_rows(temp_bus, "threads") == 1

    missing_thread = run_cli(
        "--bus",
        str(temp_bus),
        "send",
        "--as",
        "planner-main",
        "--to",
        "implementer-feature-a",
        "--in-thread",
        "thread_missing",
        "body",
    )
    assert missing_thread.returncode != 0
    assert "thread" in missing_thread.stderr.lower()


def test_send_uses_derived_default_bus_without_project_or_bus(
    make_git_repo, tmp_path, monkeypatch, cli_env
):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_git_repo("repo", origin="git@github.com:Example/Repo.git")
    script = _agent_comm_script(Path(sys.executable))

    result = subprocess.run(
        [
            str(script),
            "send",
            "--as",
            "planner-main",
            "--to",
            "implementer-feature-a",
            "Default bus message.",
        ],
        cwd=repo,
        env={**cli_env, "HOME": str(tmp_path / "home")},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    bus_path = resolve_bus_path(None, None, repo)
    assert bus_path.exists()
    message_id = _field(result.stdout, "message")
    assert _row(bus_path, "messages", message_id)["body_md"] == "Default bus message."


def test_send_prints_agent_created_only_for_new_agents(run_cli, temp_bus):
    first = run_cli(
        "--bus",
        str(temp_bus),
        "send",
        "--as",
        "planner-main",
        "--to",
        "implementer-feature-a",
        "First message.",
    )
    assert first.returncode == 0, first.stderr
    assert "agent_created: planner-main" in first.stdout
    assert "agent_created: implementer-feature-a" in first.stdout

    second = run_cli(
        "--bus",
        str(temp_bus),
        "send",
        "--as",
        "planner-main",
        "--to",
        "implementer-feature-a",
        "Second message.",
    )
    assert second.returncode == 0, second.stderr
    assert "agent_created:" not in second.stdout


def test_send_preserves_existing_agent_metadata(run_cli, temp_bus):
    assert run_cli("--bus", str(temp_bus), "init", "--project", "demo").returncode == 0
    register = run_cli(
        "--bus",
        str(temp_bus),
        "register",
        "--agent",
        "planner-main",
        "--display-name",
        "Planning Agent",
        "--harness",
        "codex",
        "--role",
        "lead",
    )
    assert register.returncode == 0, register.stderr

    result = run_cli(
        "--bus",
        str(temp_bus),
        "send",
        "--as",
        "planner-main",
        "--to",
        "implementer-feature-a",
        "Do not clear metadata.",
    )

    assert result.returncode == 0, result.stderr
    planner = _row(temp_bus, "agents", "planner-main")
    assert planner["display_name"] == "Planning Agent"
    assert planner["harness"] == "codex"
    assert planner["role"] == "lead"
    assert "agent_created: planner-main" not in result.stdout
    assert "agent_created: implementer-feature-a" in result.stdout


def test_reply_uses_original_thread_recipient_and_auto_acks(run_cli, temp_bus):
    original = run_cli(
        "--bus",
        str(temp_bus),
        "send",
        "--as",
        "planner-main",
        "--to",
        "implementer-feature-a",
        "--title",
        "Please review",
        "Can you review this?",
    )
    assert original.returncode == 0, original.stderr
    thread_id = _field(original.stdout, "thread")
    original_id = _field(original.stdout, "message")

    reply = run_cli(
        "--bus",
        str(temp_bus),
        "reply",
        original_id,
        "--as",
        "implementer-feature-a",
        "Reviewed and ready.",
    )

    assert reply.returncode == 0, reply.stderr
    reply_id = _field(reply.stdout, "message")
    assert _field(reply.stdout, "thread") == thread_id
    assert f"acked: {original_id}" in reply.stdout

    reply_row = _row(temp_bus, "messages", reply_id)
    assert reply_row["thread_id"] == thread_id
    assert reply_row["from_agent"] == "implementer-feature-a"
    assert reply_row["to_agent"] == "planner-main"
    assert reply_row["subject"] == "Re: Please review"
    assert reply_row["body_md"] == "Reviewed and ready."
    assert _acked_at(temp_bus, original_id) is not None

    with sqlite3.connect(temp_bus) as db:
        links = db.execute(
            "select message_id, reply_to_message_id from message_replies"
        ).fetchall()
    assert links == [(reply_id, original_id)]


def test_reply_rejects_to_override(run_cli, temp_bus):
    original = run_cli(
        "--bus",
        str(temp_bus),
        "send",
        "--as",
        "planner-main",
        "--to",
        "implementer-feature-a",
        "--title",
        "No override",
        "Original body.",
    )
    assert original.returncode == 0, original.stderr
    original_id = _field(original.stdout, "message")

    reply = run_cli(
        "--bus",
        str(temp_bus),
        "reply",
        original_id,
        "--as",
        "implementer-feature-a",
        "--to",
        "someone-else",
        "Body.",
    )

    assert reply.returncode != 0
    assert "--to" in reply.stderr
    assert _count_rows(temp_bus, "messages") == 1
    assert _acked_at(temp_bus, original_id) is None


def test_reply_rejects_non_recipient_agent(run_cli, temp_bus):
    original = run_cli(
        "--bus",
        str(temp_bus),
        "send",
        "--as",
        "planner-main",
        "--to",
        "implementer-feature-a",
        "--title",
        "Recipient only",
        "Original body.",
    )
    assert original.returncode == 0, original.stderr
    original_id = _field(original.stdout, "message")

    reply = run_cli(
        "--bus",
        str(temp_bus),
        "reply",
        original_id,
        "--as",
        "planner-main",
        "Body.",
    )

    assert reply.returncode != 0
    assert "recipient" in reply.stderr
    assert _count_rows(temp_bus, "messages") == 1
    assert _acked_at(temp_bus, original_id) is None


def test_next_shows_body_without_ack_and_ack_is_explicit(run_cli, temp_bus):
    send = run_cli(
        "--bus",
        str(temp_bus),
        "send",
        "--as",
        "planner-main",
        "--to",
        "implementer-feature-a",
        "--title",
        "Next",
        "Body visible in next.\n",
    )
    assert send.returncode == 0, send.stderr
    message_id = _field(send.stdout, "message")

    next_result = run_cli(
        "--bus",
        str(temp_bus),
        "next",
        "--as",
        "implementer-feature-a",
    )
    assert next_result.returncode == 0, next_result.stderr
    assert message_id in next_result.stdout
    assert "Body visible in next.\n" in next_result.stdout
    assert _acked_at(temp_bus, message_id) is None

    ack = run_cli(
        "--bus",
        str(temp_bus),
        "ack",
        message_id,
        "--as",
        "implementer-feature-a",
    )
    assert ack.returncode == 0, ack.stderr
    assert _acked_at(temp_bus, message_id) is not None

    empty_next = run_cli(
        "--bus",
        str(temp_bus),
        "next",
        "--as",
        "implementer-feature-a",
    )
    assert empty_next.returncode == 0, empty_next.stderr
    assert empty_next.stdout == ""


def test_inbox_and_wait_accept_as_alias(run_cli, temp_bus):
    send = run_cli(
        "--bus",
        str(temp_bus),
        "send",
        "--as",
        "planner-main",
        "--to",
        "implementer-feature-a",
        "--title",
        "Alias",
        "Alias body.",
    )
    assert send.returncode == 0, send.stderr
    message_id = _field(send.stdout, "message")

    inbox = run_cli(
        "--bus",
        str(temp_bus),
        "inbox",
        "--as",
        "implementer-feature-a",
    )
    assert inbox.returncode == 0, inbox.stderr
    assert message_id in inbox.stdout

    wait = run_cli(
        "--bus",
        str(temp_bus),
        "wait",
        "--as",
        "implementer-feature-a",
        "--timeout",
        "0",
    )
    assert wait.returncode == 0, wait.stderr
    assert message_id in wait.stdout
    assert _acked_at(temp_bus, message_id) is None


def test_read_command_does_not_create_sqlite_sidecars(run_cli, temp_bus):
    send = run_cli(
        "--bus",
        str(temp_bus),
        "send",
        "--as",
        "planner-main",
        "--to",
        "implementer-feature-a",
        "Existing mailbox read.",
    )
    assert send.returncode == 0, send.stderr

    with sqlite3.connect(temp_bus) as db:
        db.execute("pragma wal_checkpoint(TRUNCATE)")
    for suffix in ("-wal", "-shm"):
        temp_bus.with_name(f"{temp_bus.name}{suffix}").unlink(missing_ok=True)

    inbox = run_cli("--bus", str(temp_bus), "inbox", "--as", "implementer-feature-a")

    assert inbox.returncode == 0, inbox.stderr
    assert "Existing mailbox read." in inbox.stdout
    for suffix in ("-wal", "-shm"):
        assert not temp_bus.with_name(f"{temp_bus.name}{suffix}").exists()


def test_high_level_read_commands_do_not_create_missing_mailbox(run_cli, tmp_path):
    missing_bus = tmp_path / "empty.sqlite"

    cases = [
        ("inbox", "--as", "implementer"),
        ("next", "--as", "implementer"),
        ("show", "msg_missing"),
        ("wait", "--as", "implementer", "--timeout", "0"),
    ]

    for args in cases:
        result = run_cli("--bus", str(missing_bus), *args)

        assert result.returncode != 0
        assert "mailbox does not exist; send a message first" in result.stderr
        assert not missing_bus.exists()


def test_read_commands_require_identity_before_creating_bus(run_cli, tmp_path):
    cases = [
        ("inbox",),
        ("ack", "msg_missing"),
        ("wait", "--timeout", "0"),
    ]

    for index, args in enumerate(cases):
        missing_bus = tmp_path / f"missing-{index}.sqlite"

        result = run_cli("--bus", str(missing_bus), *args)

        assert result.returncode != 0
        assert "--as or --agent is required" in result.stderr
        assert not missing_bus.exists()


def test_sqlite_operational_errors_do_not_show_tracebacks(monkeypatch, capsys):
    from agent_comm import cli

    def raise_readonly(_args):
        raise sqlite3.OperationalError("attempt to write a readonly database")

    monkeypatch.setattr(cli, "_handle_next", raise_readonly)

    result = cli.main(["next", "--as", "implementer-main"])
    captured = capsys.readouterr()

    assert result == 1
    assert "ERROR: attempt to write a readonly database" in captured.err
    assert "Traceback" not in captured.err


def test_send_and_next_share_default_bus_across_worktrees(
    make_git_repo, tmp_path, monkeypatch, cli_env
):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo_a = make_git_repo("repo-a", origin="git@github.com:Example/Repo.git")
    repo_b = make_git_repo("repo-b", origin="https://github.com/example/repo.git")
    script = _agent_comm_script(Path(sys.executable))
    env = {**cli_env, "HOME": str(tmp_path / "home")}

    send = subprocess.run(
        [
            str(script),
            "send",
            "--as",
            "planner-main",
            "--to",
            "implementer-feature-a",
            "Default bus shared message.",
        ],
        cwd=repo_a,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert send.returncode == 0, send.stderr
    message_id = _field(send.stdout, "message")

    next_result = subprocess.run(
        [
            str(script),
            "next",
            "--as",
            "implementer-feature-a",
        ],
        cwd=repo_b,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert next_result.returncode == 0, next_result.stderr
    assert message_id in next_result.stdout
    assert "Default bus shared message." in next_result.stdout
    assert resolve_bus_path(None, None, repo_a) == resolve_bus_path(None, None, repo_b)


def test_send_wait_ignores_unrelated_existing_inbox_message(run_cli, temp_bus):
    unrelated = run_cli(
        "--bus",
        str(temp_bus),
        "send",
        "--as",
        "other-agent",
        "--to",
        "planner-main",
        "--title",
        "Existing unrelated",
        "Do not satisfy send wait.",
    )
    assert unrelated.returncode == 0, unrelated.stderr
    unrelated_id = _field(unrelated.stdout, "message")

    waiting = run_cli(
        "--bus",
        str(temp_bus),
        "send",
        "--as",
        "planner-main",
        "--to",
        "implementer-feature-a",
        "--wait",
        "--timeout",
        "0",
        "Please reply to this message.",
    )

    assert waiting.returncode != 0
    assert "timed out waiting for reply" in waiting.stderr
    assert unrelated_id not in waiting.stdout


def _field(output: str, name: str) -> str:
    prefix = f"{name}: "
    for line in output.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix)
    raise AssertionError(f"missing {name!r} field in output: {output!r}")


def _acked_at(bus_path: Path, message_id: str) -> str | None:
    with sqlite3.connect(bus_path) as db:
        return db.execute(
            "select acked_at from messages where id = ?", (message_id,)
        ).fetchone()[0]


def _row(bus_path: Path, table: str, record_id: str) -> sqlite3.Row:
    id_column = "id"
    with sqlite3.connect(bus_path) as db:
        db.row_factory = sqlite3.Row
        row = db.execute(
            f"select * from {table} where {id_column} = ?",
            (record_id,),
        ).fetchone()
    assert row is not None
    return row


def _count_rows(bus_path: Path, table: str) -> int:
    with sqlite3.connect(bus_path) as db:
        return db.execute(f"select count(*) from {table}").fetchone()[0]
