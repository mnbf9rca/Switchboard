# agent-comm CLI v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the stateless high-level `agent-comm` v2 CLI from `docs/superpowers/specs/2026-06-29-agent-comm-cli-v2.md`.

**Architecture:** Keep the existing low-level storage commands compatible, and add a high-level CLI layer that composes existing repository operations. Project identity is derived in `agent_comm.paths`; CLI commands auto-open/create the bus; `send`, `reply`, and `next` provide the normal agent-facing workflow.

**Tech Stack:** Python 3.12 stdlib, SQLite, argparse, pytest.

---

## File Structure

- Modify `agent_comm/paths.py`: derive default bus paths from git origin, git common dir, or cwd; keep explicit `--bus` and `AGENT_COMM_BUS` overrides.
- Modify `agent_comm/repository.py`: add small query/helper methods for next unread message and reply links if the CLI needs them.
- Modify `agent_comm/cli.py`: add v2 commands and shared helpers for body input, auto-init, auto-register, artifact attachment, reply auto-ack, and `--as` aliases.
- Modify `tests/test_paths.py`: behavioral tests for project-key derivation.
- Modify `tests/test_cli_mailbox.py`: behavioral tests for v2 send/reply/read semantics.
- Modify `skills/coordinate-as-planner/SKILL.md`, `skills/coordinate-as-implementer/SKILL.md`, and both protocol reference copies after the CLI tests pass.
- Do not implement `--local` in this v2 pass. The spec allows it as a future explicit experiment flag; the normal CLI must use the derived shared bus and must not silently fall back to a repo-local mailbox.
- Regenerate ignored local plugin bundle with `python3 scripts/build_codex_plugin.py` after skill updates.

## Task 1: Default Project Identity

**Files:**
- Modify: `agent_comm/paths.py`
- Test: `tests/test_paths.py`

- [ ] **Step 1: Replace the no-git failure test with cwd fallback behavior**

In `tests/test_paths.py`, replace `test_missing_project_outside_git_fails` with:

```python
def test_missing_project_outside_git_uses_absolute_cwd(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    workdir = tmp_path / "plain-project"
    workdir.mkdir()

    path = resolve_bus_path(bus=None, project=None, cwd=workdir)

    assert path.parent.parent == home / ".agent-comm" / "projects"
    assert path.parent.name.startswith("plain-project-")
    assert len(path.parent.name.rsplit("-", 1)[-1]) == 12
    assert path.name == "bus.sqlite"
```

- [ ] **Step 2: Add git common-dir fallback test**

Add this test to `tests/test_paths.py`:

```python
def test_linked_worktrees_without_origin_share_common_dir_bus(
    make_git_repo, tmp_path, monkeypatch
):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    main = make_git_repo("main")
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=main, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=main, check=True)
    (main / "README.md").write_text("# Main\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=main, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=main, check=True)
    linked = tmp_path / "linked"
    subprocess.run(
        ["git", "-C", str(main), "worktree", "add", str(linked)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert resolve_bus_path(None, None, main) == resolve_bus_path(None, None, linked)
```

Make sure `tests/test_paths.py` imports `subprocess`:

```python
import subprocess
```

- [ ] **Step 3: Keep git-unavailable fallback explicit**

Replace `test_git_unavailable_falls_through_to_bus_resolution_error` with:

```python
def test_git_unavailable_uses_absolute_cwd(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    def raise_missing_git(*_args, **_kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr("agent_comm.paths.subprocess.run", raise_missing_git)

    path = resolve_bus_path(bus=None, project=None, cwd=tmp_path)

    assert path.parent.parent == tmp_path / "home" / ".agent-comm" / "projects"
    assert path.name == "bus.sqlite"
```

- [ ] **Step 4: Run path tests and verify red**

Run:

```bash
uv run --python 3.12 pytest tests/test_paths.py -q
```

Expected before implementation: failures showing `BusResolutionError` outside git and different paths for linked worktrees without origin.

- [ ] **Step 5: Implement path derivation helpers**

In `agent_comm/paths.py`, add the common-dir fallback with a submodule guard:

```python
def derived_project_source(cwd: str | os.PathLike[str] | None = None) -> str:
    base = Path(cwd) if cwd is not None else Path.cwd()
    origin = _git_origin(base)
    if origin is not None:
        return canonical_origin(origin)

    common_dir = _git_common_dir(base)
    if common_dir is not None:
        return f"git-common-dir:{common_dir}"

    return f"cwd:{base.resolve()}"


def _git_common_dir(cwd: Path) -> str | None:
    if _git_superproject(cwd) is not None:
        return None
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(cwd),
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    common_dir = result.stdout.strip()
    return common_dir or None


def _git_superproject(cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-superproject-working-tree"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    superproject = result.stdout.strip()
    return superproject or None
```

Update `resolve_bus_path` so the no-project path uses `derived_project_source`:

```python
    if project:
        return _default_bus_path(project)

    return _default_bus_path(derived_project_source(cwd))
```

- [ ] **Step 6: Run path tests and verify green**

Run:

```bash
uv run --python 3.12 pytest tests/test_paths.py -q
```

Expected after implementation: all `tests/test_paths.py` tests pass.

- [ ] **Step 7: Commit Task 1**

Run:

```bash
git add agent_comm/paths.py tests/test_paths.py
git commit -m "Derive agent-comm project identity"
```

## Task 2: High-Level `send`

**Files:**
- Modify: `agent_comm/cli.py`
- Test: `tests/test_cli_mailbox.py`

- [ ] **Step 1: Add helpers to inspect SQLite records in CLI tests**

In `tests/test_cli_mailbox.py`, add these helpers near `_acked_at`:

```python
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
```

- [ ] **Step 2: Add failing test for inline `send` auto-setup**

Add this test to `tests/test_cli_mailbox.py`:

```python
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
```

- [ ] **Step 3: Add failing body-source validation test**

Add:

```python
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
```

- [ ] **Step 4: Add failing file/stdin/artifact/thread continuation tests**

Add:

```python
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
```

- [ ] **Step 5: Add failing normal no-`--bus`, no-`--project` CLI test**

Add this import to `tests/test_cli_mailbox.py`:

```python
from agent_comm.paths import resolve_bus_path
```

Add this test:

```python
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
```

- [ ] **Step 6: Add failing visible auto-register repeat test**

Add:

```python
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
```

- [ ] **Step 7: Run focused send tests and verify red**

Run:

```bash
uv run --python 3.12 pytest tests/test_cli_mailbox.py -q
```

Expected before implementation: argparse reports `invalid choice: 'send'`.

- [ ] **Step 8: Add parser support for `send`**

In `agent_comm/cli.py`, add `"send"` to `COMMANDS`, and in `build_parser` add:

```python
        elif command == "send":
            subparser.add_argument("--as", dest="as_agent", required=True)
            subparser.add_argument("--to", required=True)
            subparser.add_argument("--title")
            subparser.add_argument("--in-thread")
            subparser.add_argument("--artifact", action="append", default=[])
            subparser.add_argument("--body-file")
            subparser.add_argument("--stdin", action="store_true")
            subparser.add_argument("--wait", action="store_true")
            subparser.add_argument("--timeout", type=float, help=argparse.SUPPRESS)
            subparser.add_argument("message", nargs="*")
            subparser.set_defaults(handler=_handle_send)
```

- [ ] **Step 9: Add shared body and repo initialization helpers**

In `agent_comm/cli.py`, add:

```python
def _repo_create(args: argparse.Namespace) -> Repository:
    path = _bus_path(args)
    project_id = path.parent.name
    with initialize_bus(path, project_id):
        pass
    return Repository(path)


def _read_body(args: argparse.Namespace) -> str:
    body_sources = int(bool(args.message)) + int(bool(args.body_file)) + int(bool(args.stdin))
    if body_sources != 1:
        raise ValueError("send/reply requires exactly one body source")
    if args.body_file:
        return Path(args.body_file).read_bytes().decode("utf-8")
    if args.stdin:
        return sys.stdin.read()
    return " ".join(args.message)


def _ensure_agent(repo: Repository, agent_id: str) -> bool:
    try:
        repo.get_agent(agent_id)
        created = False
    except ValueError:
        created = True
    repo.register_agent(agent_id)
    return created


def _attach_artifacts(
    repo: Repository,
    thread_id: str,
    message_id: str,
    paths: list[str],
) -> list[Artifact]:
    return [
        repo.add_artifact(
            thread_id,
            message_id,
            path,
            None,
            "linked artifact",
        )
        for path in paths
    ]
```

- [ ] **Step 10: Implement `_handle_send`**

In `agent_comm/cli.py`, add:

```python
def _handle_send(args: argparse.Namespace) -> int:
    try:
        body = _read_body(args)
        repo = _repo_create(args)
        created_agents = [
            agent_id
            for agent_id in (args.as_agent, args.to)
            if _ensure_agent(repo, agent_id)
        ]
        if args.in_thread:
            thread = repo.get_thread(args.in_thread)
        else:
            title = args.title or _derive_title(body)
            thread = repo.start_thread(title, _bus_path(args).parent.name)
        message = repo.post_message(
            thread.id,
            args.as_agent,
            args.to,
            args.title or thread.title,
            body,
        )
        artifacts = _attach_artifacts(repo, thread.id, message.id, args.artifact)
    except (OSError, UnicodeDecodeError) as exc:
        return _print_error(exc)
    except _CLI_ERRORS as exc:
        return _print_error(exc)

    _print_message(message, include_body=False)
    for agent_id in created_agents:
        print(f"agent_created: {agent_id}")
    for artifact in artifacts:
        _print_artifact(artifact)
    if args.wait:
        return _wait_for_reply_to_message(
            repo,
            waiting_agent=args.as_agent,
            thread_id=message.thread_id,
            after_seq=message.seq,
            timeout=args.timeout,
        )
    return 0


def _derive_title(body: str) -> str:
    first_line = body.strip().splitlines()[0] if body.strip() else "Message"
    return first_line[:80] or "Message"
```

- [ ] **Step 11: Add reply-specific wait helper**

Add this helper to `agent_comm/cli.py`:

```python
def _wait_for_reply_to_message(
    repo: Repository,
    *,
    waiting_agent: str,
    thread_id: str,
    after_seq: int,
    timeout: float | None,
) -> int:
    print(f"waiting_for_reply_in_thread: {thread_id}")
    print("interrupt: press Ctrl-C to stop waiting")
    deadline = None if timeout is None else time.monotonic() + timeout
    while True:
        messages = [
            message
            for message in repo.inbox(waiting_agent)
            if message.thread_id == thread_id and message.seq > after_seq
        ]
        if messages:
            _print_messages(messages, include_body=False)
            return 0
        if deadline is not None and time.monotonic() >= deadline:
            print("ERROR: timed out waiting for reply", file=sys.stderr)
            return 1
        sleep_for = POLL_INTERVAL_SECONDS
        if deadline is not None:
            sleep_for = min(POLL_INTERVAL_SECONDS, max(0.0, deadline - time.monotonic()))
        time.sleep(sleep_for)
```

- [ ] **Step 12: Run focused send tests and verify green**

Run:

```bash
uv run --python 3.12 pytest tests/test_cli_mailbox.py -q
```

Expected after implementation: all existing mailbox tests and new send tests pass.

- [ ] **Step 13: Commit Task 2**

Run:

```bash
git add agent_comm/cli.py tests/test_cli_mailbox.py
git commit -m "Add high-level agent-comm send"
```

## Task 3: `reply`, `next`, and `--as` Read Aliases

**Files:**
- Modify: `agent_comm/cli.py`
- Modify if needed: `agent_comm/repository.py`
- Test: `tests/test_cli_mailbox.py`

- [ ] **Step 1: Add failing reply behavior test**

Add this test to `tests/test_cli_mailbox.py`:

```python
def test_reply_uses_original_thread_recipient_and_auto_acks(run_cli, temp_bus):
    first = run_cli(
        "--bus",
        str(temp_bus),
        "send",
        "--as",
        "planner-main",
        "--to",
        "implementer-feature-a",
        "Please acknowledge.",
    )
    assert first.returncode == 0, first.stderr
    original_id = _field(first.stdout, "message")
    thread_id = _field(first.stdout, "thread")

    reply = run_cli(
        "--bus",
        str(temp_bus),
        "reply",
        original_id,
        "--as",
        "implementer-feature-a",
        "Received.",
    )

    assert reply.returncode == 0, reply.stderr
    reply_id = _field(reply.stdout, "message")
    assert _field(reply.stdout, "thread") == thread_id

    row = _row(temp_bus, "messages", reply_id)
    assert row["from_agent"] == "implementer-feature-a"
    assert row["to_agent"] == "planner-main"
    assert row["thread_id"] == thread_id
    assert row["body_md"] == "Received."
    assert _acked_at(temp_bus, original_id) is not None

    with sqlite3.connect(temp_bus) as db:
        links = db.execute(
            "select message_id, reply_to_message_id from message_replies"
        ).fetchall()
    assert links == [(reply_id, original_id)]
```

- [ ] **Step 2: Add failing parser test proving reply has no `--to`**

Add:

```python
def test_reply_rejects_to_override(run_cli, temp_bus):
    first = run_cli(
        "--bus",
        str(temp_bus),
        "send",
        "--as",
        "planner-main",
        "--to",
        "implementer-feature-a",
        "Please acknowledge.",
    )
    original_id = _field(first.stdout, "message")

    result = run_cli(
        "--bus",
        str(temp_bus),
        "reply",
        original_id,
        "--as",
        "implementer-feature-a",
        "--to",
        "other-agent",
        "Received.",
    )

    assert result.returncode != 0
    assert result.stderr
    assert _count_rows(temp_bus, "message_replies") == 0
```

- [ ] **Step 3: Add failing recipient-only reply test**

Add:

```python
def test_reply_rejects_non_recipient_agent(run_cli, temp_bus):
    first = run_cli(
        "--bus",
        str(temp_bus),
        "send",
        "--as",
        "planner-main",
        "--to",
        "implementer-feature-a",
        "Please acknowledge.",
    )
    original_id = _field(first.stdout, "message")

    result = run_cli(
        "--bus",
        str(temp_bus),
        "reply",
        original_id,
        "--as",
        "implementer-typo",
        "Received.",
    )

    assert result.returncode != 0
    assert "recipient" in result.stderr.lower()
    assert _acked_at(temp_bus, original_id) is None
    assert _count_rows(temp_bus, "message_replies") == 0
```

- [ ] **Step 4: Add failing `next` and explicit `ack` behavior test**

Add:

```python
def test_next_shows_body_without_ack_and_ack_is_explicit(run_cli, temp_bus):
    first = run_cli(
        "--bus",
        str(temp_bus),
        "send",
        "--as",
        "planner-main",
        "--to",
        "implementer-feature-a",
        "Please read this.",
    )
    message_id = _field(first.stdout, "message")

    next_message = run_cli(
        "--bus",
        str(temp_bus),
        "next",
        "--as",
        "implementer-feature-a",
    )
    assert next_message.returncode == 0, next_message.stderr
    assert message_id in next_message.stdout
    assert "Please read this." in next_message.stdout
    assert _acked_at(temp_bus, message_id) is None

    show = run_cli("--bus", str(temp_bus), "show", message_id)
    assert show.returncode == 0
    assert _acked_at(temp_bus, message_id) is None

    ack = run_cli(
        "--bus",
        str(temp_bus),
        "ack",
        "--as",
        "implementer-feature-a",
        message_id,
    )
    assert ack.returncode == 0, ack.stderr
    assert _acked_at(temp_bus, message_id) is not None
```

- [ ] **Step 5: Add failing inbox/wait `--as` alias and auto-init test**

Add:

```python
def test_inbox_and_wait_accept_as_alias(run_cli, temp_bus):
    first = run_cli(
        "--bus",
        str(temp_bus),
        "send",
        "--as",
        "planner-main",
        "--to",
        "implementer-feature-a",
        "Please read this.",
    )
    message_id = _field(first.stdout, "message")

    inbox = run_cli("--bus", str(temp_bus), "inbox", "--as", "implementer-feature-a")
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
```

Add:

```python
def test_high_level_read_commands_auto_initialize_empty_bus(run_cli, temp_bus):
    inbox = run_cli("--bus", str(temp_bus), "inbox", "--as", "implementer-feature-a")
    assert inbox.returncode == 0, inbox.stderr
    assert inbox.stdout == ""
    assert temp_bus.exists()

    next_message = run_cli("--bus", str(temp_bus), "next", "--as", "implementer-feature-a")
    assert next_message.returncode == 0, next_message.stderr
    assert next_message.stdout == ""

    wait = run_cli(
        "--bus",
        str(temp_bus),
        "wait",
        "--as",
        "implementer-feature-a",
        "--timeout",
        "0",
    )
    assert wait.returncode != 0
    assert "timed out" in wait.stderr
```

- [ ] **Step 6: Add failing no-`--bus` two-worktree CLI test**

Add:

```python
def test_send_and_next_share_default_bus_across_worktrees(
    make_git_repo, tmp_path, monkeypatch, cli_env
):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    main = make_git_repo("main")
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=main, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=main, check=True)
    (main / "README.md").write_text("# Main\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=main, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=main, check=True)
    linked = tmp_path / "linked"
    subprocess.run(
        ["git", "-C", str(main), "worktree", "add", str(linked)],
        check=True,
        capture_output=True,
        text=True,
    )
    script = _agent_comm_script(Path(sys.executable))
    env = {**cli_env, "HOME": str(tmp_path / "home")}

    send = subprocess.run(
        [
            str(script),
            "send",
            "--as",
            "planner-main",
            "--to",
            "implementer-linked",
            "Cross-worktree message.",
        ],
        cwd=main,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert send.returncode == 0, send.stderr
    message_id = _field(send.stdout, "message")

    next_message = subprocess.run(
        [str(script), "next", "--as", "implementer-linked"],
        cwd=linked,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert next_message.returncode == 0, next_message.stderr
    assert message_id in next_message.stdout
    assert "Cross-worktree message." in next_message.stdout
```

- [ ] **Step 7: Add failing `send --wait` ignores unrelated inbox test**

Add:

```python
def test_send_wait_ignores_unrelated_existing_inbox_message(run_cli, temp_bus):
    unrelated = run_cli(
        "--bus",
        str(temp_bus),
        "send",
        "--as",
        "other-agent",
        "--to",
        "planner-main",
        "Unrelated stale message.",
    )
    assert unrelated.returncode == 0, unrelated.stderr

    result = run_cli(
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
        "Please reply to this.",
    )

    assert result.returncode != 0
    assert "timed out waiting for reply" in result.stderr
    assert "Unrelated stale message." not in result.stdout
```

- [ ] **Step 8: Run focused tests and verify red**

Run:

```bash
uv run --python 3.12 pytest tests/test_cli_mailbox.py -q
```

Expected before implementation: `invalid choice: 'reply'` and `invalid choice: 'next'`, `--as` not accepted by existing `ack`/`inbox`/`wait`, and no-`--bus` worktree behavior missing.

- [ ] **Step 9: Add parser support**

In `agent_comm/cli.py`, add `"reply"` and `"next"` to `COMMANDS`.

For `inbox`, `ack`, and `wait`, accept both old and new flags:

```python
subparser.add_argument("--agent", dest="agent")
subparser.add_argument("--as", dest="as_agent")
```

For `reply`:

```python
        elif command == "reply":
            subparser.add_argument("message_id")
            subparser.add_argument("--as", dest="as_agent", required=True)
            subparser.add_argument("--artifact", action="append", default=[])
            subparser.add_argument("--body-file")
            subparser.add_argument("--stdin", action="store_true")
            subparser.add_argument("--wait", action="store_true")
            subparser.add_argument("--timeout", type=float, help=argparse.SUPPRESS)
            subparser.add_argument("message", nargs="*")
            subparser.set_defaults(handler=_handle_reply)
```

For `next`:

```python
        elif command == "next":
            subparser.add_argument("--as", dest="as_agent", required=True)
            subparser.set_defaults(handler=_handle_next)
```

- [ ] **Step 10: Add an agent-id helper and high-level repo helper**

In `agent_comm/cli.py`, add:

```python
def _agent_arg(args: argparse.Namespace) -> str:
    agent = getattr(args, "as_agent", None) or getattr(args, "agent", None)
    if not agent:
        raise ValueError("--as or --agent is required")
    return agent
```

Update `_handle_inbox`, `_handle_ack`, and `_handle_wait` to call `_agent_arg(args)`.

High-level read commands should use `_repo_create(args)` so a fresh mailbox opens
cleanly. Keep `_repo(args)` for low-level and diagnostic commands that should not
create missing buses.

- [ ] **Step 11: Implement `_handle_reply`**

In `agent_comm/cli.py`, add:

```python
def _handle_reply(args: argparse.Namespace) -> int:
    try:
        body = _read_body(args)
        repo = _repo_create(args)
        original = repo.get_message(args.message_id)
        if original.to_agent != args.as_agent:
            raise PermissionError("only the message recipient can reply")
        _ensure_agent(repo, args.as_agent)
        message = repo.post_message(
            original.thread_id,
            args.as_agent,
            original.from_agent,
            f"Re: {original.subject}",
            body,
            reply_to=[original.id],
        )
        acked = None
        if original.to_agent == args.as_agent:
            acked = repo.ack_message(original.id, args.as_agent)
        artifacts = _attach_artifacts(repo, original.thread_id, message.id, args.artifact)
    except (OSError, UnicodeDecodeError) as exc:
        return _print_error(exc)
    except _CLI_ERRORS as exc:
        return _print_error(exc)

    _print_message(message, include_body=False)
    if acked is not None:
        print(f"acked: {acked.id}")
    for artifact in artifacts:
        _print_artifact(artifact)
    if args.wait:
        return _wait_for_reply_to_message(
            repo,
            waiting_agent=args.as_agent,
            thread_id=message.thread_id,
            after_seq=message.seq,
            timeout=args.timeout,
        )
    return 0
```

- [ ] **Step 12: Implement `_handle_next`**

In `agent_comm/cli.py`, add:

```python
def _handle_next(args: argparse.Namespace) -> int:
    try:
        messages = _repo_create(args).inbox(args.as_agent)
    except _CLI_ERRORS as exc:
        return _print_error(exc)
    if not messages:
        return 0
    _print_message(messages[0], include_body=True)
    return 0
```

- [ ] **Step 13: Run focused tests and verify green**

Run:

```bash
uv run --python 3.12 pytest tests/test_cli_mailbox.py -q
```

Expected after implementation: all mailbox tests pass.

- [ ] **Step 14: Commit Task 3**

Run:

```bash
git add agent_comm/cli.py tests/test_cli_mailbox.py
git commit -m "Add agent-comm reply and read aliases"
```

## Task 4: Skill and Protocol Update

**Files:**
- Modify: `skills/coordinate-as-planner/SKILL.md`
- Modify: `skills/coordinate-as-implementer/SKILL.md`
- Modify: `skills/coordinate-as-planner/references/agent-communication-protocol.md`
- Modify: `skills/coordinate-as-implementer/references/agent-communication-protocol.md`
- Test: `tests/test_skills_manifests_examples.py`

- [ ] **Step 1: Update skill/protocol expectations**

In `tests/test_skills_manifests_examples.py`, update protocol expectations so the command appendix must include:

```python
for guidance in (
    "agent-comm send --as",
    "agent-comm reply <message-id> --as",
    "agent-comm next --as",
    "Use ack explicitly when you read without replying",
):
    assert guidance in protocol
```

Also add assertions that the command appendix does not teach old happy-path commands:

```python
for old_command in (
    "agent-comm register",
    "agent-comm start-thread",
    "agent-comm post",
    "--body-file <path>",
):
    assert old_command not in command_appendix
```

Add assertions that both role skills teach the behavioral protocol, not just command syntax:

```python
planner_skill = (ROOT / "skills" / "coordinate-as-planner" / "SKILL.md").read_text()
implementer_skill = (ROOT / "skills" / "coordinate-as-implementer" / "SKILL.md").read_text()

for required in (
    "Do not inspect CLI help before using the normal workflow",
    "include role and worktree",
    "ask the user before using a repo-local mailbox",
):
    assert required in planner_skill
    assert required in implementer_skill

for required in (
    "Use `--artifact PATH` only when durable project context belongs in a file",
    "Use `--wait` only when blocked on the reply",
):
    assert required in planner_skill

for required in (
    "reply automatically acknowledges",
    "Use `agent-comm ack --as",
):
    assert required in implementer_skill
```

- [ ] **Step 2: Run focused skill tests and verify red**

Run:

```bash
uv run --python 3.12 pytest tests/test_skills_manifests_examples.py -q
```

Expected before doc updates: failures showing old command appendix content.

- [ ] **Step 3: Update planner skill**

In `skills/coordinate-as-planner/SKILL.md`, replace workflow examples that imply low-level setup with v2 commands:

```text
Use `agent-comm send --as <planner-id> --to <agent-id> "message"` for short messages.
Use `--artifact PATH` only when durable project context belongs in a file.
Use `--wait` only when blocked on the reply.
Choose `<planner-id>` to include role and worktree, such as `planner-main`.
Do not inspect CLI help before using the normal workflow; use help only after a command fails.
If the shared user-local mailbox is blocked by sandbox permissions, ask the user before using a repo-local mailbox.
```

- [ ] **Step 4: Update implementer skill**

In `skills/coordinate-as-implementer/SKILL.md`, describe:

```text
Use `agent-comm next --as <implementer-id>` to read the next unread message.
Use `agent-comm reply <message-id> --as <implementer-id> "message"` to answer; reply automatically acknowledges the message.
Use `agent-comm ack --as <implementer-id> <message-id>` only when you read without replying.
Choose `<implementer-id>` to include role and worktree, such as `implementer-feature-a`.
Do not inspect CLI help before using the normal workflow; use help only after a command fails.
If the shared user-local mailbox is blocked by sandbox permissions, ask the user before using a repo-local mailbox.
```

- [ ] **Step 5: Update both protocol reference copies identically**

Replace the command appendix in both protocol references with:

```sh
agent-comm send --as <sender-id> --to <recipient-id> "short message"
agent-comm send --as <sender-id> --to <recipient-id> --title "<title>" "short message"
agent-comm send --as <sender-id> --to <recipient-id> --artifact <path> "short message"
agent-comm send --as <sender-id> --to <recipient-id> --in-thread <thread-id> "short message"
agent-comm reply <message-id> --as <sender-id> "short reply"
agent-comm next --as <agent-id>
agent-comm inbox --as <agent-id>
agent-comm show <message-id>
agent-comm ack --as <agent-id> <message-id>
agent-comm wait --as <agent-id>
agent-comm wait --as <agent-id> --follow
```

Keep the prose rule:

```text
Use ack explicitly when you read without replying. Reply automatically acknowledges the message being answered.
Normal use does not require `--project` or `--bus`; the CLI derives a shared project mailbox.
If sandbox permissions block that shared mailbox, ask the user before using a repo-local mailbox.
Each agent identity should include role and worktree when multiple worktrees are active, such as `planner-main` or `implementer-feature-a`.
Do not inspect CLI help before using this normal workflow; use help only after a command fails.
```

- [ ] **Step 6: Run protocol and skill tests**

Run:

```bash
uv run --python 3.12 python scripts/validate_skill_protocols.py
uv run --python 3.12 pytest tests/test_skills_manifests_examples.py -q
```

Expected after doc updates: protocol validation passes and skill tests pass.

- [ ] **Step 7: Rebuild and validate plugin bundle**

Run:

```bash
python3 scripts/build_codex_plugin.py
python3 /Users/rob/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/agents-together
```

Expected: plugin validation passes.

- [ ] **Step 8: Install the local Codex plugin and verify cache freshness**

Run:

```bash
INSTALL_JSON=$(codex plugin add agents-together@agents-together-local --json)
INSTALLED_PATH=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["installedPath"])' <<<"$INSTALL_JSON")
test -x "$INSTALLED_PATH/scripts/agent-comm"
"$INSTALLED_PATH/scripts/agent-comm" --version
sed -n '1,160p' "$INSTALLED_PATH/skills/coordinate-as-planner/SKILL.md"
sed -n '1,160p' "$INSTALLED_PATH/skills/coordinate-as-implementer/SKILL.md"
```

Expected:

```text
installed plugin version includes the new cachebuster
agent-comm reports the package version
installed skills include `agent-comm send --as`, `agent-comm reply <message-id> --as`, and `agent-comm next --as`
installed skills do not teach `agent-comm register`, `agent-comm start-thread`, or `agent-comm post` as the normal workflow
```

This step writes to the Codex plugin cache outside the repository. In a sandboxed session, request escalation before running it.

- [ ] **Step 9: Commit Task 4**

Run:

```bash
git add skills tests
git commit -m "Teach agent-comm CLI v2 workflow"
```

The v2 spec was already committed before this plan. Do not stage it unless the implementation proves the spec itself is wrong and the user agrees to a spec change.

## Task 5: Final Verification and Smoke

**Files:**
- Modify if needed: `docs/smoke-tests/fresh-agent-sessions.md`
- Test: full suite plus manual CLI smoke

- [ ] **Step 1: Run full automated verification**

Run:

```bash
uv run --python 3.12 pytest -q
uv run --python 3.12 python scripts/validate_skill_protocols.py
python3 /Users/rob/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/agents-together
```

Expected:

```text
all pytest tests pass
Validated 2 skill protocol references
Plugin validation passed
```

Also verify no generated plugin bundle files are accidentally staged:

```bash
git status --short --ignored plugins/agents-together
```

Expected: generated bundle files are ignored or clean; no tracked plugin-cache output is staged.

- [ ] **Step 2: Run local v2 smoke with explicit temporary bus**

Run:

```bash
BUS=$(mktemp -t agent-comm-v2.XXXXXX.sqlite)
agent-comm --bus "$BUS" send --as planner-main --to implementer-feature-a "Please acknowledge this smoke test."
agent-comm --bus "$BUS" next --as implementer-feature-a
agent-comm --bus "$BUS" reply "$(agent-comm --bus "$BUS" inbox --as implementer-feature-a | awk '/^message: / {print $2; exit}')" --as implementer-feature-a "Received."
agent-comm --bus "$BUS" inbox --as planner-main
```

Expected:

```text
send prints message and thread ids
next prints the message body
reply prints a new message id and acked original id
planner inbox includes the reply
```

- [ ] **Step 3: Update smoke docs if commands changed**

If `docs/smoke-tests/fresh-agent-sessions.md` still teaches low-level `register`, `start-thread`, or `post` for the normal flow, replace the normal flow with:

```sh
agent-comm send --as planner-main --to implementer-feature-a --title "Fresh session smoke" "Please acknowledge this handoff and reply that the mailbox round trip works."
agent-comm next --as implementer-feature-a
agent-comm reply <message-id> --as implementer-feature-a "Received. The mailbox round trip works."
agent-comm inbox --as planner-main
```

- [ ] **Step 4: Commit final smoke/docs update**

Run:

```bash
git add docs/smoke-tests/fresh-agent-sessions.md
git commit -m "Update smoke docs for agent-comm CLI v2"
```

Skip this commit if the smoke docs already match v2 and no files changed.

## Self-Review

Spec coverage:

- Stateless commands: covered by `send`, `reply`, `next`, `inbox`, `ack`, and `wait` tests with explicit `--as`.
- No normal `--project` or `--bus`: covered by path derivation tests and skill/protocol updates; behavioral CLI tests still use `--bus` for isolation.
- Project-key derivation: covered by origin, git common dir, and cwd fallback tests.
- Shared worktree mailbox: covered by linked worktree common-dir test.
- Inline/file/stdin bodies: covered by send body-source tests.
- Optional artifacts: covered by send artifact tests.
- Thread rules: covered by send new-thread and `--in-thread` tests.
- Reply rules: covered by reply recipient, reply link, no `--to`, and auto-ack tests.
- Explicit ack: covered by `next`/`show` no-auto-ack and explicit `ack` tests.
- Skills and protocol: covered by protocol byte-identity validator and skill/protocol tests.

Placeholder scan:

- No placeholder markers or incomplete implementation tasks remain.

Type consistency:

- CLI flag names are consistent with the spec: `--as`, `--to`, `--title`, `--in-thread`, `--artifact`, `--body-file`, `--stdin`, `--wait`.
- Existing low-level flags remain compatible: `--agent`, `--project`, `--bus`, `--thread`, `--body-file`.
