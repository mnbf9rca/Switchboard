# Agents Together Implementation Plan

**Goal:** Build the MVP `agent-comm` package and portable skills as a durable local mailbox for independent coding agents.

**Architecture:** Keep the product small: Agent Skills are the user-facing coordination workflow, plugin manifests are thin adapters, and `agent_comm` is a Python 3.12+ CLI backed by one local SQLite database. The bus stores addressed messages, threads, replies, acknowledgements, artifacts, and agent records; it does not interpret workflow state, assign work, infer review lifecycle, or parse structured message headers.

**Tech Stack:** Python 3.12+, stdlib `argparse`, stdlib `sqlite3`, stdlib `hashlib`, stdlib `pathlib`, pytest, `uv` for development only. Runtime commands must work as `agent-comm ...` and `python -m agent_comm ...`.

---

## Non-Negotiable Scope

Build only the simplified mailbox MVP from `docs/superpowers/specs/2026-06-29-agents-together-design.md`.

Do not add:

- Structured `Intent`, `Requested-Action`, or `Thread-State` headers.
- CLI message types, `post --type`, `wait --type`, or `--allow-unstructured`.
- Claim, stale-claim, checkpoint, conflict-precedence, or review-lifecycle machinery.
- `.agent-comm.json`, `.agent-comm.local.json`, an events table, daemon behavior, PR integration, RAG, memory, or workflow category inference.
- Thread lifecycle or assignment fields: no `threads.status`, no `threads.closed_at`, no `threads.owner`, and no owner flag on `start-thread`.
- Artifact classification fields: no `artifacts.kind` and no artifact classification flag.
- Remote override flags; common bus selection options are only `--bus` and `--project`.

## File Structure

- Create `pyproject.toml`: package metadata, Python floor, console script, pytest config.
- Create `README.md`: mailbox purpose, install/runtime commands, development commands, safety notes.
- Create `agent_comm/__init__.py`: package version.
- Create `agent_comm/__main__.py`: `python -m agent_comm` entry point.
- Create `agent_comm/cli.py`: argparse command wiring and human-readable output.
- Create `agent_comm/paths.py`: bus selection, project-key derivation, git `origin` canonicalization.
- Create `agent_comm/db.py`: SQLite connection, schema version 1, WAL setup, short transactions.
- Create `agent_comm/repository.py`: agent, thread, message, reply, artifact, ack, inbox, status queries.
- Create `agent_comm/backup.py`: backup, restore validation, exclusive target handling.
- Create `agent_comm/doctor.py`: core DB health checks only.
- Create `agent_comm/export.py`: Markdown export of stored records, including bodyless/redacted mode.
- Create `tests/conftest.py`: isolated CLI runner and temp bus fixtures.
- Create `tests/test_package_cli.py`: package, help, version, command availability.
- Create `tests/test_paths.py`: bus path resolution and project-key behavior.
- Create `tests/test_db_schema.py`: schema, WAL, permissions, unsupported versions, migrations.
- Create `tests/test_repository.py`: repository-level mailbox behavior.
- Create `tests/test_cli_mailbox.py`: command-level init/register/thread/post/inbox/show/ack/wait/artifact behavior.
- Create `tests/test_backup_doctor_export.py`: backup, restore, doctor, status, export.
- Create `skills/coordinate-as-planner/SKILL.md` and `skills/coordinate-as-planner/references/agent-communication-protocol.md`.
- Create `skills/coordinate-as-implementer/SKILL.md` and `skills/coordinate-as-implementer/references/agent-communication-protocol.md`.
- Create `.codex-plugin/plugin.json` and `.claude-plugin/plugin.json`.
- Create `examples/planner-handoff.md`, `examples/implementer-question.md`, `examples/implementer-blocker.md`, `examples/ready-for-review.md`, `examples/review-findings.md`.
- Create `docs/smoke-tests/fresh-agent-sessions.md`.

## Task 1: Package Scaffold

**Files:**

- Create: `pyproject.toml`
- Create: `README.md`
- Create: `agent_comm/__init__.py`
- Create: `agent_comm/__main__.py`
- Create: `agent_comm/cli.py`
- Create: `tests/conftest.py`
- Create: `tests/test_package_cli.py`

- [ ] **Step 1: RED - package entry points**

Write tests that run the package in a subprocess:

```python
def test_help_and_version_work(run_cli):
    help_result = run_cli("--help")
    version_result = run_cli("--version")
    assert help_result.returncode == 0
    assert "agent-comm" in help_result.stdout
    assert "init" in help_result.stdout
    assert version_result.returncode == 0
    assert "agent-comm 0.1.0" in version_result.stdout


def test_python_module_entrypoint_matches_cli(run_cli):
    result = run_cli("--help")
    assert result.returncode == 0
    assert "durable local mailbox" in result.stdout.lower()
```

Run: `uv run pytest tests/test_package_cli.py -v`

Expected: FAIL because `agent_comm` does not exist.

- [ ] **Step 2: GREEN - minimal package**

Add package metadata with `requires-python = ">=3.12"`, console script `agent-comm = "agent_comm.cli:main"`, pytest config, `agent_comm.__version__ = "0.1.0"`, and an argparse skeleton with all MVP command names visible in help:

```text
init doctor backup restore register start-thread post inbox show ack wait artifact status export migrate
```

Document runtime invocation as `agent-comm`, `python3 -m agent_comm`, and `python -m agent_comm`; document `uv run ...` only for development.

Run: `uv run pytest tests/test_package_cli.py -v`

Expected: PASS.

- [ ] **Step 3: REFACTOR - command dispatch shape**

Keep CLI handlers small and side-effect free until later tasks wire storage. Unsupported skeleton handlers may return `ERR_NOT_IMPLEMENTED` only where the spec says so: `migrate`.

Run: `uv run pytest tests/test_package_cli.py -v`

Expected: PASS.

## Task 2: Path Resolution

**Files:**

- Create: `agent_comm/paths.py`
- Modify: `agent_comm/cli.py`
- Create: `tests/test_paths.py`

- [ ] **Step 1: RED - explicit bus, env bus, project, and git origin**

Write tests for bus selection order:

```python
def test_explicit_bus_wins_over_env(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_COMM_BUS", str(tmp_path / "env.sqlite"))
    assert resolve_bus_path(bus=tmp_path / "explicit.sqlite", project=None, cwd=tmp_path).name == "explicit.sqlite"


def test_env_bus_wins_over_project(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_COMM_BUS", str(tmp_path / "env.sqlite"))
    assert resolve_bus_path(bus=None, project="demo", cwd=tmp_path).name == "env.sqlite"


def test_project_uses_default_state_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    path = resolve_bus_path(bus=None, project="Example Project", cwd=tmp_path)
    assert path.parent.parent == tmp_path / ".agent-comm" / "projects"
    assert path.parent.name.startswith("example-project-")
    assert len(path.parent.name.rsplit("-", 1)[-1]) == 12
    assert path.name == "bus.sqlite"


def test_missing_project_outside_git_fails(tmp_path):
    with pytest.raises(BusResolutionError, match="--project or --bus"):
        resolve_bus_path(bus=None, project=None, cwd=tmp_path)
```

Run: `uv run pytest tests/test_paths.py -v`

Expected: FAIL because `agent_comm.paths` does not exist.

- [ ] **Step 2: GREEN - bus selection**

Implement `resolve_bus_path(bus, project, cwd)`, `project_key(value)`, `safe_project_slug(value)`, and `BusResolutionError`. Explicit `--project` values and canonical git origins both use the same safe slug plus 12-character stable hash directory rule. Do not read or write `.agent-comm.json` or `.agent-comm.local.json`.

Run: `uv run pytest tests/test_paths.py -v`

Expected: PASS for explicit, env, project, and outside-git failures.

- [ ] **Step 3: RED - canonical origin and shared worktrees**

Add tests:

```python
def test_origin_canonicalizes_ssh_and_https_forms():
    assert canonical_origin("git@github.com:Example/Repo.git") == canonical_origin("https://github.com/example/repo")


def test_project_key_includes_slug_and_stable_hash():
    key = project_key("https://github.com/example/repo")
    assert key.startswith("github.com-example-repo-")
    assert len(key.rsplit("-", 1)[-1]) == 12


def test_two_worktrees_with_same_origin_share_default_bus(make_git_repo, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo_a = make_git_repo("a", origin="git@github.com:Example/Repo.git")
    repo_b = make_git_repo("b", origin="https://github.com/example/repo.git")
    assert resolve_bus_path(None, None, repo_a) == resolve_bus_path(None, None, repo_b)
```

Run: `uv run pytest tests/test_paths.py -v`

Expected: FAIL on missing git origin support.

- [ ] **Step 4: GREEN - canonical origin support**

Implement canonical origin normalization for common SSH and HTTPS forms, strip trailing `.git`, normalize host case, and include a 12-character stable hash in origin-derived project keys. Do not add a CLI remote override option.

Run: `uv run pytest tests/test_paths.py -v`

Expected: PASS.

## Task 3: DB Schema, WAL, Versioning, and Permissions

**Files:**

- Create: `agent_comm/db.py`
- Modify: `agent_comm/cli.py`
- Create: `tests/test_db_schema.py`

- [ ] **Step 1: RED - init creates private schema version 1**

Write tests:

```python
def test_init_creates_schema_version_one_and_tables(run_cli, temp_bus):
    result = run_cli("--bus", str(temp_bus), "init", "--project", "demo")
    assert result.returncode == 0
    with sqlite3.connect(temp_bus) as db:
        assert db.execute("pragma user_version").fetchone()[0] == 1
        tables = {row[0] for row in db.execute("select name from sqlite_master where type='table'")}
    assert {"agents", "threads", "messages", "message_replies", "artifacts"} <= tables
    thread_columns = {row[1] for row in db.execute("pragma table_info(threads)")}
    artifact_columns = {row[1] for row in db.execute("pragma table_info(artifacts)")}
    assert {"status", "closed_at", "owner"}.isdisjoint(thread_columns)
    assert "kind" not in artifact_columns


def test_init_uses_private_posix_permissions(run_cli, temp_bus):
    result = run_cli("--bus", str(temp_bus), "init", "--project", "demo")
    assert result.returncode == 0
    if os.name == "posix":
        assert stat.S_IMODE(temp_bus.parent.stat().st_mode) == 0o700
        assert stat.S_IMODE(temp_bus.stat().st_mode) == 0o600
```

Run: `uv run pytest tests/test_db_schema.py -v`

Expected: FAIL because `init` does not create a database.

- [ ] **Step 2: GREEN - schema creation**

Implement `open_bus(path)`, `initialize_bus(path, project_id)`, user-private directory/file creation where supported, and schema version 1 exactly as specified:

```text
agents, threads, messages, message_replies, artifacts
```

Do not create an `events` table or any workflow-state tables.

Run: `uv run pytest tests/test_db_schema.py -v`

Expected: PASS for schema and permissions.

- [ ] **Step 3: RED - WAL, busy timeout, supported version checks**

Add tests:

```python
def test_wal_and_busy_timeout_enabled(run_cli, temp_bus):
    assert run_cli("--bus", str(temp_bus), "init", "--project", "demo").returncode == 0
    with sqlite3.connect(temp_bus) as db:
        assert db.execute("pragma journal_mode").fetchone()[0].lower() == "wal"
        assert db.execute("pragma busy_timeout").fetchone()[0] >= 1000


def test_newer_schema_version_fails_clearly(run_cli, temp_bus):
    assert run_cli("--bus", str(temp_bus), "init", "--project", "demo").returncode == 0
    with sqlite3.connect(temp_bus) as db:
        db.execute("pragma user_version = 99")
    result = run_cli("--bus", str(temp_bus), "doctor")
    assert result.returncode != 0
    assert "unsupported schema version" in result.stderr.lower()


def test_migrate_returns_not_implemented(run_cli, temp_bus):
    result = run_cli("--bus", str(temp_bus), "migrate")
    assert result.returncode != 0
    assert "ERR_NOT_IMPLEMENTED" in result.stderr
```

Run: `uv run pytest tests/test_db_schema.py -v`

Expected: FAIL until WAL/version checks are implemented.

- [ ] **Step 4: GREEN - connection policy**

Enable WAL, set nonzero busy timeout such as 5000 ms, verify WAL activation, reject schema versions newer than supported, and implement `migrate` as `ERR_NOT_IMPLEMENTED`.

Run: `uv run pytest tests/test_db_schema.py -v`

Expected: PASS.

## Task 4: Repository Operations

**Files:**

- Create: `agent_comm/repository.py`
- Modify: `agent_comm/db.py`
- Create: `tests/test_repository.py`

- [ ] **Step 1: RED - agents and threads**

Write repository tests:

```python
def test_register_upserts_agent_and_last_seen(bus):
    repo = Repository(bus)
    repo.register_agent("implementer:codex:abc", role="implementer", harness="codex")
    repo.register_agent("implementer:codex:abc", role="implementer", harness="codex")
    agent = repo.get_agent("implementer:codex:abc")
    assert agent.role == "implementer"
    assert agent.harness == "codex"
    assert agent.last_seen_at is not None


def test_start_thread_creates_thread(bus):
    repo = Repository(bus)
    thread = repo.start_thread(title="Issue #304 adaptive limiter", project_id="demo")
    assert thread.title == "Issue #304 adaptive limiter"
    assert thread.project_id == "demo"
```

Run: `uv run pytest tests/test_repository.py -v`

Expected: FAIL because repository operations do not exist.

- [ ] **Step 2: GREEN - agents and threads**

Implement dataclass-like return objects or dictionaries for agents and threads. Use UTC ISO-8601 timestamps. Threads have no owner, status, closed timestamp, or lifecycle behavior.

Run: `uv run pytest tests/test_repository.py -v`

Expected: PASS for agents and threads.

- [ ] **Step 3: RED - messages, replies, ack, artifacts**

Add tests:

```python
def test_post_assigns_per_thread_sequence_and_stores_body_as_is(bus):
    repo = Repository(bus)
    thread = repo.start_thread("Title", "demo")
    msg1 = repo.post_message(thread.id, "planner", "implementer", "Handoff", "Requested action: read this.\n\nBody")
    msg2 = repo.post_message(thread.id, "implementer", "planner", "Question", "No structured headers here.")
    assert msg1.seq == 1
    assert msg2.seq == 2
    assert repo.get_message(msg2.id).body_md == "No structured headers here."


def test_reply_targets_must_be_in_same_thread(bus):
    repo = Repository(bus)
    one = repo.start_thread("One", "demo")
    two = repo.start_thread("Two", "demo")
    original = repo.post_message(one.id, "planner", "implementer", "A", "body")
    with pytest.raises(ValueError, match="same thread"):
        repo.post_message(two.id, "implementer", "planner", "B", "body", reply_to=[original.id])


def test_ack_only_recipient_can_ack(bus):
    repo = Repository(bus)
    thread = repo.start_thread("Title", "demo")
    msg = repo.post_message(thread.id, "planner", "implementer", "Handoff", "body")
    with pytest.raises(PermissionError):
        repo.ack_message(msg.id, "planner")
    repo.ack_message(msg.id, "implementer")
    assert repo.get_message(msg.id).acked_at is not None


def test_artifact_links_thread_and_optional_message(bus):
    repo = Repository(bus)
    thread = repo.start_thread("Title", "demo")
    msg = repo.post_message(thread.id, "planner", "implementer", "Handoff", "body")
    artifact = repo.add_artifact(thread.id, msg.id, "docs/handoff.md", None, "Approved handoff")
    assert artifact.path == "docs/handoff.md"
```

Run: `uv run pytest tests/test_repository.py -v`

Expected: FAIL until mailbox operations are implemented.

- [ ] **Step 4: GREEN - mailbox records**

Implement immutable message creation, `message_replies`, same-thread validation, recipient-only acknowledgement, artifact links, and inbox queries by `to_agent` plus `acked_at is null`. Assign per-thread `seq` inside `BEGIN IMMEDIATE`.

Run: `uv run pytest tests/test_repository.py -v`

Expected: PASS.

- [ ] **Step 5: RED/GREEN - concurrent posting**

Add a test that posts many messages to one thread from multiple Python threads and asserts sorted sequences are `1..N` without uncaught lock errors.

Run: `uv run pytest tests/test_repository.py::test_concurrent_posts_get_unique_thread_sequences -v`

Expected RED first, then PASS after tightening the transaction around sequence allocation and insert.

## Task 5: CLI Mailbox Commands

**Files:**

- Modify: `agent_comm/cli.py`
- Modify: `agent_comm/repository.py`
- Create: `tests/test_cli_mailbox.py`

- [ ] **Step 1: RED - init, register, start-thread**

Write CLI tests for:

```text
agent-comm --bus <path> init --project demo
agent-comm --bus <path> register --agent implementer --role implementer --harness codex
agent-comm --bus <path> start-thread --project demo --title "Issue #304 adaptive limiter"
```

Assert successful exit, readable output containing created ids where applicable, and persisted records.

Run: `uv run pytest tests/test_cli_mailbox.py::test_init_register_and_start_thread -v`

Expected: FAIL until commands call repository functions.

- [ ] **Step 2: GREEN - init/register/thread commands**

Wire common bus options `--bus` and `--project` where relevant. Do not add a remote override flag. `init --project <project-id>` creates or opens the bus and initializes schema version 1. `start-thread --project <project-id>` stores the thread `project_id`; there is no hidden bus metadata for recovering a project id from a prior `init`.

Run: `uv run pytest tests/test_cli_mailbox.py::test_init_register_and_start_thread -v`

Expected: PASS.

- [ ] **Step 3: RED - post, replies, inbox, show, ack**

Write CLI tests for:

```text
agent-comm post --thread <thread-id> --from planner --to implementer --subject "Implementation handoff ready" --body-file docs/handoff.md
agent-comm post ... --reply-to <message-id> --reply-to <message-id>
agent-comm inbox --agent implementer
agent-comm show <message-id>
agent-comm ack <message-id> --agent implementer
```

Assert message bodies are stored as-is, repeated `--reply-to` values are linked, `inbox` lists only unacknowledged messages for the recipient, `show` prints the full message and linked artifacts, and `ack --agent planner` rejects a message addressed to `implementer`.

Run: `uv run pytest tests/test_cli_mailbox.py::test_post_inbox_show_and_ack -v`

Expected: FAIL until commands are wired.

- [ ] **Step 4: GREEN - message commands**

Implement CLI parsing and output for post, inbox, show, and ack. Do not add `--type`; do not parse body headers; do not reject unstructured Markdown.

Run: `uv run pytest tests/test_cli_mailbox.py::test_post_inbox_show_and_ack -v`

Expected: PASS.

- [ ] **Step 5: RED/GREEN - wait and artifact**

Write then satisfy tests for:

```text
agent-comm wait --agent planner
agent-comm wait --agent planner --follow
agent-comm wait --agent planner -f
agent-comm artifact add --thread <thread-id> --message <message-id> --path docs/handoff.md --description "Approved implementation handoff"
```

Assert `wait` exits after printing at least one unacknowledged message, `--follow` prints newly available unacknowledged messages without auto-acknowledging, and artifact links are available through `show`.

Run: `uv run pytest tests/test_cli_mailbox.py -v`

Expected: PASS.

## Task 6: Backup, Restore, and Doctor

**Files:**

- Create: `agent_comm/backup.py`
- Create: `agent_comm/doctor.py`
- Modify: `agent_comm/cli.py`
- Create: `tests/test_backup_doctor_export.py`

- [ ] **Step 1: RED - backup creates readable copy**

Write test:

```python
def test_backup_uses_readable_sqlite_copy(run_cli, temp_bus, tmp_path):
    run_cli("--bus", str(temp_bus), "init", "--project", "demo", check=True)
    backup = tmp_path / "backup.sqlite"
    result = run_cli("--bus", str(temp_bus), "backup", "--out", str(backup))
    assert result.returncode == 0
    with sqlite3.connect(backup) as db:
        assert db.execute("pragma integrity_check").fetchone()[0] == "ok"
```

Run: `uv run pytest tests/test_backup_doctor_export.py::test_backup_uses_readable_sqlite_copy -v`

Expected: FAIL until backup exists.

- [ ] **Step 2: GREEN - backup API**

Use SQLite's backup API, create private backup files where supported, and leave the source bus untouched.

Run: `uv run pytest tests/test_backup_doctor_export.py::test_backup_uses_readable_sqlite_copy -v`

Expected: PASS.

- [ ] **Step 3: RED - restore validation and active-writer refusal**

Write tests that restore a valid backup, reject a non-SQLite file, and refuse restore when an exclusive lock cannot be acquired on the target bus.

Run: `uv run pytest tests/test_backup_doctor_export.py::test_restore_validates_backup_and_refuses_active_target -v`

Expected: FAIL until restore is implemented.

- [ ] **Step 4: GREEN - restore**

Validate backup integrity and supported schema first. Acquire exclusive access to the target bus, write a replacement temp file, and atomically replace where supported.

Run: `uv run pytest tests/test_backup_doctor_export.py::test_restore_validates_backup_and_refuses_active_target -v`

Expected: PASS.

- [ ] **Step 5: RED/GREEN - doctor core health only**

Write then satisfy tests that `doctor` checks only:

```text
DB opens
schema version supported
integrity_check ok
WAL active
private permissions where supported
```

Assert output does not mention claims, stale work, review state, checkpoints, message categories, or workflow health.

Run: `uv run pytest tests/test_backup_doctor_export.py::test_doctor_reports_core_db_health_only -v`

Expected: PASS.

## Task 7: Status and Export

**Files:**

- Create: `agent_comm/export.py`
- Modify: `agent_comm/cli.py`
- Modify: `agent_comm/repository.py`
- Modify: `tests/test_backup_doctor_export.py`

- [ ] **Step 1: RED - status summarizes stored records**

Write test:

```python
def test_status_shows_thread_messages_replies_unread_and_artifacts(run_cli, populated_bus):
    result = run_cli("--bus", str(populated_bus.path), "status", "--thread", populated_bus.thread_id)
    assert result.returncode == 0
    assert "Thread:" in result.stdout
    assert "Unread:" in result.stdout
    assert "Recent messages:" in result.stdout
    assert "Artifacts:" in result.stdout
    assert "claim" not in result.stdout.lower()
    assert "workflow" not in result.stdout.lower()
```

Run: `uv run pytest tests/test_backup_doctor_export.py::test_status_shows_thread_messages_replies_unread_and_artifacts -v`

Expected: FAIL until status exists.

- [ ] **Step 2: GREEN - status**

Implement status as a read-only direct summary of stored thread metadata, unread messages, recent messages, reply links, and artifacts. Do not infer ownership, completion, acceptance, lifecycle, review state, or categories from body text.

Run: `uv run pytest tests/test_backup_doctor_export.py::test_status_shows_thread_messages_replies_unread_and_artifacts -v`

Expected: PASS.

- [ ] **Step 3: RED - Markdown export with redacted/bodyless mode**

Write tests that `export --thread <id>` writes Markdown under `<bus-dir>/exports/` using temp file plus replace, includes stored records, and `export --thread <id> --redacted` or `--bodyless` omits message bodies while retaining metadata.

Run: `uv run pytest tests/test_backup_doctor_export.py::test_export_writes_markdown_and_bodyless_variant -v`

Expected: FAIL until export exists.

- [ ] **Step 4: GREEN - export**

Render only stored records: thread metadata, messages by `seq`, reply references, acknowledgement timestamps, and artifacts. Use an atomic replace where supported.

Run: `uv run pytest tests/test_backup_doctor_export.py::test_export_writes_markdown_and_bodyless_variant -v`

Expected: PASS.

## Task 8: Skills, Examples, and Plugin Manifests

**Files:**

- Create: `skills/coordinate-as-planner/SKILL.md`
- Create: `skills/coordinate-as-planner/references/agent-communication-protocol.md`
- Create: `skills/coordinate-as-implementer/SKILL.md`
- Create: `skills/coordinate-as-implementer/references/agent-communication-protocol.md`
- Create: `.codex-plugin/plugin.json`
- Create: `.claude-plugin/plugin.json`
- Create: `examples/planner-handoff.md`
- Create: `examples/implementer-question.md`
- Create: `examples/implementer-blocker.md`
- Create: `examples/ready-for-review.md`
- Create: `examples/review-findings.md`
- Create: `tests/test_skills_manifests_examples.py`

- [ ] **Step 1: RED - skill and manifest contract**

Write tests that assert:

```text
each SKILL.md has YAML frontmatter with required name and description
frontmatter name matches parent directory
descriptions are trigger-rich
each skill has its own duplicated references/agent-communication-protocol.md
both plugin manifests contain name/version/description/skills exactly enough to expose ./skills/
```

Run: `uv run pytest tests/test_skills_manifests_examples.py -v`

Expected: FAIL until files exist.

- [ ] **Step 2: GREEN - planner and implementer skills**

Create the two skills with the exact required names and frontmatter descriptions from the spec. The body must explain runtime command discovery in this order:

```text
agent-comm --version
python3 -m agent_comm --version
python -m agent_comm --version
py -3.12 -m agent_comm   # Windows where available
uv run agent-comm        # development checkout only
```

Planner behavior covers selecting/starting a thread, creating project artifacts when useful, posting deliberate addressed messages, reading replies, and not relying on chat history. Implementer behavior covers inbox, show, ack after reading, artifact use, questions/blockers, ready-for-review messages, and stopping for clarification on conflicts.

Run: `uv run pytest tests/test_skills_manifests_examples.py -v`

Expected: PASS for skills and manifests.

- [ ] **Step 3: RED/GREEN - protocol and examples avoid workflow enforcement**

Add tests that scan skills, protocol references, examples, and manifests for stale terms:

```text
post --type
wait --type
allow-unstructured
Intent:
Thread-State:
stale claim
checkpoint
.agent-comm.json
.agent-comm.local.json
events table
```

Then write protocol and example message bodies for planner handoff, implementer question/blocker, ready for review, and review findings. Examples may use prose such as `Requested action: review this plan and reply with blockers only.` inside Markdown bodies, but must not describe CLI-enforced headers.

Run: `uv run pytest tests/test_skills_manifests_examples.py -v`

Expected: PASS.

## Task 9: Smoke Docs

**Files:**

- Create: `docs/smoke-tests/fresh-agent-sessions.md`
- Modify: `README.md`
- Create: `tests/test_docs_smoke.py`

- [ ] **Step 1: RED - smoke doc requirements**

Write docs tests that assert the smoke guide includes:

```text
local Codex install path or marketplace fixture instructions
local Claude plugin path instructions
/agents-together:coordinate-as-planner
/agents-together:coordinate-as-implementer
agent-comm and python -m agent_comm runtime commands
planner posts a handoff with an artifact link
implementer reads, shows, acks, and replies
planner reads the reply
```

Run: `uv run pytest tests/test_docs_smoke.py -v`

Expected: FAIL until docs exist.

- [ ] **Step 2: GREEN - fresh-agent smoke docs**

Write the smoke guide as a concrete manual script for one planner session and one implementer session. Note that local skills-directory installs may use a different Claude namespace. Keep it focused on essential mailbox behavior only.

Run: `uv run pytest tests/test_docs_smoke.py -v`

Expected: PASS.

## Task 10: Final Verification

**Files:**

- Modify only files created or changed by earlier tasks.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/test_package_cli.py tests/test_paths.py tests/test_db_schema.py tests/test_repository.py tests/test_cli_mailbox.py tests/test_backup_doctor_export.py tests/test_skills_manifests_examples.py tests/test_docs_smoke.py -v
```

Expected: PASS.

- [ ] **Step 2: Run complete test suite**

Run:

```bash
uv run pytest
```

Expected: PASS.

- [ ] **Step 3: Verify runtime invocations**

Run:

```bash
uv run agent-comm --version
python -m agent_comm --version
```

Expected: both print `agent-comm 0.1.0`. If `agent-comm` is installed in the active environment, also run `agent-comm --version`.

- [ ] **Step 4: Verify no stale workflow concepts**

Run:

```bash
rg -n "post --type|wait --type|allow-unstructured|Intent:|Thread-State:|stale claim|checkpoint|\\.agent-comm\\.json|\\.agent-comm\\.local\\.json|events table|claim state|review lifecycle" agent_comm tests skills examples README.md docs/smoke-tests
```

Expected: no matches except text in tests that intentionally asserts those terms are absent.

- [ ] **Step 5: Manual smoke test**

Follow `docs/smoke-tests/fresh-agent-sessions.md` with a temporary bus path and two logical agents:

```text
planner
implementer
```

Expected: planner posts a handoff with an artifact link; implementer sees it in inbox, shows it, acknowledges it, replies; planner sees the reply.

- [ ] **Step 6: Commit**

Run:

```bash
git add pyproject.toml README.md agent_comm tests skills examples .codex-plugin .claude-plugin docs/smoke-tests
git commit -m "feat: implement durable agent mailbox"
```

## Residual Risks

- Fresh-agent plugin installation still depends on local Claude Code and Codex behavior outside automated tests.
- `wait --follow` is polling-based in MVP and may need tuning after real multi-agent use.
- WAL is intended for local same-host storage; network filesystem behavior is deliberately not solved in the MVP.
- Message bodies and exports can contain sensitive data, so skills and docs must keep warning agents to prefer artifact links and avoid secrets.
