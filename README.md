# Switchboard

Switchboard is a local mailbox for deliberate coordination between independent
coding agents working in separate sessions, worktrees, or harnesses.

It is intentionally small. Switchboard stores addressed messages, replies,
acknowledgements, and artifact links through SQLite. Plans, review notes, logs,
large context, and project decisions stay in normal project files, where the
repository can review and version them.

## What It Is

- A local CLI for sending explicit handoffs between agents.
- A durable SQLite mailbox for addressed messages and replies.
- A lightweight way to link project artifacts from mailbox messages.
- A coordination tool for humans and agents sharing one project.

## What It Is Not

- A task tracker, scheduler, workflow engine, or chat room.
- A replacement for plans, design notes, review docs, or logs.
- A place to paste secrets, credentials, private tokens, or large proprietary
  context.
- A network service or hosted collaboration platform.

## Quick Start

Send a handoff:

```sh
switchboard send --as planner-main --to implementer-feature-a --title "Review plan" "Please review the plan and reply with blockers."
```

Read the next addressed message:

```sh
switchboard next --as implementer-feature-a
```

Reply to a message:

```sh
switchboard reply <message-id> --as implementer-feature-a "No blockers."
```

Check an inbox:

```sh
switchboard inbox --as planner-main
```

By default, Switchboard stores each project mailbox at:

```text
~/.switchboard/projects/<project-key>/bus.sqlite
```

Linked worktrees for the same project share one mailbox. There is no repo-local
fallback mailbox.

## Runtime Commands

```sh
switchboard --help
python3.12 -m switchboard --help
```

## Development Commands

Use `uv` from a development checkout:

```sh
uv run --python 3.12 pytest -q
uv run --python 3.12 python scripts/validate_skill_protocols.py
uv run --python 3.12 switchboard --help
```

## Smoke Test

See the fresh-agent smoke test guide:

```text
docs/smoke-tests/fresh-agent-sessions.md
```
