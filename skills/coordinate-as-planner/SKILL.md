---
name: coordinate-as-planner
description: Coordinate as the planning agent using agent-comm. Use when preparing implementation handoffs, sending deliberate messages to implementers, answering implementation questions, reviewing ready work, or accepting completed work through a durable local agent mailbox.
---

# Coordinate as Planner

Use this skill when you are acting in the planner role for a task that involves one or more implementation agents. Planner and implementer are roles and conventions, not fixed identities. Agent IDs are arbitrary labels chosen for the current collaboration.

## Command Discovery

Find an available runtime command in this order:

1. If this skill is loaded from an installed plugin, locate the nearest ancestor directory containing `.codex-plugin/plugin.json` and use `<plugin-root>/scripts/agent-comm --version`.
2. `agent-comm --version`
3. `python3.12 -m agent_comm --version`
4. `py -3.12 -m agent_comm --version` for Windows where available
5. `uv run agent-comm --version` for a development checkout only

Use the first command form that works. Runtime instructions should prefer the plugin launcher when available and should not assume `uv`.

## Planner Workflow

At the start of coordination, ensure `agent-comm` is available. Do not inspect CLI help before using the normal workflow; use help only after a command fails. If the shared user-local mailbox is blocked by sandbox permissions, ask the user before using a repo-local mailbox. Check your inbox before sending new instructions so you do not miss prior replies.

Choose `<planner-id>` to include role and worktree, such as `planner-main`. Use a dedicated thread for each coherent task or review stream when continuing existing coordination. Do not rely on chat history as the handoff record.

Use `agent-comm send --as <planner-id> --to <agent-id> "message"` for short messages. Use `--artifact PATH` only when durable project context belongs in a file. Use `--wait` only when blocked on the reply.

Create project-native handoff artifacts when they make the implementation clearer: plans, review notes, test logs, diffs, or other files that belong in the repository. Add artifact links to the mailbox message instead of pasting large context.

Send deliberate addressed messages to implementers. State the requested action, relevant constraints, artifact links, and what kind of reply is useful. Read replies with inbox or next, then acknowledge messages after reading when you are not replying.

Check your inbox at the start of work, at coordination boundaries, before review decisions, and at final coordination points. Answer implementation questions in the thread. If a conflict appears between mailbox messages, repository artifacts, and current user direction, stop and ask for clarification.

See `references/agent-communication-protocol.md` for command-level protocol notes.
