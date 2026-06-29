# Switchboard

Switchboard is a local mailbox for coding agents that need to work together
without sharing one chat session. It is built for running agents side by side:
for example, a Claude session planning or reviewing work while a Codex session
implements it, or two agents in separate worktrees coordinating a handoff.

The mailbox is deliberately narrow. Agents send addressed messages, replies,
acknowledgements, and links to project artifacts through a shared SQLite file.
The actual plan, review notes, logs, and larger context stay in normal project
files where they can be edited, reviewed, and versioned.

## What It Is

- A local CLI for explicit agent-to-agent handoffs.
- A durable SQLite mailbox shared by agents working on the same project.
- A small protocol for questions, replies, acknowledgements, and review
  handoffs.
- Plugin manifests and Agent Skills for Claude and Codex-style harnesses.

## What It Is Not

- A task tracker, scheduler, workflow engine, or chat room.
- A replacement for plans, design notes, review docs, or logs.
- A place to paste secrets, credentials, private tokens, or large proprietary
  context.
- A network service or hosted collaboration platform.

## Quick Start

Planner sends a handoff:

```sh
switchboard send --as planner-main --to implementer-feature-a --title "Review plan" "Please review the plan and reply with blockers."
```

Implementer reads the next addressed message:

```sh
switchboard next --as implementer-feature-a
```

Implementer replies:

```sh
switchboard reply <message-id> --as implementer-feature-a "No blockers."
```

Planner checks for the reply:

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

See the [fresh-agent smoke test guide](docs/smoke-tests/fresh-agent-sessions.md).

## Agent Guidance

See [AGENTS.md](AGENTS.md) for the canonical external specifications and project
principles used when changing skills, manifests, marketplaces, or coordination
behavior.
