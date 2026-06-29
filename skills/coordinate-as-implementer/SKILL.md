---
name: coordinate-as-implementer
description: Coordinate as the implementation agent using agent-comm. Use when receiving planner handoffs, reading durable agent messages, acknowledging work, asking implementation questions, reporting blockers, or signaling ready-for-review work through a local mailbox.
---

# Coordinate as Implementer

Use this skill when you are acting in the implementer role for a task planned or reviewed through `agent-comm`. Planner and implementer are roles and conventions, not fixed identities. Agent IDs are arbitrary labels chosen for the current collaboration.

## Command Discovery

Find an available runtime command in this order:

1. If this skill is loaded from an installed plugin, locate the nearest ancestor directory containing `.codex-plugin/plugin.json` and use `<plugin-root>/scripts/agent-comm --version`.
2. `agent-comm --version`
3. `python3.12 -m agent_comm --version`
4. `python3 -m agent_comm --version`
5. `python -m agent_comm --version`
6. `py -3.12 -m agent_comm --version` for Windows where available
7. `uv run agent-comm --version` for a development checkout only

Use the first command form that works. Runtime instructions should prefer the plugin launcher when available and should not assume `uv`.

## Implementer Workflow

At the start of work, ensure `agent-comm` is available. Do not inspect CLI help before using the normal workflow; use help only after a command fails. If the shared user-local mailbox is blocked by sandbox permissions, ask the user before using a repo-local mailbox. Read your inbox before acting.

Choose `<implementer-id>` to include role and worktree, such as `implementer-feature-a`. Use `agent-comm next --as <implementer-id>` to read the next unread message.

Read the full message body and any linked artifacts before acting. Use `agent-comm reply <message-id> --as <implementer-id> "message"` to answer; reply automatically acknowledges the message. Use `agent-comm ack --as <implementer-id> <message-id>` only when you read without replying. Use artifact links as the durable source for plans, logs, review notes, and other larger context.

Work in the thread selected by the planner or start a focused thread if you need to initiate coordination.

Send questions, blockers, and ready-for-review notes as deliberate addressed messages. Include the requested action, what you tried, relevant artifact links, and the specific decision or review you need. Do not rely on chat history as the handoff record.

Check your inbox at the start of work, at implementation boundaries, before final reporting, and at final coordination points. If instructions conflict across mailbox messages, repository artifacts, and current user direction, stop and ask for clarification before proceeding.

See `references/agent-communication-protocol.md` for command-level protocol notes.
