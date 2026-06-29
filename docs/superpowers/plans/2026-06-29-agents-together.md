# Agents Together Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the MVP `agents-together` plugin-shaped repo with a Python 3.12+ SQLite coordination CLI and two portable Agent Skills.

**Architecture:** Keep the SQLite bus and CLI in a focused `agent_comm` package. Store project work products as external artifacts and use the DB only for threads, deliberate addressed messages, reply links, artifact links, and audit events. Treat `skills/` as the canonical portable skill source, with Claude and Codex manifests as thin adapters.

**Tech Stack:** Python 3.12+, stdlib `sqlite3`, stdlib `argparse`, stdlib `unittest`/`pytest` tests, `uv` for development only, Agent Skills `SKILL.md`, Claude Code `.claude-plugin/plugin.json`, Codex `.codex-plugin/plugin.json`.

---

## File Structure

- Create `pyproject.toml`: package metadata, Python floor, console script, pytest config.
- Create `README.md`: project purpose, development commands, runtime invocation.
- Create `agent_comm/__init__.py`: package version.
- Create `agent_comm/__main__.py`: portable `python -m agent_comm` entry point.
- Create `agent_comm/cli.py`: argparse command definitions and output formatting.
- Create `agent_comm/db.py`: SQLite connection, schema creation, version checks, transactions.
- Create `agent_comm/models.py`: small dataclasses for thread, message, artifact summaries.
- Create `agent_comm/ids.py`: stable id generation helpers.
- Create `agent_comm/paths.py`: bus path resolution and project key normalization.
- Create `agent_comm/export.py`: Markdown thread export.
- Create `tests/conftest.py`: temp bus fixtures and CLI runner.
- Create `tests/test_init.py`: init/version/path behavior.
- Create `tests/test_threads_messages.py`: threads, messages, replies, ack.
- Create `tests/test_cli_wait_export.py`: wait, follow, artifacts, export, migrate.
- Create `skills/coordinate-as-planner/SKILL.md`: planner role workflow.
- Create `skills/coordinate-as-planner/references/agent-communication-protocol.md`: copied shared protocol.
- Create `skills/coordinate-as-implementer/SKILL.md`: implementer role workflow.
- Create `skills/coordinate-as-implementer/references/agent-communication-protocol.md`: copied shared protocol.
- Create `.codex-plugin/plugin.json`: Codex adapter manifest pointing at `./skills/`.
- Create `.claude-plugin/plugin.json`: Claude adapter manifest.
- Create `examples/planner-handoff.md`: example body for a handoff signal.
- Create `examples/implementer-question.md`: example body for a question signal.
- Create `examples/ready-for-review.md`: example body for a review-ready signal.
- Create `docs/smoke-tests/fresh-agent-sessions.md`: manual Claude/Codex/Copilot-style smoke test procedure.

## Task 1: Python Package Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `agent_comm/__init__.py`
- Create: `agent_comm/__main__.py`
- Create: `agent_comm/cli.py`
- Create: `tests/conftest.py`
- Create: `tests/test_init.py`

- [ ] **Step 1: Write the failing CLI import and help tests**

Create `tests/conftest.py`:

```python
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def temp_bus(tmp_path: Path) -> Path:
    return tmp_path / "bus.sqlite"


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agent_comm", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
```

Create `tests/test_init.py`:

```python
from __future__ import annotations

from .conftest import run_cli


def test_module_help_runs() -> None:
    result = run_cli("--help")

    assert result.returncode == 0
    assert "agent-comm" in result.stdout
    assert "init" in result.stdout
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python -m pytest tests/test_init.py::test_module_help_runs -v
```

Expected: FAIL with `No module named agent_comm` or equivalent import failure.

- [ ] **Step 3: Add package metadata and minimal CLI entry point**

Create `pyproject.toml`:

```toml
[project]
name = "agents-together"
version = "0.1.0"
description = "Durable local coordination for independent coding agents"
requires-python = ">=3.12"
readme = "README.md"
dependencies = []

[project.scripts]
agent-comm = "agent_comm.cli:main"

[dependency-groups]
dev = [
  "pytest>=8.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

Create `README.md`:

````markdown
# Agents Together

Agents Together is a small local coordination system for independent coding agents.

Runtime invocation should work without `uv`:

```bash
python -m agent_comm --help
```

During development, use:

```bash
uv run pytest
uv run agent-comm --help
```
````

Create `agent_comm/__init__.py`:

```python
from __future__ import annotations

__version__ = "0.1.0"
```

Create `agent_comm/__main__.py`:

```python
from __future__ import annotations

from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
```

Create `agent_comm/cli.py`:

```python
from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-comm",
        description="Durable local coordination for independent coding agents.",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("init", help="Initialize a project coordination bus")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    return 0
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
python -m pytest tests/test_init.py::test_module_help_runs -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add pyproject.toml README.md agent_comm tests
git commit -m "feat: scaffold agent-comm package"
```

## Task 2: Bus Paths, Schema, Init, and Version Checks

**Files:**
- Create: `agent_comm/paths.py`
- Create: `agent_comm/db.py`
- Modify: `agent_comm/cli.py`
- Modify: `tests/test_init.py`

- [ ] **Step 1: Write failing tests for init and schema version**

Append to `tests/test_init.py`:

```python
import sqlite3


def test_init_creates_versioned_bus(temp_bus) -> None:
    result = run_cli("init", "--project", "github.com/example/project", "--bus", str(temp_bus))

    assert result.returncode == 0
    assert temp_bus.exists()
    with sqlite3.connect(temp_bus) as conn:
        version = conn.execute("pragma user_version").fetchone()[0]
        tables = {
            row[0]
            for row in conn.execute(
                "select name from sqlite_master where type = 'table'"
            ).fetchall()
        }
    assert version == 1
    assert {
        "agents",
        "threads",
        "messages",
        "message_replies",
        "artifacts",
        "events",
    }.issubset(tables)


def test_migrate_returns_not_implemented(temp_bus) -> None:
    init = run_cli("init", "--project", "proj", "--bus", str(temp_bus))
    assert init.returncode == 0

    result = run_cli("migrate", "--bus", str(temp_bus))

    assert result.returncode == 2
    assert "ERR_NOT_IMPLEMENTED" in result.stderr
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_init.py -v
```

Expected: FAIL because `--project`, `--bus`, schema creation, and `migrate` are not implemented.

- [ ] **Step 3: Implement path resolution**

Create `agent_comm/paths.py`:

```python
from __future__ import annotations

import os
import re
from pathlib import Path


def project_key(project_id: str) -> str:
    key = re.sub(r"[^a-zA-Z0-9._-]+", "-", project_id.strip())
    key = re.sub(r"-+", "-", key).strip("-")
    if not key:
        raise ValueError("project id must contain at least one usable character")
    return key


def default_bus_path(project_id: str) -> Path:
    root = Path.home() / ".agent-comm" / "projects" / project_key(project_id)
    return root / "bus.sqlite"


def resolve_bus_path(bus: str | None, project_id: str | None) -> Path:
    if bus:
        return Path(bus).expanduser()
    env_bus = os.environ.get("AGENT_COMM_BUS")
    if env_bus:
        return Path(env_bus).expanduser()
    if not project_id:
        raise ValueError("project id is required when --bus and AGENT_COMM_BUS are unset")
    return default_bus_path(project_id)
```

- [ ] **Step 4: Implement schema creation and version checks**

Create `agent_comm/db.py`:

```python
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA_SQL = """
create table if not exists agents(
  id text primary key,
  display_name text,
  harness text,
  created_at text not null,
  last_seen_at text
);

create table if not exists threads(
  id text primary key,
  project_id text not null,
  title text not null,
  status text not null,
  owner text not null,
  branch text,
  worktree text,
  created_at text not null,
  updated_at text not null,
  closed_at text
);

create table if not exists messages(
  id text primary key,
  thread_id text not null,
  seq integer not null,
  from_agent text not null,
  to_agent text not null,
  subject text not null,
  body_md text not null,
  priority text not null,
  created_at text not null,
  acked_at text,
  unique(thread_id, seq)
);

create table if not exists message_replies(
  message_id text not null,
  reply_to_message_id text not null,
  primary key(message_id, reply_to_message_id)
);

create table if not exists artifacts(
  id text primary key,
  thread_id text not null,
  kind text not null,
  path text,
  git_ref text,
  description text,
  created_at text not null
);

create table if not exists events(
  id text primary key,
  thread_id text,
  agent_id text not null,
  event_type text not null,
  payload_json text not null,
  created_at text not null
);
"""


class SchemaError(RuntimeError):
    pass


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: Path) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.execute(f"pragma user_version = {SCHEMA_VERSION}")


def require_supported_schema(conn: sqlite3.Connection) -> None:
    version = conn.execute("pragma user_version").fetchone()[0]
    if version != SCHEMA_VERSION:
        raise SchemaError(
            f"unsupported schema version {version}; this CLI supports {SCHEMA_VERSION}"
        )
```

- [ ] **Step 5: Wire init and migrate commands**

Replace `agent_comm/cli.py` with:

```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .db import init_db
from .paths import resolve_bus_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-comm",
        description="Durable local coordination for independent coding agents.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize a project coordination bus")
    init_parser.add_argument("--bus", help="Path to bus.sqlite")
    init_parser.add_argument("--project", required=True, help="Stable project id")

    migrate_parser = subparsers.add_parser("migrate", help="Run schema migrations")
    migrate_parser.add_argument("--bus", help="Path to bus.sqlite")
    return parser


def _cmd_init(args: argparse.Namespace) -> int:
    bus = resolve_bus_path(args.bus, args.project)
    init_db(bus)
    print(f"initialized {bus}")
    return 0


def _cmd_migrate(args: argparse.Namespace) -> int:
    print("ERR_NOT_IMPLEMENTED: migrations are not implemented in schema version 1", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        return _cmd_init(args)
    if args.command == "migrate":
        return _cmd_migrate(args)
    parser.error(f"unknown command {args.command}")
    return 2
```

- [ ] **Step 6: Run tests**

Run:

```bash
python -m pytest tests/test_init.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add agent_comm tests
git commit -m "feat: initialize versioned sqlite bus"
```

## Task 3: Threads, Messages, Replies, and Artifacts

**Files:**
- Create: `agent_comm/ids.py`
- Create: `agent_comm/models.py`
- Modify: `agent_comm/db.py`
- Create: `tests/test_threads_messages.py`

- [ ] **Step 1: Write failing repository tests**

Create `tests/test_threads_messages.py`:

```python
from __future__ import annotations

from agent_comm.db import add_artifact, ack_message, create_thread, get_message, init_db, post_message


def test_thread_message_reply_and_ack(temp_bus) -> None:
    init_db(temp_bus)
    thread = create_thread(temp_bus, project_id="proj", title="Build thing", owner="planner")
    first = post_message(
        temp_bus,
        thread_id=thread.id,
        from_agent="planner",
        to_agent="implementer",
        subject="Handoff",
        body_md="Read docs/handoff.md",
        priority="normal",
        reply_to=[],
    )
    second = post_message(
        temp_bus,
        thread_id=thread.id,
        from_agent="implementer",
        to_agent="planner",
        subject="Question",
        body_md="Need a decision.",
        priority="normal",
        reply_to=[first.id],
    )

    assert first.id != second.id
    assert first.seq == 1
    assert second.seq == 2
    loaded = get_message(temp_bus, second.id)
    assert loaded.reply_to == [first.id]

    ack_message(temp_bus, first.id, agent_id="implementer")
    acked = get_message(temp_bus, first.id)
    assert acked.acked_at is not None


def test_artifact_link(temp_bus) -> None:
    init_db(temp_bus)
    thread = create_thread(temp_bus, project_id="proj", title="Build thing", owner="planner")

    artifact = add_artifact(
        temp_bus,
        thread_id=thread.id,
        kind="handoff",
        artifact_path="docs/handoff.md",
        git_ref=None,
        description="Approved handoff",
    )

    assert artifact.kind == "handoff"
    assert artifact.path == "docs/handoff.md"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_threads_messages.py -v
```

Expected: FAIL because repository functions and models do not exist.

- [ ] **Step 3: Add ids and models**

Create `agent_comm/ids.py`:

```python
from __future__ import annotations

import uuid


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"
```

Create `agent_comm/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThreadRecord:
    id: str
    project_id: str
    title: str
    status: str
    owner: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class MessageRecord:
    id: str
    thread_id: str
    seq: int
    from_agent: str
    to_agent: str
    subject: str
    body_md: str
    priority: str
    created_at: str
    acked_at: str | None
    reply_to: list[str]


@dataclass(frozen=True)
class ArtifactRecord:
    id: str
    thread_id: str
    kind: str
    path: str | None
    git_ref: str | None
    description: str | None
    created_at: str
```

- [ ] **Step 4: Implement repository operations**

Append to `agent_comm/db.py`:

```python
from datetime import UTC, datetime

from .ids import new_id
from .models import ArtifactRecord, MessageRecord, ThreadRecord


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def create_thread(path: Path, *, project_id: str, title: str, owner: str) -> ThreadRecord:
    now = utc_now()
    thread_id = new_id("thr")
    with connect(path) as conn:
        require_supported_schema(conn)
        conn.execute(
            """
            insert into threads(id, project_id, title, status, owner, created_at, updated_at)
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            (thread_id, project_id, title, "open", owner, now, now),
        )
    return ThreadRecord(thread_id, project_id, title, "open", owner, now, now)


def _next_seq(conn: sqlite3.Connection, thread_id: str) -> int:
    row = conn.execute(
        "select coalesce(max(seq), 0) + 1 from messages where thread_id = ?",
        (thread_id,),
    ).fetchone()
    return int(row[0])


def post_message(
    path: Path,
    *,
    thread_id: str,
    from_agent: str,
    to_agent: str,
    subject: str,
    body_md: str,
    priority: str,
    reply_to: list[str],
) -> MessageRecord:
    now = utc_now()
    message_id = new_id("msg")
    with connect(path) as conn:
        require_supported_schema(conn)
        seq = _next_seq(conn, thread_id)
        conn.execute(
            """
            insert into messages(
              id, thread_id, seq, from_agent, to_agent, subject, body_md, priority, created_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (message_id, thread_id, seq, from_agent, to_agent, subject, body_md, priority, now),
        )
        for reply_id in reply_to:
            conn.execute(
                "insert into message_replies(message_id, reply_to_message_id) values (?, ?)",
                (message_id, reply_id),
            )
        conn.execute("update threads set updated_at = ? where id = ?", (now, thread_id))
    return MessageRecord(
        message_id, thread_id, seq, from_agent, to_agent, subject, body_md, priority, now, None, reply_to
    )


def get_message(path: Path, message_id: str) -> MessageRecord:
    with connect(path) as conn:
        require_supported_schema(conn)
        row = conn.execute("select * from messages where id = ?", (message_id,)).fetchone()
        if row is None:
            raise KeyError(f"message not found: {message_id}")
        replies = [
            r[0]
            for r in conn.execute(
                "select reply_to_message_id from message_replies where message_id = ? order by reply_to_message_id",
                (message_id,),
            ).fetchall()
        ]
    return MessageRecord(
        row["id"],
        row["thread_id"],
        row["seq"],
        row["from_agent"],
        row["to_agent"],
        row["subject"],
        row["body_md"],
        row["priority"],
        row["created_at"],
        row["acked_at"],
        replies,
    )


def ack_message(path: Path, message_id: str, *, agent_id: str) -> None:
    now = utc_now()
    with connect(path) as conn:
        require_supported_schema(conn)
        row = conn.execute("select to_agent from messages where id = ?", (message_id,)).fetchone()
        if row is None:
            raise KeyError(f"message not found: {message_id}")
        if row["to_agent"] != agent_id:
            raise PermissionError(f"message {message_id} is addressed to {row['to_agent']}, not {agent_id}")
        conn.execute("update messages set acked_at = ? where id = ?", (now, message_id))


def add_artifact(
    db_path: Path,
    *,
    thread_id: str,
    kind: str,
    artifact_path: str | None,
    git_ref: str | None,
    description: str | None,
) -> ArtifactRecord:
    now = utc_now()
    artifact_id = new_id("art")
    with connect(db_path) as conn:
        require_supported_schema(conn)
        conn.execute(
            """
            insert into artifacts(id, thread_id, kind, path, git_ref, description, created_at)
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            (artifact_id, thread_id, kind, artifact_path, git_ref, description, now),
        )
        conn.execute("update threads set updated_at = ? where id = ?", (now, thread_id))
    return ArtifactRecord(artifact_id, thread_id, kind, artifact_path, git_ref, description, now)
```

- [ ] **Step 5: Run tests**

Run:

```bash
python -m pytest tests/test_threads_messages.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add agent_comm tests
git commit -m "feat: add thread message and artifact records"
```

## Task 4: CLI Commands for Threads, Messages, Inbox, Ack, and Artifacts

**Files:**
- Modify: `agent_comm/db.py`
- Modify: `agent_comm/cli.py`
- Modify: `tests/test_threads_messages.py`

- [ ] **Step 1: Write failing CLI behavior tests**

Append to `tests/test_threads_messages.py`:

```python
from .conftest import run_cli


def test_cli_thread_post_inbox_show_ack_and_artifact(temp_bus, tmp_path) -> None:
    body = tmp_path / "handoff.md"
    body.write_text("Please implement the approved plan.\n", encoding="utf-8")

    assert run_cli("init", "--project", "proj", "--bus", str(temp_bus)).returncode == 0
    thread_result = run_cli(
        "start-thread",
        "--bus",
        str(temp_bus),
        "--project",
        "proj",
        "--title",
        "Build thing",
        "--owner",
        "planner",
    )
    assert thread_result.returncode == 0
    thread_id = thread_result.stdout.strip()

    post_result = run_cli(
        "post",
        "--bus",
        str(temp_bus),
        "--thread",
        thread_id,
        "--from",
        "planner",
        "--to",
        "implementer",
        "--subject",
        "Handoff",
        "--body-file",
        str(body),
    )
    assert post_result.returncode == 0
    message_id = post_result.stdout.strip()

    inbox = run_cli("inbox", "--bus", str(temp_bus), "--agent", "implementer")
    assert inbox.returncode == 0
    assert message_id in inbox.stdout
    assert "Handoff" in inbox.stdout

    shown = run_cli("show", "--bus", str(temp_bus), message_id)
    assert shown.returncode == 0
    assert "Please implement the approved plan." in shown.stdout

    artifact = run_cli(
        "artifact",
        "--bus",
        str(temp_bus),
        "add",
        "--thread",
        thread_id,
        "--kind",
        "handoff",
        "--path",
        str(body),
        "--description",
        "Approved handoff",
    )
    assert artifact.returncode == 0

    ack = run_cli("ack", "--bus", str(temp_bus), message_id, "--agent", "implementer")
    assert ack.returncode == 0

    empty = run_cli("inbox", "--bus", str(temp_bus), "--agent", "implementer")
    assert empty.returncode == 0
    assert message_id not in empty.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_threads_messages.py::test_cli_thread_post_inbox_show_ack_and_artifact -v
```

Expected: FAIL because CLI commands are not wired.

- [ ] **Step 3: Add inbox query helper**

Append to `agent_comm/db.py`:

```python
def inbox(path: Path, *, agent_id: str) -> list[MessageRecord]:
    with connect(path) as conn:
        require_supported_schema(conn)
        rows = conn.execute(
            """
            select * from messages
            where to_agent = ? and acked_at is null
            order by created_at asc, seq asc
            """,
            (agent_id,),
        ).fetchall()
    return [get_message(path, row["id"]) for row in rows]
```

- [ ] **Step 4: Wire CLI commands**

Update `agent_comm/cli.py` to import repository functions and add subcommands. The key command handlers should have this shape:

```python
from .db import (
    ack_message,
    add_artifact,
    create_thread,
    get_message,
    inbox,
    init_db,
    post_message,
)


def _bus(args: argparse.Namespace) -> Path:
    return resolve_bus_path(args.bus, getattr(args, "project", None))


def _cmd_start_thread(args: argparse.Namespace) -> int:
    thread = create_thread(_bus(args), project_id=args.project, title=args.title, owner=args.owner)
    print(thread.id)
    return 0


def _cmd_post(args: argparse.Namespace) -> int:
    body = Path(args.body_file).read_text(encoding="utf-8")
    message = post_message(
        _bus(args),
        thread_id=args.thread,
        from_agent=args.from_agent,
        to_agent=args.to_agent,
        subject=args.subject,
        body_md=body,
        priority=args.priority,
        reply_to=args.reply_to,
    )
    print(message.id)
    return 0


def _cmd_inbox(args: argparse.Namespace) -> int:
    for message in inbox(_bus(args), agent_id=args.agent):
        print(f"{message.id}\t{message.created_at}\t{message.from_agent}\t{message.subject}")
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    message = get_message(_bus(args), args.message_id)
    print(f"Message: {message.id}")
    print(f"Thread: {message.thread_id} seq={message.seq}")
    print(f"From: {message.from_agent}")
    print(f"To: {message.to_agent}")
    print(f"Subject: {message.subject}")
    print(f"Created: {message.created_at}")
    if message.reply_to:
        print(f"Replies-To: {', '.join(message.reply_to)}")
    print()
    print(message.body_md, end="" if message.body_md.endswith("\n") else "\n")
    return 0


def _cmd_ack(args: argparse.Namespace) -> int:
    ack_message(_bus(args), args.message_id, agent_id=args.agent)
    print(f"acked {args.message_id}")
    return 0


def _cmd_artifact_add(args: argparse.Namespace) -> int:
    artifact = add_artifact(
        _bus(args),
        thread_id=args.thread,
        kind=args.kind,
        artifact_path=args.path,
        git_ref=args.git_ref,
        description=args.description,
    )
    print(artifact.id)
    return 0
```

Add parser entries:

```python
thread_parser = subparsers.add_parser("start-thread", help="Start a collaboration thread")
thread_parser.add_argument("--bus", help="Path to bus.sqlite")
thread_parser.add_argument("--project", required=True)
thread_parser.add_argument("--title", required=True)
thread_parser.add_argument("--owner", required=True)

post_parser = subparsers.add_parser("post", help="Post a deliberate addressed message")
post_parser.add_argument("--bus", help="Path to bus.sqlite")
post_parser.add_argument("--thread", required=True)
post_parser.add_argument("--from", dest="from_agent", required=True)
post_parser.add_argument("--to", dest="to_agent", required=True)
post_parser.add_argument("--subject", required=True)
post_parser.add_argument("--body-file", required=True)
post_parser.add_argument("--priority", default="normal")
post_parser.add_argument("--reply-to", action="append", default=[])

inbox_parser = subparsers.add_parser("inbox", help="List unacknowledged messages")
inbox_parser.add_argument("--bus", help="Path to bus.sqlite")
inbox_parser.add_argument("--agent", required=True)

show_parser = subparsers.add_parser("show", help="Show a message")
show_parser.add_argument("--bus", help="Path to bus.sqlite")
show_parser.add_argument("message_id")

ack_parser = subparsers.add_parser("ack", help="Acknowledge a message")
ack_parser.add_argument("--bus", help="Path to bus.sqlite")
ack_parser.add_argument("message_id")
ack_parser.add_argument("--agent", required=True)

artifact_parser = subparsers.add_parser("artifact", help="Manage artifacts")
artifact_parser.add_argument("--bus", help="Path to bus.sqlite")
artifact_sub = artifact_parser.add_subparsers(dest="artifact_command", required=True)
artifact_add = artifact_sub.add_parser("add", help="Link an artifact")
artifact_add.add_argument("--thread", required=True)
artifact_add.add_argument("--kind", required=True)
artifact_add.add_argument("--path")
artifact_add.add_argument("--git-ref")
artifact_add.add_argument("--description")
```

Dispatch each command in `main`.

- [ ] **Step 5: Run tests**

Run:

```bash
python -m pytest tests/test_threads_messages.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add agent_comm tests
git commit -m "feat: expose core coordination commands"
```

## Task 5: Wait, Follow, Status, Export

**Files:**
- Create: `agent_comm/export.py`
- Modify: `agent_comm/db.py`
- Modify: `agent_comm/cli.py`
- Create: `tests/test_cli_wait_export.py`

- [ ] **Step 1: Write failing tests for export and wait**

Create `tests/test_cli_wait_export.py`:

```python
from __future__ import annotations

import subprocess
import sys
import time

from .conftest import run_cli


def test_wait_exits_when_message_exists(temp_bus, tmp_path) -> None:
    body = tmp_path / "body.md"
    body.write_text("Act on this.\n", encoding="utf-8")
    run_cli("init", "--project", "proj", "--bus", str(temp_bus))
    thread = run_cli(
        "start-thread", "--bus", str(temp_bus), "--project", "proj", "--title", "T", "--owner", "planner"
    ).stdout.strip()
    message = run_cli(
        "post",
        "--bus",
        str(temp_bus),
        "--thread",
        thread,
        "--from",
        "planner",
        "--to",
        "implementer",
        "--subject",
        "Signal",
        "--body-file",
        str(body),
    ).stdout.strip()

    result = run_cli("wait", "--bus", str(temp_bus), "--agent", "implementer", "--interval", "0.01")

    assert result.returncode == 0
    assert message in result.stdout
    assert "Signal" in result.stdout


def test_wait_follow_prints_new_message_without_ack(temp_bus, tmp_path) -> None:
    body = tmp_path / "body.md"
    body.write_text("Act on this.\n", encoding="utf-8")
    run_cli("init", "--project", "proj", "--bus", str(temp_bus))
    thread = run_cli(
        "start-thread", "--bus", str(temp_bus), "--project", "proj", "--title", "T", "--owner", "planner"
    ).stdout.strip()

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "agent_comm",
            "wait",
            "--bus",
            str(temp_bus),
            "--agent",
            "implementer",
            "--follow",
            "--interval",
            "0.01",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        time.sleep(0.05)
        message = run_cli(
            "post",
            "--bus",
            str(temp_bus),
            "--thread",
            thread,
            "--from",
            "planner",
            "--to",
            "implementer",
            "--subject",
            "Signal",
            "--body-file",
            str(body),
        ).stdout.strip()
        deadline = time.time() + 2
        output = ""
        while time.time() < deadline and message not in output:
            output += proc.stdout.readline()
        assert message in output
    finally:
        proc.terminate()
        proc.wait(timeout=2)


def test_export_writes_thread_markdown(temp_bus, tmp_path) -> None:
    body = tmp_path / "body.md"
    body.write_text("Act on this.\n", encoding="utf-8")
    run_cli("init", "--project", "proj", "--bus", str(temp_bus))
    thread = run_cli(
        "start-thread", "--bus", str(temp_bus), "--project", "proj", "--title", "T", "--owner", "planner"
    ).stdout.strip()
    run_cli(
        "post",
        "--bus",
        str(temp_bus),
        "--thread",
        thread,
        "--from",
        "planner",
        "--to",
        "implementer",
        "--subject",
        "Signal",
        "--body-file",
        str(body),
    )

    result = run_cli("export", "--bus", str(temp_bus), "--thread", thread)

    assert result.returncode == 0
    export_path = result.stdout.strip()
    assert "thread-" in export_path
    assert "Signal" in open(export_path, encoding="utf-8").read()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_cli_wait_export.py -v
```

Expected: FAIL because `wait` and `export` do not exist.

- [ ] **Step 3: Add thread detail query and export renderer**

Append query helpers to `agent_comm/db.py`:

```python
def thread_messages(path: Path, *, thread_id: str) -> list[MessageRecord]:
    with connect(path) as conn:
        require_supported_schema(conn)
        rows = conn.execute(
            "select id from messages where thread_id = ? order by seq asc",
            (thread_id,),
        ).fetchall()
    return [get_message(path, row["id"]) for row in rows]


def thread_artifacts(path: Path, *, thread_id: str) -> list[ArtifactRecord]:
    with connect(path) as conn:
        require_supported_schema(conn)
        rows = conn.execute(
            "select * from artifacts where thread_id = ? order by created_at asc",
            (thread_id,),
        ).fetchall()
    return [
        ArtifactRecord(
            row["id"],
            row["thread_id"],
            row["kind"],
            row["path"],
            row["git_ref"],
            row["description"],
            row["created_at"],
        )
        for row in rows
    ]
```

Create `agent_comm/export.py`:

```python
from __future__ import annotations

from pathlib import Path

from .db import thread_artifacts, thread_messages


def export_thread(db_path: Path, *, thread_id: str) -> Path:
    export_dir = db_path.parent / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    output = export_dir / f"thread-{thread_id}.md"
    messages = thread_messages(db_path, thread_id=thread_id)
    artifacts = thread_artifacts(db_path, thread_id=thread_id)

    lines = [f"# Thread {thread_id}", ""]
    lines.extend(["## Artifacts", ""])
    if artifacts:
        for artifact in artifacts:
            target = artifact.path or artifact.git_ref or ""
            lines.append(f"- `{artifact.kind}` {target} {artifact.description or ''}".rstrip())
    else:
        lines.append("- No artifacts linked.")
    lines.extend(["", "## Messages", ""])
    for message in messages:
        lines.append(f"### {message.seq}. {message.subject}")
        lines.append("")
        lines.append(f"- Id: `{message.id}`")
        lines.append(f"- From: `{message.from_agent}`")
        lines.append(f"- To: `{message.to_agent}`")
        lines.append(f"- Created: `{message.created_at}`")
        if message.acked_at:
            lines.append(f"- Acked: `{message.acked_at}`")
        if message.reply_to:
            lines.append(f"- Replies-To: {', '.join(f'`{r}`' for r in message.reply_to)}")
        lines.append("")
        lines.append(message.body_md.rstrip())
        lines.append("")
    output.write_text("\n".join(lines), encoding="utf-8")
    return output
```

- [ ] **Step 4: Wire wait and export commands**

In `agent_comm/cli.py`, add:

```python
import time

from .export import export_thread


def _print_message_summary(message) -> None:
    print(f"{message.id}\t{message.created_at}\t{message.from_agent}\t{message.subject}", flush=True)


def _cmd_wait(args: argparse.Namespace) -> int:
    printed: set[str] = set()
    while True:
        messages = inbox(_bus(args), agent_id=args.agent)
        new_messages = [message for message in messages if message.id not in printed]
        for message in new_messages:
            _print_message_summary(message)
            printed.add(message.id)
        if new_messages and not args.follow:
            return 0
        time.sleep(args.interval)


def _cmd_export(args: argparse.Namespace) -> int:
    output = export_thread(_bus(args), thread_id=args.thread)
    print(output)
    return 0
```

Add parser entries:

```python
wait_parser = subparsers.add_parser("wait", help="Wait for unacknowledged messages")
wait_parser.add_argument("--bus", help="Path to bus.sqlite")
wait_parser.add_argument("--agent", required=True)
wait_parser.add_argument("--follow", "-f", action="store_true")
wait_parser.add_argument("--interval", type=float, default=2.0)

export_parser = subparsers.add_parser("export", help="Export a thread to Markdown")
export_parser.add_argument("--bus", help="Path to bus.sqlite")
export_parser.add_argument("--thread", required=True)
```

Dispatch `wait` and `export` in `main`.

- [ ] **Step 5: Run tests**

Run:

```bash
python -m pytest tests/test_cli_wait_export.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add agent_comm tests
git commit -m "feat: add wait and markdown export"
```

## Task 6: Portable Skills, Protocol References, and Examples

**Files:**
- Create: `skills/coordinate-as-planner/SKILL.md`
- Create: `skills/coordinate-as-planner/references/agent-communication-protocol.md`
- Create: `skills/coordinate-as-implementer/SKILL.md`
- Create: `skills/coordinate-as-implementer/references/agent-communication-protocol.md`
- Create: `examples/planner-handoff.md`
- Create: `examples/implementer-question.md`
- Create: `examples/ready-for-review.md`

- [ ] **Step 1: Create protocol reference content**

Create both `references/agent-communication-protocol.md` files with identical content:

````markdown
# Agent Communication Protocol

Use `agent-comm` for deliberate cross-agent signals only. Do not use it for routine progress logs or private scratch state.

## Runtime Command

Prefer:

```bash
python -m agent_comm
```

Use `agent-comm` only when it is installed on `PATH`. Use `uv run agent-comm` only in a development checkout where `uv` is available.

## Message Rules

- Send messages to a specific `to_agent`.
- Use a clear `subject`.
- Put the requested action in the message body.
- Link project artifacts instead of pasting large plans or logs into the bus.
- Acknowledge a message only after reading enough to take ownership.
- Reply with `--reply-to` when responding to specific messages.

## Artifact Boundary

Specs, plans, handoffs, status notes, review reports, and test logs remain project files. The bus stores links and deliberate signals.

## Inbox Discipline

Check inboxes at coordination boundaries. Implementers should also check periodically during longer work. Background `wait --follow` is optional.
````

- [ ] **Step 2: Create planner skill**

Create `skills/coordinate-as-planner/SKILL.md`:

````markdown
---
name: coordinate-as-planner
description: Coordinate as the planning agent using agent-comm. Use when preparing implementation handoffs, sending deliberate messages to implementers, answering implementation questions, reviewing ready work, or accepting/rejecting completed work through a durable local agent mailbox.
---

# Coordinate as Planner

Use this skill when acting as the planning side of an agent-to-agent workflow.

## Start

1. Resolve the command:
   - Prefer `python -m agent_comm`.
   - Use `agent-comm` if installed on `PATH`.
   - Use `uv run agent-comm` only inside a development checkout.
2. Read `references/agent-communication-protocol.md`.
3. Identify your planner agent id. Use `planner` unless the user or existing thread specifies another id.
4. Initialize or select the bus and thread.

## Handoff

Create a project-native handoff artifact before posting. Include:

- Spec and plan paths.
- Acceptance criteria.
- Branch/worktree guidance when known.
- Verification commands.
- Requested next action.

Post only the deliberate signal:

```bash
python -m agent_comm post \
  --thread THREAD_ID \
  --from planner \
  --to implementer \
  --subject "Implementation handoff ready" \
  --body-file docs/handoffs/example.md
```

## While Waiting

Check your inbox at coordination boundaries:

```bash
python -m agent_comm inbox --agent planner
```

Use `wait --follow` only when the harness can safely run a background watch.

## Responding

Use `show` before responding:

```bash
python -m agent_comm show MESSAGE_ID
```

Reply with `--reply-to MESSAGE_ID` when answering a question, sending a decision, requesting fixes, or accepting work.

Do not rely on chat history as the handoff or acceptance record.
````

- [ ] **Step 3: Create implementer skill**

Create `skills/coordinate-as-implementer/SKILL.md`:

````markdown
---
name: coordinate-as-implementer
description: Coordinate as the implementation agent using agent-comm. Use when receiving planner handoffs, reading durable agent messages, acknowledging work, asking implementation questions, reporting plan defects, or signaling ready-for-review work through a local mailbox.
---

# Coordinate as Implementer

Use this skill when acting as the implementation side of an agent-to-agent workflow.

## Start

1. Resolve the command:
   - Prefer `python -m agent_comm`.
   - Use `agent-comm` if installed on `PATH`.
   - Use `uv run agent-comm` only inside a development checkout.
2. Read `references/agent-communication-protocol.md`.
3. Identify your implementer agent id. Use `implementer` unless the user or existing thread specifies another id.
4. Read your inbox:

```bash
python -m agent_comm inbox --agent implementer
```

## Consuming Work

Show the message before acting:

```bash
python -m agent_comm show MESSAGE_ID
```

Ack only after reading enough to take ownership:

```bash
python -m agent_comm ack MESSAGE_ID --agent implementer
```

Use project artifacts for working notes, verification logs, and implementation status.

## During Work

Check the inbox at natural coordination points and periodically during longer work:

```bash
python -m agent_comm inbox --agent implementer
```

Send a deliberate message if the plan is contradictory, unsafe, untestable, or missing a decision. Reply to the relevant message:

```bash
python -m agent_comm post \
  --thread THREAD_ID \
  --from implementer \
  --to planner \
  --subject "Question about retry behavior" \
  --reply-to MESSAGE_ID \
  --body-file docs/questions/retry-behavior.md
```

## Ready for Review

Create a project-native ready-for-review artifact with branch, summary, verification results, review status, and known risks. Post a deliberate signal pointing at it.
````

- [ ] **Step 4: Create example message bodies**

Create `examples/planner-handoff.md`:

```markdown
# Implementation Handoff

Requested action: implement the approved plan.

Artifacts:
- Spec: docs/superpowers/specs/2026-06-29-agents-together-design.md
- Plan: docs/superpowers/plans/2026-06-29-agents-together.md

Acceptance criteria:
- CLI tests pass with `python -m pytest`.
- Skills validate as Agent Skills.
- Claude and Codex plugin manifests are present.
```

Create `examples/implementer-question.md`:

```markdown
# Question

Requested action: planner decision required.

I found that the plan allows arbitrary priorities but does not define display ordering for equal timestamps.

Proposed decision:
Sort inbox by `created_at asc, seq asc`.
```

Create `examples/ready-for-review.md`:

```markdown
# Ready for Review

Requested action: review and either accept or send findings.

Artifacts:
- Branch: feature/agent-comm-mvp
- Test log: test-logs/agent-comm-mvp.txt
- Summary: docs/status/agent-comm-mvp.md

Known risks:
- Fresh-agent smoke tests require local harness setup.
```

- [ ] **Step 5: Validate skill frontmatter manually**

Run:

```bash
python - <<'PY'
from pathlib import Path
for path in Path("skills").glob("*/SKILL.md"):
    text = path.read_text()
    assert text.startswith("---\n"), path
    assert "\nname: " in text, path
    assert "\ndescription: " in text, path
    assert path.parent.name in text, path
print("skill frontmatter ok")
PY
```

Expected: prints `skill frontmatter ok`.

- [ ] **Step 6: Commit**

Run:

```bash
git add skills examples
git commit -m "feat: add coordination skills and examples"
```

## Task 7: Plugin Manifests and Fresh-Agent Smoke Test Docs

**Files:**
- Create: `.codex-plugin/plugin.json`
- Create: `.claude-plugin/plugin.json`
- Create: `docs/smoke-tests/fresh-agent-sessions.md`
- Modify: `README.md`

- [ ] **Step 1: Create Codex plugin manifest**

Create `.codex-plugin/plugin.json`:

```json
{
  "name": "agents-together",
  "version": "0.1.0",
  "description": "Durable local coordination workflows for independent coding agents",
  "skills": "./skills/"
}
```

- [ ] **Step 2: Create Claude plugin manifest**

Create `.claude-plugin/plugin.json`:

```json
{
  "name": "agents-together",
  "version": "0.1.0",
  "description": "Durable local coordination workflows for independent coding agents",
  "skills": "./skills/"
}
```

- [ ] **Step 3: Create fresh-agent smoke test procedure**

Create `docs/smoke-tests/fresh-agent-sessions.md`:

````markdown
# Fresh Agent Session Smoke Tests

These tests verify that the skills work when invoked by new agent sessions. They are manual because each harness has different installation and session controls.

## Shared Setup

From this repo:

```bash
python -m agent_comm init --project agents-together --bus /tmp/agents-together-smoke.sqlite
THREAD_ID=$(python -m agent_comm start-thread --project agents-together --bus /tmp/agents-together-smoke.sqlite --title "Smoke test" --owner planner)
printf '%s\n' "# Smoke Handoff" "Requested action: respond from implementer." > /tmp/agents-together-handoff.md
python -m agent_comm post --bus /tmp/agents-together-smoke.sqlite --thread "$THREAD_ID" --from planner --to implementer --subject "Smoke handoff" --body-file /tmp/agents-together-handoff.md
```

## Implementer Session

Start a fresh agent session with the plugin or skills exposed. Ask it:

```text
Use coordinate-as-implementer. Bus: /tmp/agents-together-smoke.sqlite. Agent id: implementer. Read your inbox, show the message, acknowledge it, and reply to planner with a short ready message.
```

Expected:

- The agent uses `python -m agent_comm`.
- The agent reads the protocol reference.
- The agent runs `inbox`, `show`, `ack`, and `post --reply-to`.
- The reply is addressed to `planner`.

## Planner Session

Start a separate fresh agent session with the plugin or skills exposed. Ask it:

```text
Use coordinate-as-planner. Bus: /tmp/agents-together-smoke.sqlite. Agent id: planner. Read your inbox and show any implementer reply.
```

Expected:

- The agent uses `python -m agent_comm`.
- The agent finds the implementer reply.
- The agent does not rely on prior chat history.
````

- [ ] **Step 4: Update README with validation commands**

Append to `README.md`:

````markdown
## Validation

```bash
python -m pytest
python -m agent_comm --help
python -m agent_comm init --project agents-together --bus /tmp/agents-together.sqlite
```

Fresh-agent smoke tests are documented in `docs/smoke-tests/fresh-agent-sessions.md`.
````

- [ ] **Step 5: Validate JSON manifests**

Run:

```bash
python -m json.tool .codex-plugin/plugin.json >/tmp/codex-plugin.json
python -m json.tool .claude-plugin/plugin.json >/tmp/claude-plugin.json
```

Expected: both commands exit 0.

- [ ] **Step 6: Commit**

Run:

```bash
git add .codex-plugin .claude-plugin docs/smoke-tests README.md
git commit -m "feat: add plugin manifests and smoke tests"
```

## Task 8: Final Verification and Tightening

**Files:**
- Modify only files required to fix verification failures.

- [ ] **Step 1: Run full tests**

Run:

```bash
python -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 2: Run development workflow with uv**

Run:

```bash
uv run pytest -v
uv run agent-comm --help
```

Expected: all tests PASS and help prints successfully.

- [ ] **Step 3: Run a local CLI smoke test**

Run:

```bash
python -m agent_comm init --project agents-together --bus /tmp/agents-together-local.sqlite
THREAD_ID=$(python -m agent_comm start-thread --project agents-together --bus /tmp/agents-together-local.sqlite --title "Local smoke" --owner planner)
printf '%s\n' "Requested action: inspect this local smoke message." > /tmp/agents-together-local-body.md
MSG_ID=$(python -m agent_comm post --bus /tmp/agents-together-local.sqlite --thread "$THREAD_ID" --from planner --to implementer --subject "Local smoke" --body-file /tmp/agents-together-local-body.md)
python -m agent_comm inbox --bus /tmp/agents-together-local.sqlite --agent implementer
python -m agent_comm show --bus /tmp/agents-together-local.sqlite "$MSG_ID"
python -m agent_comm ack --bus /tmp/agents-together-local.sqlite "$MSG_ID" --agent implementer
python -m agent_comm export --bus /tmp/agents-together-local.sqlite --thread "$THREAD_ID"
```

Expected: inbox shows the message before ack, show prints the body, ack succeeds, export prints a Markdown path.

- [ ] **Step 4: Validate no accidental progress-message taxonomy returned**

Run:

```bash
rg -n "handoff_ready|implementation_started|plan_defect|code_ready|message type|--type" .
```

Expected: no matches in implementation docs or skills except historical discussion in `handover.md` if it remains untracked.

- [ ] **Step 5: Commit fixes if verification required changes**

If Step 1, 2, 3, or 4 required edits, run:

```bash
git add agent_comm tests skills examples docs README.md pyproject.toml .codex-plugin .claude-plugin
git commit -m "fix: tighten agent comm mvp verification"
```

Expected: commit created only when verification edits were necessary.

## Self-Review Notes

- Spec coverage: package scaffold, schema versioning, deliberate messages, arbitrary agent ids, reply links, artifacts, wait/follow, export, skills, manifests, and smoke tests are covered.
- Runtime invocation: agent instructions use `python -m agent_comm`; `uv` is limited to development and verification.
- No daemon: inbox checking and optional `wait --follow` are documented in skills and smoke tests.
- Progress boundary: routine progress is kept in project artifacts, not message types.
