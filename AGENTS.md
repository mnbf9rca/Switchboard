# Agent Guidance

This repository follows external plugin and skill specifications rather than
local conventions invented ad hoc. When changing skills, plugin manifests, or
marketplace files, check the canonical references first:

- Agent Skills specification: https://agentskills.io/specification.md
- Claude plugin marketplaces: https://code.claude.com/docs/en/plugin-marketplaces.md
- Claude plugin reference and manifest schema: https://code.claude.com/docs/en/plugins-reference.md

## Project Purpose

Switchboard lets independent coding agents coordinate deliberately while they
work side by side on the same project. A typical use case is one Claude session
and one Codex session sharing a local mailbox so a planner can hand work to an
implementer, an implementer can ask a focused question, or a reviewer can return
findings without relying on chat history.

Switchboard is not a workflow engine, task tracker, chat room, progress log, or
agent memory system. Durable plans, review notes, logs, and large context belong
in normal project files. Switchboard messages should be short, addressed, and
intentional.

## Core Principles

- Keep the tool stateless: each command is a query or mutation over the SQLite
  mailbox.
- Keep agent messages deliberate: progress updates belong in project artifacts,
  not in the mailbox.
- Keep the CLI small: prefer `send`, `reply`, `next`, `inbox`, `show`, `ack`,
  and `wait` over role-specific command variants.
- Keep storage user-local by default: do not fall back to repo-local mailboxes.
- Keep project identity automatic: agents should not need to pass a project name
  for normal use.
- Keep compatibility explicit: this pre-release package does not preserve old
  `agent-comm` or `agent_comm` aliases.
- Keep plugin packaging source-owned: this repository root is the plugin source
  for local marketplaces; do not add generated plugin copies.

## Development Notes

- Python runtime target is 3.12.
- Development uses `uv`; installed agents invoke the packaged script or
  `python3.12 -m switchboard`.
- The two skill protocol reference files must remain byte-identical. Run:

```sh
uv run --python 3.12 python scripts/validate_skill_protocols.py
```

- Run the test suite before claiming completion:

```sh
uv run --python 3.12 pytest -q
```
