---
name: coordinate-as-implementer
description: Coordinate as the implementation agent using agent-comm. Use when receiving planner handoffs, reading durable agent messages, acknowledging work, asking implementation questions, reporting blockers, or signaling ready-for-review work through a local mailbox.
---

# Coordinate as Implementer

Use this skill when you are acting in the implementer role for a task planned or reviewed through `agent-comm`. Planner and implementer are roles and conventions, not fixed identities. Agent IDs are arbitrary labels chosen for the current collaboration.

## Command Discovery

Find an available runtime command in this order:

1. `agent-comm --version`
2. `python3 -m agent_comm --version`
3. `python -m agent_comm --version`
4. `py -3.12 -m agent_comm` for Windows where available
5. `uv run agent-comm` for a development checkout only

Use the first command form that works. Runtime instructions should prefer installed Python or module entry points and should not assume `uv`.

## Implementer Workflow

At the start of work, ensure `agent-comm` is available, then resolve or initialize the bus for the current project. Read your inbox before acting.

Show the full message body before acknowledging it. Acknowledge only after reading the message and any linked artifacts. Use artifact links as the durable source for plans, logs, review notes, and other larger context.

Work in the thread selected by the planner or start a focused thread if you need to initiate coordination. Keep replies in that thread with repeated `--reply-to` use.

Send questions, blockers, and ready-for-review notes as deliberate addressed messages. Include the requested action, what you tried, relevant artifact links, and the specific decision or review you need. Do not rely on chat history as the handoff record.

Check your inbox at the start of work, at implementation boundaries, before final reporting, and at final coordination points. If instructions conflict across mailbox messages, repository artifacts, and current user direction, stop and ask for clarification before proceeding.

See `references/agent-communication-protocol.md` for command-level protocol notes.
