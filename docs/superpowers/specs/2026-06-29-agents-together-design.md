# Agents Together Design

## Purpose

Agents Together is a small, project-agnostic coordination system for independent coding agents running in different harnesses, such as Claude Code, Codex, or Copilot-style sessions.

It provides a durable local mailbox. It does not manage agent runtimes, decide workflow state, store canonical project plans, or replace project artifacts. Its job is to let agents deliberately send addressed messages to each other across separate sessions, branches, worktrees, and tool APIs.

## Design Goals

The MVP should stay small enough that a new harness can use it with only Python, SQLite, and the Agent Skills files.

Core goals:

- Provide durable addressed messages between arbitrary agent ids.
- Make unread/read state reliable across fresh agent sessions.
- Let agents link to project-native artifacts instead of copying project state into the bus.
- Keep the CLI harness-agnostic and usable as `agent-comm` or `python -m agent_comm`.
- Keep SQLite local, versioned, backed up, and recoverable enough for one-machine coordination.
- Keep routine progress, working notes, specifications, plans, review reports, and logs in project files.

Simplicity rules:

- The bus stores communication records; it does not interpret project workflow.
- Agents ask for clarification when instructions conflict; the bus does not decide precedence.
- Message bodies are human/agent-readable Markdown; the CLI does not parse workflow headers or message types.
- Acknowledgement means only "the recipient read this message."
- Status and export summarize stored records; they do not infer ownership, completion, acceptance, or stale work.

## MVP Scope

Build:

- Portable Agent Skills as the canonical user-facing instructions.
- Thin Claude Code and Codex plugin manifests that expose those skills.
- A Python 3.12+ CLI package named `agent-comm`.
- A SQLite-backed local bus stored outside the project worktree by default.
- Threads, addressed messages, replies, acknowledgement, and artifact links.
- Simple inbox, show, wait, status, export, backup, restore, and doctor commands.
- Automated CLI tests and a documented fresh-agent smoke test.

Do not build:

- Scheduler, daemon, or agent runtime manager.
- PR integration.
- External database service.
- Memory, RAG, or semantic search layer.
- Project-specific workflow rules.
- Progress feed, agent scratch state, or project-status tracker.
- CLI-enforced review lifecycle, conflict precedence, claim state, or stale-claim detection.
- DB-level or CLI-level message types.

## Packaging

Agent Skills are the canonical format. Plugin manifests are adapters.

Planned layout:

```text
agents-together/
├── skills/
│   ├── coordinate-as-planner/
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── agent-communication-protocol.md
│   └── coordinate-as-implementer/
│       ├── SKILL.md
│       └── references/
│           └── agent-communication-protocol.md
├── agent_comm/
├── tests/
├── examples/
├── .codex-plugin/
│   └── plugin.json
├── .claude-plugin/
│   └── plugin.json
├── pyproject.toml
└── README.md
```

The skill names are:

- `coordinate-as-planner`
- `coordinate-as-implementer`

These are coordination roles, not fixed identities. Agents still use arbitrary ids such as `planner`, `implementer`, `planner:claude:abc123`, or `implementer:codex:def456`.

Each `SKILL.md` must conform to the Agent Skills specification:

- YAML frontmatter includes `name` and `description`.
- `name` matches the parent directory name.
- `description` is trigger-rich enough for implicit invocation.

Required frontmatter:

```yaml
---
name: coordinate-as-planner
description: Coordinate as the planning agent using agent-comm. Use when preparing implementation handoffs, sending deliberate messages to implementers, answering implementation questions, reviewing ready work, or accepting completed work through a durable local agent mailbox.
---
```

```yaml
---
name: coordinate-as-implementer
description: Coordinate as the implementation agent using agent-comm. Use when receiving planner handoffs, reading durable agent messages, acknowledging work, asking implementation questions, reporting blockers, or signaling ready-for-review work through a local mailbox.
---
```

The shared protocol reference is duplicated under each skill's `references/` directory so each skill remains self-contained across harnesses.

Codex and Claude adapter manifests:

```json
{
  "name": "agents-together",
  "version": "0.1.0",
  "description": "Durable local coordination workflows for independent coding agents",
  "skills": "./skills/"
}
```

Fresh-agent smoke docs must show the actual local install path for each harness. Codex docs should include a local marketplace fixture. Claude docs should include namespaced plugin invocation such as `/agents-together:coordinate-as-planner`, while noting that local skills-directory installs may use a different namespace.

## Storage

By default, the SQLite database lives outside the git worktree:

```text
~/.agent-comm/projects/<project-key>/bus.sqlite
~/.agent-comm/projects/<project-key>/exports/
```

Bus path resolution:

1. Explicit `--bus PATH`.
2. `AGENT_COMM_BUS`.
3. Default path derived from `--project PROJECT_ID`.
4. If `--project` is omitted inside a git repo, default path derived from canonical `origin`.
5. Otherwise fail and ask for `--project` or `--bus`.

Project keys are deterministic safe slugs plus a short stable hash. Canonical git remote handling should treat common SSH and HTTPS forms as equivalent, strip trailing `.git`, normalize host case, and include the hash to avoid slug collisions. Tests must prove that two worktrees with the same canonical remote resolve to the same bus path.

Multiple agents working in different worktrees of the same project use that same shared bus. The bus distinguishes agents by `agent_id`, not by worktree. Worktree paths, branches, HEAD SHAs, and intended edits belong in message bodies or linked artifacts when relevant. The bus is not a lock manager and does not decide which worktree state wins.

This MVP does not use committed `.agent-comm.json` or local `.agent-comm.local.json` pointer files. They can be added later if repeated manual `--project` or `--bus` use becomes painful.

Runtime SQLite state should not be committed by default.

## Schema

The MVP schema uses simple SQLite tables with UTC ISO-8601 timestamps.

```text
agents(
  id text primary key,
  display_name text,
  harness text,
  role text,
  created_at text not null,
  last_seen_at text
);

threads(
  id text primary key,
  project_id text not null,
  title text not null,
  created_at text not null,
  updated_at text not null
);

messages(
  id text primary key,
  thread_id text not null,
  seq integer not null,
  from_agent text not null,
  to_agent text not null,
  subject text not null,
  body_md text not null,
  created_at text not null,
  acked_at text,
  unique(thread_id, seq)
);

message_replies(
  message_id text not null,
  reply_to_message_id text not null,
  primary key(message_id, reply_to_message_id)
);

artifacts(
  id text primary key,
  thread_id text not null,
  message_id text,
  path text,
  git_ref text,
  description text,
  created_at text not null
);
```

MVP deliberately omits an events table. If audit history beyond messages/artifacts is needed later, add it in a migration.

Schema versioning uses `PRAGMA user_version`. MVP creates schema version `1`. Normal commands require version `1`. If the database version is newer than the CLI supports, the CLI fails clearly. `agent-comm migrate` exists in MVP and returns `ERR_NOT_IMPLEMENTED`.

Timestamps are display metadata, not causal ordering. Within a thread, message order is `seq`.

SQLite behavior:

- Enable WAL mode with `PRAGMA journal_mode=WAL`.
- Set `PRAGMA busy_timeout` to a nonzero value such as 5000 ms.
- Keep write transactions short.
- Assign per-thread `seq` inside `BEGIN IMMEDIATE`.
- Verify WAL was enabled; otherwise fail clearly.

Security and recovery:

- Create state directories/files as user-private where supported: POSIX `0700` directories and `0600` DB/export/backup files.
- Document equivalent Windows ACL intent.
- Warn agents not to paste secrets, credentials, private tokens, or large proprietary logs into message bodies.
- Prefer artifact links over copying large or sensitive content into messages.
- Support redacted/bodyless export.
- `doctor` checks only the core local bus health: DB opens, schema version supported, integrity ok, WAL active, and private permissions where supported.
- `backup` uses SQLite's backup API.
- `restore` validates the backup DB first, refuses if it cannot acquire exclusive access to the target bus, and swaps the replacement atomically where supported.

## Protocol

Messages are deliberate cross-agent signals. They are for cases where the recipient needs to notice, decide, act, review, or acknowledge. Routine progress updates and private scratch state do not go through the bus.

The database does not enforce workflow enums. Routing is based on `to_agent` and acknowledgement state. `post --type`, `wait --type`, intent taxonomies, claim state, stale-claim state, and review lifecycle state are out of MVP scope.

Agents should register before participating:

```text
agent-comm register --agent implementer:codex:abc123 --role implementer --harness codex
```

Simple ids such as `planner` and `implementer` are acceptable for one-planner/one-implementer smoke tests. Real multi-agent work should use stable ids. Skills must not assume every session using `implementer` is the same actor.

Message body convention:

- Use Markdown.
- Start with a short requested-action summary in prose, for example `Requested action: review this plan and reply with blockers only.`
- Include links to project artifacts when context is needed.
- Include any workflow-specific labels, deadlines, or handoff details in the body as prose, not as CLI-enforced state.

The CLI stores message bodies as-is. It does not parse required headers or reject unstructured messages.

Messages are immutable. Replies are new messages. A message can reply to zero or more earlier messages in the same thread through `message_replies`. Every reply target must belong to the same thread.

Artifacts are links to external project state. They may be linked to a thread and optionally to a specific message. Message bodies remain the place to explain why an artifact matters.

`acked_at` means the recipient has read the message. It does not mean work was claimed, started, accepted, or completed.

Conflict handling:

- If an agent sees conflicting chat, messages, artifacts, branch/worktree state, or repo state, it stops before acting.
- The agent sends a deliberate question or blocker message to the relevant agent(s), explaining the conflict and asking them to clarify order and intent.
- The bus does not decide which instruction wins.

## CLI

The CLI package exposes `agent-comm`.

During package development, commands may be run with `uv run agent-comm ...`. Agent-facing instructions must not assume `uv` or assume the current working directory is the plugin root.

Runtime command resolution:

1. Prefer installed `agent-comm` on `PATH`; verify with `agent-comm --version`.
2. If installed into the active Python environment, try `python3 -m agent_comm`, then `python -m agent_comm`.
3. On Windows, try `py -3.12 -m agent_comm` when available.
4. In a development checkout only, use `uv run agent-comm`.
5. If none work, stop with setup instructions.

Commands:

```text
agent-comm init --project <project-id>
```

Create or open the shared project bus and initialize schema version `1`.

```text
agent-comm doctor
```

Check core local bus health: schema version, WAL, integrity, and permissions.

```text
agent-comm backup --out <path>
agent-comm restore --from <path>
```

Backup and restore the bus safely.

```text
agent-comm register --agent <agent-id> --role <role> --harness <harness>
```

Register or update a logical agent identity and `last_seen_at`.

```text
agent-comm start-thread --project <project-id> --title "Issue #304 adaptive limiter"
```

Create a collaboration thread. `--project` provides the stored thread `project_id`; it also participates in bus path resolution when `--bus` is not supplied.

```text
agent-comm post \
  --thread <thread-id> \
  --from planner \
  --to implementer \
  --subject "Implementation handoff ready" \
  --body-file docs/handoffs/issue-304.md
```

Send an addressed message. Replies use repeated `--reply-to` flags:

```text
agent-comm post ... --reply-to <message-id> --reply-to <message-id>
```

```text
agent-comm inbox --agent implementer
agent-comm show <message-id>
agent-comm ack <message-id> --agent implementer
```

List unread messages, show a full message, and mark a message read. `ack --agent` must reject acknowledgement by anyone other than the recipient.

```text
agent-comm wait --agent planner
agent-comm wait --agent planner --follow
agent-comm wait --agent planner -f
```

`wait` blocks until at least one unacknowledged message is addressed to the agent, prints a summary, and exits. `--follow` keeps running and prints each newly available unacknowledged message. It does not auto-ack and may reprint still-unacknowledged messages after restart.

```text
agent-comm artifact add \
  --thread <thread-id> \
  --message <message-id> \
  --path docs/handoffs/issue-304.md \
  --description "Approved implementation handoff"
```

Link an external artifact to a thread and optionally to a message.

```text
agent-comm status --thread <thread-id>
agent-comm export --thread <thread-id>
```

Status and export show thread metadata, unread messages, recent messages, replies, and linked artifacts. Export writes Markdown under the bus export directory using a temp file and atomic replace where supported. Export supports redacted/bodyless mode.

```text
agent-comm migrate
```

Return `ERR_NOT_IMPLEMENTED` for MVP.

All bus-backed commands accept common bus selection options: `--bus` and `--project` where relevant.

## Skill Behavior

`coordinate-as-planner`:

- Ensures `agent-comm` is available.
- Resolves or initializes the bus.
- Starts or selects a thread.
- Creates project-native handoff artifacts when useful.
- Sends deliberate messages when an implementer needs to act, answer, review, or acknowledge.
- Reads planner inbox and replies through durable messages.
- Does not rely on chat history as the handoff record.

`coordinate-as-implementer`:

- Ensures `agent-comm` is available.
- Reads implementer inbox for deliberate work signals.
- Uses `show` to inspect message bodies and linked artifacts.
- Acknowledges messages only after reading them.
- Uses project-native artifacts for working notes, status, logs, and evidence.
- Sends questions, blockers, and ready-for-review notices as addressed messages.
- Stops and asks for clarification when instructions or state conflict.

Both skills:

- Treat roles as conventions, not fixed identities.
- Use arbitrary agent ids.
- Prefer artifact links and durable messages over chat assumptions.
- Include concrete message body examples.
- Check inbox at session start, before posting final coordination messages, and at sensible boundaries during long work.

`agent-comm` does not run a daemon. Background `wait --follow` is optional and not required for protocol correctness.

## Testing

CLI tests use temporary bus paths and do not touch the user's home directory. The test suite covers:

- Package help/version.
- `init` creates schema version `1`.
- `doctor` reports core DB health.
- `backup` creates a readable backup via SQLite backup API.
- `restore` validates replacement and refuses active writers.
- Unsupported schema versions fail clearly.
- `migrate` returns `ERR_NOT_IMPLEMENTED`.
- Project-key derivation is stable across worktrees sharing a canonical remote.
- Remote selection handles explicit project id, `origin`, SSH/HTTPS canonicalization, and slug/hash collisions.
- SQLite concurrent posting assigns unique per-thread sequences without uncaught lock errors.
- POSIX file permissions for state directories/files are private where supported.
- Thread creation.
- Message posting with unique ids and per-thread sequence numbers.
- Multiple `--reply-to` links and same-thread validation.
- Inbox listing by recipient.
- Message display.
- Explicit acknowledgement by recipient only.
- `wait` exit behavior.
- `wait --follow` reporting without auto-ack.
- Artifact linking.
- Status and Markdown export, including redacted export.

Fresh-agent smoke testing should prove only the essential workflow:

- Install or expose the plugin to Claude Code and Codex through documented local paths.
- Start one planner session and one implementer session.
- Verify that each skill discovers the CLI.
- Planner posts a handoff message with an artifact link.
- Implementer reads, shows, acks, and replies.
- Planner reads the reply.

Example message bodies must cover:

- planner handoff
- implementer question or blocker
- ready for review
- review findings

## Open Risks

- Claude Code and Codex plugin manifests differ; the shared `skills/` tree must remain the canonical source to prevent drift.
- Shared references may need duplication per skill for maximum portability.
- Fresh-agent smoke testing may require local machine setup outside normal automated tests.
- `wait --follow` is polling-based in MVP.
- WAL mode is appropriate only on local same-host storage; network filesystems may require explicit degraded behavior or refusal later.
- Local message bodies and exports can contain sensitive coordination data; skills must prefer artifact links and avoid secrets.
