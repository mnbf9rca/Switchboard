# Agents Together Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the MVP `agents-together` plugin-shaped repo with a Python 3.12+ SQLite coordination CLI and two portable Agent Skills.

**Architecture:** Keep the SQLite bus and CLI in a focused `agent_comm` package. Use SQLite for durable threads, deliberate addressed messages, structured message headers, reply links, artifact links, agent registration, health checks, backups, and exports. Keep project work products as external artifacts. Treat `skills/` as the canonical portable skill source, with Claude and Codex manifests as thin adapters.

**Tech Stack:** Python 3.12+, stdlib `sqlite3`, stdlib `argparse`, stdlib `json`, stdlib `hashlib`, stdlib `subprocess`, pytest, `uv` for development only, Agent Skills `SKILL.md`, Claude Code `.claude-plugin/plugin.json`, Codex `.codex-plugin/plugin.json`.

---

## File Structure

- Create `pyproject.toml`: package metadata, Python floor, console script, pytest config.
- Create `.gitignore`: ignore local bus pointer config and generated runtime files.
- Create `README.md`: purpose, runtime/development commands, validation commands.
- Create `agent_comm/__init__.py`: package version.
- Create `agent_comm/__main__.py`: `python -m agent_comm` entry point.
- Create `agent_comm/cli.py`: argparse commands and output formatting.
- Create `agent_comm/db.py`: SQLite connection, schema, WAL, transactions, repository functions.
- Create `agent_comm/headers.py`: structured message header parser/validator.
- Create `agent_comm/ids.py`: stable id generation.
- Create `agent_comm/models.py`: dataclasses for records and parsed headers.
- Create `agent_comm/paths.py`: bus path resolution, config, remote canonicalization, safety checks.
- Create `agent_comm/export.py`: status and Markdown export rendering.
- Create `agent_comm/health.py`: doctor, backup, restore, integrity, permissions.
- Create `tests/conftest.py`: temp bus fixtures, CLI runner, timeout helpers.
- Create `tests/test_init_paths.py`: package, init, path/config behavior.
- Create `tests/test_db_health.py`: WAL, schema, permissions, doctor, backup, restore, corruption behavior.
- Create `tests/test_headers.py`: structured header parser and CLI rejection behavior.
- Create `tests/test_threads_messages.py`: threads, register, messages, replies, ack, claims, artifacts.
- Create `tests/test_cli_status_wait_export.py`: inbox, wait/follow, status, export, stale claims.
- Create `skills/coordinate-as-planner/SKILL.md` and `references/agent-communication-protocol.md`.
- Create `skills/coordinate-as-implementer/SKILL.md` and `references/agent-communication-protocol.md`.
- Create examples: `planner-handoff.md`, `implementer-question.md`, `plan-defect.md`, `ready-for-review.md`, `review-findings.md`.
- Create `.codex-plugin/plugin.json` and `.claude-plugin/plugin.json`.
- Create `docs/smoke-tests/fresh-agent-sessions.md`.

## Task 1: Package Scaffold and CLI Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `agent_comm/__init__.py`
- Create: `agent_comm/__main__.py`
- Create: `agent_comm/cli.py`
- Create: `tests/conftest.py`
- Create: `tests/test_init_paths.py`

- [ ] **Step 1: Write failing help/version tests**

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


def run_cli(*args: str, cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, "-m", "agent_comm", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    if check and result.returncode != 0:
        raise AssertionError(f"command failed: {result.args}\nstdout={result.stdout}\nstderr={result.stderr}")
    return result
```

Create `tests/test_init_paths.py`:

```python
from __future__ import annotations

from .conftest import run_cli


def test_help_and_version_run() -> None:
    help_result = run_cli("--help")
    version_result = run_cli("--version")

    assert help_result.returncode == 0
    assert "agent-comm" in help_result.stdout
    assert "init" in help_result.stdout
    assert version_result.returncode == 0
    assert "0.1.0" in version_result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_init_paths.py::test_help_and_version_run -v
```

Expected: FAIL with `No module named agent_comm`.

- [ ] **Step 3: Add package files and skeleton CLI**

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

Agents Together is a local coordination system for independent coding agents.

Runtime invocation should not assume `uv`:

```bash
agent-comm --version
python3 -m agent_comm --version
python -m agent_comm --version
```

During development:

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

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-comm",
        description="Durable local coordination for independent coding agents.",
    )
    parser.add_argument("--version", action="version", version=f"agent-comm {__version__}")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("init", help="Initialize a project coordination bus")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest tests/test_init_paths.py::test_help_and_version_run -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add pyproject.toml README.md agent_comm tests
git commit -m "feat: scaffold agent comm package"
```

## Task 2: Path Resolution and Config Safety

**Files:**
- Create: `.gitignore`
- Create: `agent_comm/paths.py`
- Modify: `tests/test_init_paths.py`

- [ ] **Step 1: Write failing path/config tests**

Append to `tests/test_init_paths.py`:

```python
import json
import subprocess
from pathlib import Path

import pytest

from agent_comm.paths import canonical_remote, project_key, resolve_bus_path


def test_project_key_slug_includes_hash() -> None:
    key = project_key("github.com/example/project")

    assert key.startswith("github.com-example-project-")
    assert len(key.rsplit("-", 1)[-1]) == 12


def test_canonical_remote_normalizes_common_forms() -> None:
    assert canonical_remote("git@github.com:Example/Project.git") == "github.com/example/project"
    assert canonical_remote("https://github.com/example/project.git") == "github.com/example/project"
    assert canonical_remote("ssh://git@github.com:22/example/project.git") == "github.com/example/project"


def test_resolution_order_uses_bus_then_env_then_local_config(tmp_path, monkeypatch) -> None:
    explicit = tmp_path / "explicit.sqlite"
    env_bus = tmp_path / "env.sqlite"
    local_bus = tmp_path / "local.sqlite"
    (tmp_path / ".agent-comm.local.json").write_text(json.dumps({"bus": str(local_bus)}), encoding="utf-8")
    monkeypatch.setenv("AGENT_COMM_BUS", str(env_bus))

    assert resolve_bus_path(bus=str(explicit), project=None, cwd=tmp_path) == explicit
    assert resolve_bus_path(bus=None, project=None, cwd=tmp_path) == env_bus
    monkeypatch.delenv("AGENT_COMM_BUS")
    assert resolve_bus_path(bus=None, project=None, cwd=tmp_path) == local_bus


def test_committed_config_bus_is_rejected(tmp_path) -> None:
    (tmp_path / ".agent-comm.json").write_text(
        json.dumps({"project_id": "github.com/example/project", "bus": "/tmp/bad.sqlite"}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="committed.*bus"):
        resolve_bus_path(bus=None, project=None, cwd=tmp_path)


def test_committed_project_id_derives_default_bus(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    (tmp_path / ".agent-comm.json").write_text(
        json.dumps({"project_id": "github.com/example/project"}),
        encoding="utf-8",
    )

    bus = resolve_bus_path(bus=None, project=None, cwd=tmp_path)

    assert str(bus).startswith(str(home / ".agent-comm" / "projects"))
    assert bus.name == "bus.sqlite"


def test_gitignore_excludes_local_pointer_config() -> None:
    assert ".agent-comm.local.json" in Path(".gitignore").read_text(encoding="utf-8")


def test_detects_bus_inside_git_worktree(tmp_path) -> None:
    from agent_comm.paths import bus_inside_git_worktree

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    repo_bus = tmp_path / ".agent-comm" / "bus.sqlite"
    outside_bus = tmp_path.parent / "outside-bus.sqlite"

    assert bus_inside_git_worktree(repo_bus, tmp_path) is True
    assert bus_inside_git_worktree(outside_bus, tmp_path) is False


def test_same_canonical_remote_same_bus_across_worktrees(tmp_path, monkeypatch) -> None:
    from agent_comm import paths

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    w1 = tmp_path / "worktree-one"
    w2 = tmp_path / "worktree-two"
    w1.mkdir()
    w2.mkdir()

    def fake_origin(cwd: Path, remote_name: str) -> str | None:
        if remote_name != "origin":
            return None
        return {
            w1: "git@github.com:Example/Project.git",
            w2: "https://github.com/example/project.git",
        }[cwd]

    monkeypatch.setattr(paths, "_git_remote", fake_origin)
    monkeypatch.setattr(paths, "_single_git_remote", lambda cwd: None)

    assert resolve_bus_path(bus=None, project=None, cwd=w1) == resolve_bus_path(bus=None, project=None, cwd=w2)


def test_project_keys_do_not_collide_for_similar_slugs() -> None:
    first = project_key("github.com/example/a-b")
    second = project_key("github.com/example/a/b")

    assert first != second
    assert first.rsplit("-", 1)[-1] != second.rsplit("-", 1)[-1]


def test_multi_remote_without_origin_is_ambiguous(tmp_path, monkeypatch) -> None:
    from agent_comm import paths

    monkeypatch.setattr(paths, "_git_remote", lambda cwd, remote_name: None)

    def ambiguous_remote(cwd: Path) -> str | None:
        raise ValueError("multiple git remotes found; pass --project or --remote")

    monkeypatch.setattr(paths, "_single_git_remote", ambiguous_remote)

    with pytest.raises(ValueError, match="multiple git remotes"):
        resolve_bus_path(bus=None, project=None, cwd=tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_init_paths.py -v
```

Expected: FAIL because `agent_comm.paths` does not exist.

- [ ] **Step 3: Implement path resolution**

Create `.gitignore`:

```gitignore
.agent-comm.local.json
.agent-comm/
*.sqlite-wal
*.sqlite-shm
```

Create `agent_comm/paths.py`:

```python
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse


def canonical_remote(remote: str) -> str:
    value = remote.strip()
    if value.startswith("git@") and ":" in value:
        host, path = value[4:].split(":", 1)
        parsed_path = path
    else:
        parsed = urlparse(value)
        host = parsed.hostname or ""
        parsed_path = parsed.path.lstrip("/")
        if parsed_path.startswith("~"):
            parsed_path = parsed_path.lstrip("~/")
    host = host.lower()
    parsed_path = parsed_path.removesuffix(".git").strip("/")
    parsed_path = re.sub(r"/+", "/", parsed_path).lower()
    if not host or parsed_path.count("/") < 1:
        raise ValueError(f"unsupported remote URL: {remote}")
    return f"{host}/{parsed_path}"


def project_key(project_id: str) -> str:
    canonical = project_id.strip()
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", canonical).strip("-").lower()
    slug = re.sub(r"-+", "-", slug)[:80].strip("-")
    if not slug:
        slug = "project"
    return f"{slug}-{digest}"


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _git_remote(cwd: Path, remote_name: str) -> str | None:
    result = subprocess.run(
        ["git", "remote", "get-url", remote_name],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def _single_git_remote(cwd: Path) -> str | None:
    result = subprocess.run(["git", "remote"], cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        return None
    names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(names) == 1:
        return _git_remote(cwd, names[0])
    if len(names) > 1:
        raise ValueError("multiple git remotes found; pass --project or --remote")
    return None


def _default_bus(project_id: str) -> Path:
    return Path.home() / ".agent-comm" / "projects" / project_key(project_id) / "bus.sqlite"


def bus_inside_git_worktree(bus_path: Path, cwd: Path) -> bool:
    try:
        root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return False
    if root.returncode != 0:
        return False
    repo_root = Path(root.stdout.strip()).resolve()
    try:
        bus_path.expanduser().resolve().relative_to(repo_root)
    except ValueError:
        return False
    return True


def resolve_project_id(project: str | None, cwd: Path, remote: str | None = None) -> str:
    if project:
        return project
    committed = _read_json(cwd / ".agent-comm.json")
    if "bus" in committed:
        raise ValueError("committed .agent-comm.json must not contain bus")
    if isinstance(committed.get("project_id"), str):
        return str(committed["project_id"])
    if remote:
        return canonical_remote(remote)
    origin = _git_remote(cwd, "origin")
    if origin:
        return canonical_remote(origin)
    only_remote = _single_git_remote(cwd)
    if only_remote:
        return canonical_remote(only_remote)
    raise ValueError("project id is required when no bus, config, or git remote is available")


def resolve_bus_path(
    *,
    bus: str | None,
    project: str | None,
    cwd: Path | None = None,
    remote: str | None = None,
) -> Path:
    base = cwd or Path.cwd()
    if bus:
        return Path(bus).expanduser()
    env_bus = os.environ.get("AGENT_COMM_BUS")
    if env_bus:
        return Path(env_bus).expanduser()
    local = _read_json(base / ".agent-comm.local.json")
    if isinstance(local.get("bus"), str):
        return Path(str(local["bus"])).expanduser()
    return _default_bus(resolve_project_id(project, base, remote))
```

When wiring CLI commands, call `bus_inside_git_worktree()` after resolving any explicit or configured bus path. Emit a stderr warning and include the warning in `doctor` output when the bus resolves inside the current git worktree.

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_init_paths.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add .gitignore agent_comm/paths.py tests/test_init_paths.py
git commit -m "feat: add bus path resolution"
```

## Task 3: Schema, WAL, Permissions, Init, and Migration Stub

**Files:**
- Create: `agent_comm/db.py`
- Modify: `agent_comm/cli.py`
- Create: `tests/test_db_health.py`
- Modify: `tests/test_init_paths.py`

- [ ] **Step 1: Write failing DB init tests**

Create `tests/test_db_health.py`:

```python
from __future__ import annotations

import os
import sqlite3
import stat

from .conftest import run_cli


def test_init_creates_private_versioned_wal_bus(temp_bus) -> None:
    result = run_cli("init", "--project", "github.com/example/project", "--bus", str(temp_bus))

    assert result.returncode == 0, result.stderr
    assert temp_bus.exists()
    with sqlite3.connect(temp_bus) as conn:
        assert conn.execute("pragma user_version").fetchone()[0] == 1
        assert conn.execute("pragma journal_mode").fetchone()[0].lower() == "wal"
        tables = {row[0] for row in conn.execute("select name from sqlite_master where type='table'")}
    assert {"agents", "threads", "messages", "message_replies", "artifacts", "events"}.issubset(tables)
    if os.name == "posix":
        assert stat.S_IMODE(temp_bus.parent.stat().st_mode) & 0o077 == 0
        assert stat.S_IMODE(temp_bus.stat().st_mode) & 0o077 == 0


def test_migrate_returns_not_implemented(temp_bus) -> None:
    assert run_cli("init", "--project", "proj", "--bus", str(temp_bus)).returncode == 0

    result = run_cli("migrate", "--bus", str(temp_bus))

    assert result.returncode == 2
    assert "ERR_NOT_IMPLEMENTED" in result.stderr
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_db_health.py -v
```

Expected: FAIL because DB code and CLI init are not implemented.

- [ ] **Step 3: Implement schema and WAL setup**

Create `agent_comm/db.py` with:

```python
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = 1
BUSY_TIMEOUT_MS = 5000

SCHEMA_SQL = """
create table if not exists agents(
  id text primary key,
  display_name text,
  harness text,
  role text,
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
  message_id text,
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


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _private_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        os.chmod(path.parent, 0o700)


def connect(path: Path) -> sqlite3.Connection:
    _private_parent(path)
    conn = sqlite3.connect(path, timeout=BUSY_TIMEOUT_MS / 1000)
    conn.row_factory = sqlite3.Row
    conn.execute(f"pragma busy_timeout = {BUSY_TIMEOUT_MS}")
    mode = conn.execute("pragma journal_mode = wal").fetchone()[0].lower()
    if mode != "wal":
        conn.close()
        raise RuntimeError(f"unable to enable WAL journal mode for {path}")
    if os.name == "posix" and path.exists():
        os.chmod(path, 0o600)
    return conn


def init_db(path: Path) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.execute(f"pragma user_version = {SCHEMA_VERSION}")


def require_supported_schema(conn: sqlite3.Connection) -> None:
    version = conn.execute("pragma user_version").fetchone()[0]
    if version != SCHEMA_VERSION:
        raise SchemaError(f"unsupported schema version {version}; this CLI supports {SCHEMA_VERSION}")


def require_integrity(conn: sqlite3.Connection) -> None:
    result = conn.execute("pragma integrity_check").fetchone()[0]
    if result != "ok":
        raise RuntimeError(f"database integrity check failed: {result}")


@contextmanager
def immediate_transaction(conn: sqlite3.Connection):
    conn.execute("begin immediate")
    try:
        yield
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()
```

- [ ] **Step 4: Wire init/migrate with `--bus`, `--project`, and `--remote`**

Replace `agent_comm/cli.py` with:

```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .db import init_db
from .paths import resolve_bus_path


def add_bus_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--bus", help="Path to bus.sqlite")
    parser.add_argument("--project", help="Stable project id")
    parser.add_argument("--remote", help="Git remote URL to derive project id")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-comm")
    parser.add_argument("--version", action="version", version=f"agent-comm {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init")
    add_bus_args(init_parser)
    migrate_parser = subparsers.add_parser("migrate")
    add_bus_args(migrate_parser)
    return parser


def bus_path(args: argparse.Namespace) -> Path:
    return resolve_bus_path(bus=args.bus, project=args.project, remote=args.remote)


def _cmd_init(args: argparse.Namespace) -> int:
    path = bus_path(args)
    init_db(path)
    print(path)
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

- [ ] **Step 5: Run tests**

Run:

```bash
python -m pytest tests/test_init_paths.py tests/test_db_health.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add agent_comm tests
git commit -m "feat: initialize sqlite bus safely"
```

## Task 4: Structured Message Headers

**Files:**
- Create: `agent_comm/headers.py`
- Create: `agent_comm/models.py`
- Create: `tests/test_headers.py`

- [ ] **Step 1: Write failing header parser tests**

Create `tests/test_headers.py`:

```python
from __future__ import annotations

import pytest

from agent_comm.headers import HeaderError, parse_message_body


VALID = """Intent: handoff
Requested-Action: implement
Blocking: no
Thread-State: open

# Handoff
Read the linked plan.
"""


def test_parse_valid_header() -> None:
    parsed = parse_message_body(VALID)

    assert parsed.header.intent == "handoff"
    assert parsed.header.requested_action == "implement"
    assert parsed.markdown.startswith("# Handoff")


@pytest.mark.parametrize(
    "body",
    [
        "# Missing header\n",
        "Requested-Action: implement\nIntent: handoff\nBlocking: no\nThread-State: open\n\nBody\n",
        "Intent: typo\nRequested-Action: implement\nBlocking: no\nThread-State: open\n\nBody\n",
        "Intent: handoff\nRequested-Action: implement\nBlocking: maybe\nThread-State: open\n\nBody\n",
        "Intent: handoff\nRequested-Action: implement\nBlocking: no\nThread-State: open\nBody without blank\n",
    ],
)
def test_reject_invalid_header(body: str) -> None:
    with pytest.raises(HeaderError):
        parse_message_body(body)


def test_accept_extension_header() -> None:
    parsed = parse_message_body(
        "Intent: claim\n"
        "Requested-Action: none\n"
        "Blocking: no\n"
        "Thread-State: claimed\n"
        "X-Checkpoint-Due-At: 2026-06-29T12:00:00Z\n"
        "\n"
        "Claiming work.\n"
    )

    assert parsed.header.extensions["X-Checkpoint-Due-At"] == "2026-06-29T12:00:00Z"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_headers.py -v
```

Expected: FAIL because `headers.py` and `models.py` do not exist.

- [ ] **Step 3: Implement models and header parser**

Create `agent_comm/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MessageHeader:
    intent: str
    requested_action: str
    blocking: bool
    thread_state: str
    extensions: dict[str, str]


@dataclass(frozen=True)
class ParsedMessageBody:
    header: MessageHeader | None
    markdown: str
```

Create `agent_comm/headers.py`:

```python
from __future__ import annotations

from .models import MessageHeader, ParsedMessageBody

INTENTS = {
    "handoff", "question", "answer", "defect", "claim", "decision", "plan-amendment",
    "ready-for-review", "review-findings", "fixes-ready", "accepted", "closed", "takeover", "other",
}
REQUESTED_ACTIONS = {"none", "answer", "implement", "review", "fix", "accept", "acknowledge"}
REQUIRED = ("Intent", "Requested-Action", "Blocking", "Thread-State")


class HeaderError(ValueError):
    pass


def parse_message_body(body: str, *, allow_unstructured: bool = False) -> ParsedMessageBody:
    lines = body.splitlines()
    if allow_unstructured:
        try:
            return parse_message_body(body)
        except HeaderError:
            return ParsedMessageBody(None, body)
    if len(lines) < 5:
        raise HeaderError("message body must start with structured header")
    values: dict[str, str] = {}
    idx = 0
    for key in REQUIRED:
        if idx >= len(lines) or not lines[idx].startswith(f"{key}: "):
            raise HeaderError(f"missing or out-of-order header key: {key}")
        if key in values:
            raise HeaderError(f"duplicate header key: {key}")
        values[key] = lines[idx].split(": ", 1)[1].strip()
        idx += 1
    extensions: dict[str, str] = {}
    while idx < len(lines) and lines[idx] != "":
        key, sep, value = lines[idx].partition(": ")
        if sep != ": " or not key.startswith("X-"):
            raise HeaderError("extension headers must use X-* keys")
        if key in extensions:
            raise HeaderError(f"duplicate extension header: {key}")
        extensions[key] = value.strip()
        idx += 1
    if idx >= len(lines) or lines[idx] != "":
        raise HeaderError("message header must be followed by a blank line")
    intent = values["Intent"]
    requested_action = values["Requested-Action"]
    blocking = values["Blocking"]
    if intent not in INTENTS:
        raise HeaderError(f"invalid Intent: {intent}")
    if requested_action not in REQUESTED_ACTIONS:
        raise HeaderError(f"invalid Requested-Action: {requested_action}")
    if blocking not in {"yes", "no"}:
        raise HeaderError("Blocking must be yes or no")
    markdown = "\n".join(lines[idx + 1:])
    if body.endswith("\n"):
        markdown += "\n"
    return ParsedMessageBody(
        MessageHeader(intent, requested_action, blocking == "yes", values["Thread-State"], extensions),
        markdown,
    )
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_headers.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add agent_comm tests/test_headers.py
git commit -m "feat: validate structured message headers"
```

## Task 5: Repository Records, Register, Messages, Replies, Claims, Artifacts

**Files:**
- Create: `agent_comm/ids.py`
- Modify: `agent_comm/models.py`
- Modify: `agent_comm/db.py`
- Create: `tests/test_threads_messages.py`

- [ ] **Step 1: Write failing repository tests**

Create `tests/test_threads_messages.py`:

```python
from __future__ import annotations

import concurrent.futures

import pytest

from agent_comm.db import (
    ack_message,
    add_artifact,
    create_thread,
    get_message,
    init_db,
    inbox,
    post_message,
    register_agent,
)


BODY = """Intent: handoff
Requested-Action: implement
Blocking: no
Thread-State: open

Read docs/handoff.md
"""


def test_register_thread_message_reply_ack_and_artifact(temp_bus) -> None:
    init_db(temp_bus)
    agent = register_agent(temp_bus, agent_id="implementer:codex:a1", role="implementer", harness="codex")
    thread = create_thread(temp_bus, project_id="proj", title="Build thing", owner="planner")
    first = post_message(
        temp_bus,
        thread_id=thread.id,
        from_agent="planner",
        to_agent=agent.id,
        subject="Handoff",
        body_md=BODY,
        priority="normal",
        reply_to=[],
        allow_unstructured=False,
    )
    second = post_message(
        temp_bus,
        thread_id=thread.id,
        from_agent=agent.id,
        to_agent="planner",
        subject="Answer",
        body_md=BODY.replace("Intent: handoff", "Intent: answer").replace("Requested-Action: implement", "Requested-Action: none"),
        priority="normal",
        reply_to=[first.id],
        allow_unstructured=False,
    )

    assert first.seq == 1
    assert second.seq == 2
    assert get_message(temp_bus, second.id).reply_to == [first.id]
    assert inbox(temp_bus, agent_id=agent.id)[0].id == first.id

    ack_message(temp_bus, first.id, agent_id=agent.id)
    assert get_message(temp_bus, first.id).acked_at is not None

    artifact = add_artifact(
        temp_bus,
        thread_id=thread.id,
        message_id=first.id,
        kind="handoff",
        artifact_path="docs/handoff.md",
        git_ref=None,
        description="Approved handoff",
    )
    assert artifact.message_id == first.id


def test_reject_cross_thread_reply_and_artifact_message_mismatch(temp_bus) -> None:
    init_db(temp_bus)
    one = create_thread(temp_bus, project_id="proj", title="One", owner="planner")
    two = create_thread(temp_bus, project_id="proj", title="Two", owner="planner")
    msg = post_message(
        temp_bus,
        thread_id=one.id,
        from_agent="planner",
        to_agent="implementer",
        subject="Handoff",
        body_md=BODY,
        priority="normal",
        reply_to=[],
        allow_unstructured=False,
    )

    with pytest.raises(ValueError, match="same thread"):
        post_message(
            temp_bus,
            thread_id=two.id,
            from_agent="implementer",
            to_agent="planner",
            subject="Bad reply",
            body_md=BODY,
            priority="normal",
            reply_to=[msg.id],
            allow_unstructured=False,
        )
    with pytest.raises(ValueError, match="same thread"):
        add_artifact(
            temp_bus,
            thread_id=two.id,
            message_id=msg.id,
            kind="handoff",
            artifact_path="docs/handoff.md",
            git_ref=None,
            description=None,
        )


def test_concurrent_posts_get_unique_sequences(temp_bus) -> None:
    init_db(temp_bus)
    thread = create_thread(temp_bus, project_id="proj", title="Concurrent", owner="planner")

    def send(i: int) -> int:
        return post_message(
            temp_bus,
            thread_id=thread.id,
            from_agent=f"a{i}",
            to_agent="planner",
            subject=f"M{i}",
            body_md=BODY.replace("Intent: handoff", "Intent: question"),
            priority="normal",
            reply_to=[],
            allow_unstructured=False,
        ).seq

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        seqs = list(pool.map(send, range(20)))

    assert sorted(seqs) == list(range(1, 21))
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_threads_messages.py -v
```

Expected: FAIL because repository functions are missing.

- [ ] **Step 3: Implement ids, records, and repository functions**

Create `agent_comm/ids.py`:

```python
from __future__ import annotations

import uuid


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"
```

Append dataclasses to `agent_comm/models.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentRecord:
    id: str
    role: str
    harness: str
    created_at: str
    last_seen_at: str


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
    header: MessageHeader | None


@dataclass(frozen=True)
class ArtifactRecord:
    id: str
    thread_id: str
    message_id: str | None
    kind: str
    path: str | None
    git_ref: str | None
    description: str | None
    created_at: str
```

Append to `agent_comm/db.py` repository functions using these rules:

```python
# Implement:
# - register_agent(path, agent_id, role, harness)
# - create_thread(path, project_id, title, owner)
# - post_message(path, thread_id, from_agent, to_agent, subject, body_md, priority, reply_to, allow_unstructured)
# - get_message(path, message_id)
# - inbox(path, agent_id)
# - ack_message(path, message_id, agent_id)
# - add_artifact(path, thread_id, message_id, kind, artifact_path, git_ref, description)
#
# Required implementation details:
# - call require_supported_schema() and require_integrity() before mutating commands
# - parse_message_body(body_md, allow_unstructured=allow_unstructured) before insert
# - use immediate_transaction(conn) for post_message sequence allocation and insert
# - validate thread exists before inserting message
# - validate every reply_to message exists and belongs to the same thread
# - validate message_id on artifact exists and belongs to the same thread
# - update threads.updated_at on message/artifact insert
# - ack_message must reject ack by any agent other than to_agent
```

Write complete Python code, not a stub, following the exact behaviors above.

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_threads_messages.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add agent_comm tests/test_threads_messages.py
git commit -m "feat: add coordination records"
```

## Task 6: Core CLI Commands, Header Enforcement, and Artifacts

**Files:**
- Modify: `agent_comm/cli.py`
- Modify: `tests/test_threads_messages.py`

- [ ] **Step 1: Write failing CLI tests**

Append to `tests/test_threads_messages.py`:

```python
from .conftest import run_cli


def test_cli_register_thread_post_rejects_bad_header_and_allows_escape(temp_bus, tmp_path) -> None:
    good = tmp_path / "good.md"
    good.write_text(BODY, encoding="utf-8")
    bad = tmp_path / "bad.md"
    bad.write_text("No header\n", encoding="utf-8")

    run_cli("init", "--project", "proj", "--bus", str(temp_bus), check=True)
    reg = run_cli("register", "--bus", str(temp_bus), "--agent", "implementer:codex:a1", "--role", "implementer", "--harness", "codex", check=True)
    assert "implementer:codex:a1" in reg.stdout
    thread = run_cli("start-thread", "--bus", str(temp_bus), "--project", "proj", "--title", "T", "--owner", "planner", check=True).stdout.strip()

    rejected = run_cli("post", "--bus", str(temp_bus), "--thread", thread, "--from", "planner", "--to", "implementer:codex:a1", "--subject", "Bad", "--body-file", str(bad))
    assert rejected.returncode != 0
    assert "header" in rejected.stderr

    message = run_cli("post", "--bus", str(temp_bus), "--thread", thread, "--from", "planner", "--to", "implementer:codex:a1", "--subject", "Good", "--body-file", str(good), check=True).stdout.strip()
    inbox = run_cli("inbox", "--bus", str(temp_bus), "--agent", "implementer:codex:a1", check=True)
    assert message in inbox.stdout

    artifact = run_cli("artifact", "--bus", str(temp_bus), "add", "--thread", thread, "--message", message, "--kind", "handoff", "--path", str(good), "--description", "Handoff", check=True)
    assert "art_" in artifact.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_threads_messages.py::test_cli_register_thread_post_rejects_bad_header_and_allows_escape -v
```

Expected: FAIL because CLI commands are missing.

- [ ] **Step 3: Wire CLI commands**

Update `agent_comm/cli.py` to include:

```python
# Add subcommands:
# register --agent --role --harness
# start-thread --project --title --owner
# post --thread --from --to --subject --body-file --priority normal --reply-to repeated --allow-unstructured
# inbox --agent
# show MESSAGE_ID
# ack MESSAGE_ID --agent
# artifact add --thread --message optional --kind --path --git-ref --description
#
# All bus-backed commands must include add_bus_args().
# On HeaderError, print a clear error to stderr and return 2.
# On ValueError/PermissionError, print the exception text to stderr and return 2.
```

Write concrete command handlers that call the repository functions from Task 5.

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_threads_messages.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add agent_comm tests/test_threads_messages.py
git commit -m "feat: expose coordination cli commands"
```

## Task 7: Doctor, Backup, Restore, Status, Wait, and Export

**Files:**
- Create: `agent_comm/health.py`
- Create: `agent_comm/export.py`
- Modify: `agent_comm/cli.py`
- Create: `tests/test_cli_status_wait_export.py`
- Modify: `tests/test_db_health.py`

- [ ] **Step 1: Write failing health/export tests**

Append to `tests/test_db_health.py`:

```python
def test_doctor_backup_and_restore(temp_bus, tmp_path) -> None:
    run_cli("init", "--project", "proj", "--bus", str(temp_bus), check=True)
    doctor = run_cli("doctor", "--bus", str(temp_bus), check=True)
    assert "integrity: ok" in doctor.stdout
    assert "journal_mode: wal" in doctor.stdout
    assert "python:" in doctor.stdout
    assert "sqlite:" in doctor.stdout
    assert "permissions:" in doctor.stdout
    assert "wal_support: ok" in doctor.stdout
    assert "bus_location:" in doctor.stdout

    backup = tmp_path / "backup.sqlite"
    result = run_cli("backup", "--bus", str(temp_bus), "--out", str(backup), check=True)
    assert str(backup) in result.stdout
    assert backup.exists()

    restored = tmp_path / "restored.sqlite"
    restore = run_cli("restore", "--bus", str(restored), "--from", str(backup), check=True)
    assert str(restored) in restore.stdout
    assert restored.exists()


def test_restore_refuses_when_exclusive_lock_unavailable(temp_bus, tmp_path) -> None:
    import sqlite3

    run_cli("init", "--project", "proj", "--bus", str(temp_bus), check=True)
    backup = tmp_path / "backup.sqlite"
    run_cli("backup", "--bus", str(temp_bus), "--out", str(backup), check=True)

    conn = sqlite3.connect(temp_bus)
    try:
        conn.execute("begin immediate")
        result = run_cli("restore", "--bus", str(temp_bus), "--from", str(backup))
    finally:
        conn.rollback()
        conn.close()

    assert result.returncode == 2
    assert "ERR_ACTIVE_WRITER" in result.stderr


def test_doctor_reports_corruption_recovery_guidance(tmp_path) -> None:
    corrupt = tmp_path / "corrupt.sqlite"
    corrupt.write_bytes(b"not sqlite")

    result = run_cli("doctor", "--bus", str(corrupt))

    assert result.returncode == 2
    assert "integrity: failed" in result.stdout
    assert "recovery:" in result.stdout
```

Create `tests/test_cli_status_wait_export.py`:

```python
from __future__ import annotations

import subprocess
import sys
import threading
import time

from .conftest import run_cli
from .test_threads_messages import BODY


def _thread_and_message(temp_bus, tmp_path):
    body = tmp_path / "body.md"
    body.write_text(
        BODY.replace("Intent: handoff", "Intent: claim")
        .replace("Requested-Action: implement", "Requested-Action: none")
        .replace("Thread-State: open", "Thread-State: claimed")
        .replace("\n\n", "\nX-Checkpoint-Due-At: 2000-01-01T00:00:00Z\n\n", 1),
        encoding="utf-8",
    )
    run_cli("init", "--project", "proj", "--bus", str(temp_bus), check=True)
    thread = run_cli("start-thread", "--bus", str(temp_bus), "--project", "proj", "--title", "T", "--owner", "planner", check=True).stdout.strip()
    message = run_cli("post", "--bus", str(temp_bus), "--thread", thread, "--from", "implementer", "--to", "planner", "--subject", "Claim", "--body-file", str(body), check=True).stdout.strip()
    return thread, message


def test_status_and_export_include_stale_claim_and_redaction(temp_bus, tmp_path) -> None:
    thread, message = _thread_and_message(temp_bus, tmp_path)

    status = run_cli("status", "--bus", str(temp_bus), "--thread", thread, check=True)
    assert "stale" in status.stdout.lower()
    assert message in status.stdout

    export = run_cli("export", "--bus", str(temp_bus), "--thread", thread, "--redact-body", check=True)
    export_path = export.stdout.strip()
    text = open(export_path, encoding="utf-8").read()
    assert "Stale Claims" in text
    assert "Body redacted" in text


def test_wait_follow_prints_startup_and_message_without_hanging(temp_bus, tmp_path) -> None:
    run_cli("init", "--project", "proj", "--bus", str(temp_bus), check=True)
    thread = run_cli("start-thread", "--bus", str(temp_bus), "--project", "proj", "--title", "T", "--owner", "planner", check=True).stdout.strip()
    body = tmp_path / "body.md"
    body.write_text(BODY, encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "agent_comm", "wait", "--bus", str(temp_bus), "--agent", "implementer", "--follow", "--interval", "0.05"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    lines: list[str] = []

    def reader() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.append(line)

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    try:
        time.sleep(0.2)
        message = run_cli("post", "--bus", str(temp_bus), "--thread", thread, "--from", "planner", "--to", "implementer", "--subject", "Handoff", "--body-file", str(body), check=True).stdout.strip()
        deadline = time.time() + 3
        while time.time() < deadline and message not in "".join(lines):
            time.sleep(0.05)
        output = "".join(lines)
        assert "watching" in output.lower()
        assert message in output
    finally:
        proc.terminate()
        proc.wait(timeout=2)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_db_health.py tests/test_cli_status_wait_export.py -v
```

Expected: FAIL because health/status/export/wait commands are missing.

- [ ] **Step 3: Implement health commands**

Create `agent_comm/health.py`:

```python
from __future__ import annotations

import os
import shutil
import sqlite3
import stat
import sys
from pathlib import Path

from .db import connect, require_integrity
from .paths import bus_inside_git_worktree


def doctor_lines(path: Path) -> list[str]:
    lines = [
        f"bus: {path}",
        f"python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        f"sqlite: {sqlite3.sqlite_version}",
    ]
    try:
        with connect(path) as conn:
            require_integrity(conn)
            version = conn.execute("pragma user_version").fetchone()[0]
            mode = conn.execute("pragma journal_mode").fetchone()[0]
            wal_supported = mode.lower() == "wal"
    except Exception:
        return lines + [
            "integrity: failed",
            "recovery: inspect latest backup/export, run backup from an intact copy, or restore with exclusive access",
        ]

    permissions = "unknown"
    if os.name == "posix" and path.exists():
        file_private = stat.S_IMODE(path.stat().st_mode) & 0o077 == 0
        parent_private = stat.S_IMODE(path.parent.stat().st_mode) & 0o077 == 0
        permissions = "private" if file_private and parent_private else "too-open"
    location = "inside-worktree" if bus_inside_git_worktree(path, Path.cwd()) else "outside-worktree"
    return lines + [
        "integrity: ok",
        f"schema_version: {version}",
        f"journal_mode: {mode}",
        f"wal_support: {'ok' if wal_supported else 'failed'}",
        f"permissions: {permissions}",
        f"bus_location: {location}",
    ]


def backup_db(path: Path, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as src, sqlite3.connect(out) as dest:
        src.backup(dest)
    return out


def restore_db(target: Path, source: Path) -> Path:
    replacement = target.with_suffix(target.suffix + ".restore")
    if replacement.exists():
        replacement.unlink()
    shutil.copy2(source, replacement)
    with connect(replacement) as conn:
        require_integrity(conn)

    lock = sqlite3.connect(target, timeout=0.1)
    try:
        lock.execute("pragma busy_timeout = 100")
        lock.execute("begin exclusive")
        replacement.replace(target)
        lock.commit()
        return target
    except sqlite3.OperationalError as exc:
        raise RuntimeError("ERR_ACTIVE_WRITER: restore requires exclusive access to the bus") from exc
    finally:
        lock.close()
```

This MVP restore implementation validates the replacement and refuses to swap unless it can acquire an exclusive SQLite lock on the target bus. The CLI should map `ERR_ACTIVE_WRITER` to exit code 2.

The `doctor` command must exit non-zero if integrity fails, WAL is unavailable, schema is unsupported, permissions are too open, or the configured bus path is inside a git worktree. When possible, include likely backup/export candidates in the recovery line by scanning the bus directory for recent `*.backup.sqlite` and export files.

- [ ] **Step 4: Implement status/export/wait**

Create `agent_comm/export.py`:

```python
# Implement render_status(db_path, thread_id) -> str
# Implement export_thread(db_path, thread_id, redact_body=False) -> Path
# Required:
# - use one connection/read transaction per render
# - include thread state/owner, unacked messages, artifacts, event timeline, recent messages
# - parse headers and group stale claims using X-Checkpoint-Due-At
# - write export via temp file then Path.replace()
# - redact body when requested
```

Write complete Python code. Add helper queries to `agent_comm/db.py` as needed: `thread_messages`, `thread_artifacts`, `thread_record`.

Update `agent_comm/cli.py`:

```python
# Add:
# doctor
# backup --out
# restore --from
# status --thread
# wait --agent --follow/-f --interval
# export --thread --redact-body
#
# wait --follow must print startup metadata including bus path and process id.
```

- [ ] **Step 5: Run tests**

Run:

```bash
python -m pytest tests/test_db_health.py tests/test_cli_status_wait_export.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add agent_comm tests
git commit -m "feat: add health status wait and export"
```

## Task 8: Skills, Protocol References, Examples

**Files:**
- Create: `skills/coordinate-as-planner/SKILL.md`
- Create: `skills/coordinate-as-planner/references/agent-communication-protocol.md`
- Create: `skills/coordinate-as-implementer/SKILL.md`
- Create: `skills/coordinate-as-implementer/references/agent-communication-protocol.md`
- Create: `examples/planner-handoff.md`
- Create: `examples/implementer-question.md`
- Create: `examples/plan-defect.md`
- Create: `examples/ready-for-review.md`
- Create: `examples/review-findings.md`

- [ ] **Step 1: Create shared protocol reference**

Create both `references/agent-communication-protocol.md` files with identical content covering:

```markdown
# Agent Communication Protocol

Use `agent-comm` only for deliberate cross-agent signals.

## Command Resolution

1. Try `agent-comm --version`.
2. Try `python3 -m agent_comm --version`.
3. Try `python -m agent_comm --version`.
4. On Windows, try `py -3.12 -m agent_comm --version`.
5. Use `uv run agent-comm` only in a development checkout.

## Required Header

Every posted body starts with:

```text
Intent: handoff
Requested-Action: implement
Blocking: yes|no
Thread-State: handoff-ready
```

Use `Intent: claim` before substantial work. Include `X-Checkpoint-Due-At`.
Use `Intent: ready-for-review` or `Intent: fixes-ready` with current worktree, branch/detached state, HEAD SHA, diff/commit summary, verification results, review status, risks, and artifact/log paths.

## Inbox Discipline

Check inbox at start, before ack/claim, after long commands, before commit, before ready/accepted/closed, and before final response.

## Conflict Rule

Stop and send `Intent: question` or `Intent: defect` when chat, messages, artifacts, or current repo state conflict.
```

- [ ] **Step 2: Create planner and implementer skills**

Planner `SKILL.md` must include:

- required frontmatter from the spec
- command resolution ladder
- instruction to run `doctor`
- handoff template with structured header
- claim requirement before treating work as owned
- ready-for-review metadata verification
- review lifecycle and human escalation
- final inbox check before response

Implementer `SKILL.md` must include:

- required frontmatter from the spec
- command resolution ladder
- instruction to register stable agent id
- ack means read only
- claim template with `X-Checkpoint-Due-At`
- defect/question templates
- ready-for-review and fixes-ready templates with required metadata
- contradiction stop rule
- final inbox check before response

- [ ] **Step 3: Create examples with valid headers**

Each example must start with the four required header lines and a blank line.

`examples/planner-handoff.md`:

```markdown
Intent: handoff
Requested-Action: implement
Blocking: no
Thread-State: handoff-ready

# Implementation Handoff

Artifacts:
- Spec: docs/superpowers/specs/2026-06-29-agents-together-design.md
- Plan: docs/superpowers/plans/2026-06-29-agents-together.md
```

`examples/implementer-question.md`, `examples/plan-defect.md`, `examples/ready-for-review.md`, and `examples/review-findings.md` must use `Intent: question`, `Intent: defect`, `Intent: ready-for-review`, and `Intent: review-findings` respectively. The ready-for-review example must include repo/worktree/HEAD metadata and verification results in the body.

- [ ] **Step 4: Validate skills/examples**

Run:

```bash
python - <<'PY'
from pathlib import Path
from agent_comm.headers import parse_message_body

for path in Path("skills").glob("*/SKILL.md"):
    text = path.read_text()
    assert text.startswith("---\n"), path
    assert f"name: {path.parent.name}" in text, path
    assert "description: " in text, path

for path in Path("examples").glob("*.md"):
    parse_message_body(path.read_text())
print("skills and examples ok")
PY
```

Expected: prints `skills and examples ok`.

- [ ] **Step 5: Commit**

Run:

```bash
git add skills examples
git commit -m "feat: add coordination skills and examples"
```

## Task 9: Plugin Manifests and Fresh-Agent Smoke Docs

**Files:**
- Create: `.codex-plugin/plugin.json`
- Create: `.claude-plugin/plugin.json`
- Create: `docs/smoke-tests/fresh-agent-sessions.md`
- Modify: `README.md`

- [ ] **Step 1: Create plugin manifests**

Create `.codex-plugin/plugin.json` and `.claude-plugin/plugin.json`:

```json
{
  "name": "agents-together",
  "version": "0.1.0",
  "description": "Durable local coordination workflows for independent coding agents",
  "skills": "./skills/"
}
```

- [ ] **Step 2: Create smoke-test docs**

Create `docs/smoke-tests/fresh-agent-sessions.md` with:

- Codex local marketplace fixture:

```json
{
  "name": "agents-together-local",
  "interface": { "displayName": "Agents Together Local" },
  "plugins": [
    {
      "name": "agents-together",
      "source": { "source": "local", "path": "./plugins/agents-together" },
      "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" },
      "category": "Productivity"
    }
  ]
}
```

- Claude namespaced invocation examples: `/agents-together:coordinate-as-planner` and `/agents-together:coordinate-as-implementer`; note skills-directory installs may use `/agents-together@skills-dir:...`.
- Shared setup commands using valid structured message bodies.
- Implementer session prompt requiring inbox, show, ack, claim, and reply.
- Planner session prompt requiring inbox, show, and validation of implementer reply.
- Adversarial checklist: missing CLI, Python <3.12, stale watcher restart, two worktrees same remote, multiple implementers, ack-then-crash, stale artifact ref, contradictory artifact/message, worktree mismatch, review rejection, human takeover.

- [ ] **Step 3: Update README validation**

Append:

````markdown
## Validation

```bash
python -m pytest
python -m agent_comm --version
python -m agent_comm init --project agents-together --bus /tmp/agents-together.sqlite
```

Fresh-agent smoke tests are documented in `docs/smoke-tests/fresh-agent-sessions.md`.
````

- [ ] **Step 4: Validate manifests and docs**

Run:

```bash
python -m json.tool .codex-plugin/plugin.json >/tmp/codex-plugin.json
python -m json.tool .claude-plugin/plugin.json >/tmp/claude-plugin.json
rg -n "Intent: " examples docs/smoke-tests/fresh-agent-sessions.md
```

Expected: JSON commands pass and examples/smoke docs contain structured headers.

- [ ] **Step 5: Commit**

Run:

```bash
git add .codex-plugin .claude-plugin docs/smoke-tests README.md
git commit -m "feat: add plugin manifests and smoke tests"
```

## Task 10: Final Verification

**Files:**
- Modify only files needed to fix verification failures.

- [ ] **Step 1: Run full automated tests**

Run:

```bash
python -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 2: Run development workflow**

Run:

```bash
uv run pytest -v
uv run agent-comm --version
```

Expected: all tests PASS and version prints.

- [ ] **Step 3: Run local CLI smoke**

Run:

```bash
python -m agent_comm init --project agents-together --bus /tmp/agents-together-local.sqlite
THREAD_ID=$(python -m agent_comm start-thread --project agents-together --bus /tmp/agents-together-local.sqlite --title "Local smoke" --owner planner)
cat > /tmp/agents-together-local-body.md <<'EOF'
Intent: handoff
Requested-Action: implement
Blocking: no
Thread-State: handoff-ready

Requested action: inspect this local smoke message.
EOF
MSG_ID=$(python -m agent_comm post --bus /tmp/agents-together-local.sqlite --thread "$THREAD_ID" --from planner --to implementer --subject "Local smoke" --body-file /tmp/agents-together-local-body.md)
python -m agent_comm inbox --bus /tmp/agents-together-local.sqlite --agent implementer
python -m agent_comm show --bus /tmp/agents-together-local.sqlite "$MSG_ID"
python -m agent_comm ack --bus /tmp/agents-together-local.sqlite "$MSG_ID" --agent implementer
python -m agent_comm export --bus /tmp/agents-together-local.sqlite --thread "$THREAD_ID"
```

Expected: inbox shows the message before ack, show prints the body, ack succeeds, export prints a Markdown path.

- [ ] **Step 4: Validate no stale type-based CLI returned**

Run:

```bash
rg -n "handoff_ready|implementation_started|plan_defect|code_ready|message type|--type" --glob '!handover.md' --glob '!docs/superpowers/plans/2026-06-29-agents-together.md' .
```

Expected: no matches outside intentionally historical or explanatory text.

- [ ] **Step 5: Commit fixes if verification required changes**

If verification required edits, run:

```bash
git add agent_comm tests skills examples docs README.md pyproject.toml .codex-plugin .claude-plugin
git commit -m "fix: tighten agent comm mvp verification"
```

Expected: commit created only when verification edits were necessary.

## Self-Review Notes

- Spec coverage: storage resolution, schema, WAL/concurrency, permissions, health/backup/restore, structured headers, register, claims, replies, artifacts, status/export, wait/follow, skills, manifests, smoke tests, and final verification are covered.
- Runtime invocation: skills and docs prefer installed `agent-comm`, then Python module invocations, and reserve `uv` for development.
- No daemon: inbox checking and optional `wait --follow` are documented.
- Progress boundary: routine progress remains in project artifacts, not messages.
