# Agents Together Design

## Purpose

Agents Together is a small, project-agnostic coordination system for independent coding agents running in different harnesses, such as Claude Code, Codex, or Copilot-style sessions.

The system provides a durable local mailbox and thread protocol. It does not manage agent runtimes, store project plans as canonical state, or replace project artifacts. Its job is to let agents deliberately signal each other across separate sessions, branches, worktrees, and tool APIs.

## Scope

Build an MVP with:

- Agent Skills as the canonical portable skill format.
- Thin Claude Code and Codex plugin manifests as harness adapters.
- A Python 3.12+ CLI package. Development uses `uv`, but runtime skill instructions must not assume users have `uv`.
- A SQLite-backed local bus stored outside the project worktree by default.
- Deliberate addressed messages between arbitrary agent ids.
- Artifact links to project-native files, branches, commits, logs, and refs.
- Markdown status exports generated from SQLite.
- Automated CLI tests and documented fresh-agent smoke tests.

Do not build:

- Scheduler or agent runtime manager.
- Background daemon.
- PR integration.
- External database service.
- Memory or RAG layer.
- Trader-specific workflow rules.
- Progress feed or agent scratch state.

## Packaging

Agent Skills are the canonical format. The repo is plugin-shaped from day one, but plugin manifests are adapters rather than the source of truth.

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

These names describe temporary coordination roles without requiring fixed agent identities. The CLI name is `agent-comm`. The repo/plugin name remains `agents-together`.

The shared protocol reference should be present inside each skill's `references/` directory. This duplicates a small document, but keeps each skill self-contained and portable across clients that resolve references relative to the skill root.

## Storage

The canonical SQLite database lives outside the git worktree by default:

```text
~/.agent-comm/projects/<project-key>/bus.sqlite
~/.agent-comm/projects/<project-key>/exports/
```

Resolution order:

1. Explicit `--bus PATH`.
2. `AGENT_COMM_BUS`.
3. Repo pointer config, `.agent-comm.json`.
4. Default path derived from `--project`, git remote, or repository root.

The pointer config may be committed when useful, but runtime SQLite state should not be committed by default.

## Schema

The MVP schema uses simple SQLite tables with UTC ISO-8601 timestamps.

```text
agents(
  id text primary key,
  display_name text,
  harness text,
  created_at text not null,
  last_seen_at text
);

threads(
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

messages(
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

message_replies(
  message_id text not null,
  reply_to_message_id text not null,
  primary key(message_id, reply_to_message_id)
);

artifacts(
  id text primary key,
  thread_id text not null,
  kind text not null,
  path text,
  git_ref text,
  description text,
  created_at text not null
);

events(
  id text primary key,
  thread_id text,
  agent_id text not null,
  event_type text not null,
  payload_json text not null,
  created_at text not null
);
```

`events` is for internal audit of CLI operations. It is not a progress feed and is not a substitute for project artifacts.

Schema versioning uses `PRAGMA user_version`. MVP creates schema version `1`. Normal commands require version `1`. If the database version is newer than the CLI supports, the CLI fails clearly. The `agent-comm migrate` command exists in MVP but returns `ERR_NOT_IMPLEMENTED`.

## Protocol Boundaries

Agent ids, thread owners, artifact kinds, thread statuses, and message priorities are strings. The protocol may recommend values, but the database does not enforce project-specific enums.

Messages are deliberate cross-agent signals. They are for cases where the recipient needs to notice, decide, act, review, or acknowledge. Routine progress updates do not go through the bus.

Project artifacts remain canonical in the project filesystem and git history. Examples include specs, implementation plans, handoff documents, status notes, test logs, review reports, branches, commits, and PR links. Bus messages point to these artifacts when context is needed.

Messages are immutable. Replies are new messages. A message can reply to zero or more earlier messages in the same thread through `message_replies`.

`acked_at` means the recipient has consumed or taken ownership of the message. It does not mean the requested work is complete.

## CLI

The CLI package exposes `agent-comm`.

During package development, commands may be run with `uv run agent-comm ...`.
Agent-facing instructions should use the most portable invocation first:

```text
python -m agent_comm ...
```

If the package has been installed into the active environment, agents may use:

```text
agent-comm ...
```

Skills should resolve the command in this order:

1. `python -m agent_comm` from the plugin/repo root or active environment.
2. `agent-comm` if it is available on `PATH`.
3. `uv run agent-comm` only when working inside the development checkout and `uv` is available.

```text
agent-comm init --project <project-id>
```

Create or open the shared project bus, initialize schema version `1`, and optionally write `.agent-comm.json`.

```text
agent-comm start-thread \
  --title "Issue #304 adaptive limiter" \
  --owner planner
```

Create a collaboration thread. `owner` is arbitrary text.

```text
agent-comm post \
  --thread <thread-id> \
  --from planner \
  --to implementer \
  --subject "Implementation handoff ready" \
  --body-file docs/handoffs/issue-304.md
```

Send a deliberate addressed message. The body must be self-describing and should link to project artifacts.

Replies use repeated `--reply-to` flags:

```text
agent-comm post ... --reply-to <message-id> --reply-to <message-id>
```

```text
agent-comm inbox --agent implementer
```

List unacknowledged messages addressed to an agent.

```text
agent-comm show <message-id>
```

Print full message metadata and body.

```text
agent-comm ack <message-id> --agent implementer
```

Mark a message acknowledged. `--agent` prevents accidental acknowledgement by the wrong recipient.

```text
agent-comm wait --agent planner
agent-comm wait --agent planner --follow
agent-comm wait --agent planner -f
```

`wait` blocks until at least one unacknowledged message is addressed to the agent, prints a summary, and exits. `--follow` keeps running and prints each newly available unacknowledged message. It does not auto-ack. It tracks messages printed during the current process to avoid repeated output, but a restarted process may print still-unacknowledged messages again.

```text
agent-comm artifact add \
  --thread <thread-id> \
  --kind handoff \
  --path docs/handoffs/issue-304.md \
  --description "Approved implementation handoff"
```

Link an external project artifact to a thread.

```text
agent-comm status --thread <thread-id>
```

Show thread metadata, unacknowledged messages, recent messages, and linked artifacts. This is coordination status, not project progress tracking.

```text
agent-comm export --thread <thread-id>
```

Generate a Markdown export under the project bus export directory.

```text
agent-comm migrate
```

Return `ERR_NOT_IMPLEMENTED` for MVP.

## Skill Behavior

`coordinate-as-planner`:

- Ensures `agent-comm` is available.
- Resolves or initializes the bus.
- Starts or selects a thread.
- Produces project-native handoff artifacts with approved plan/spec paths and acceptance criteria.
- Posts deliberate messages to the implementer when action, review, or acknowledgement is needed.
- Reads planner inbox and responds through durable messages when decisions, plan amendments, review findings, or acceptance are needed.
- Does not rely on chat history as the handoff.

`coordinate-as-implementer`:

- Ensures `agent-comm` is available.
- Reads implementer inbox for deliberate work signals.
- Uses `show` to inspect message bodies and linked artifacts.
- Acknowledges messages only after consuming enough to act.
- Implements independently using project-native artifacts for working notes, status, logs, and evidence.
- Posts questions, defects, ready-for-review notices, or completion signals as deliberate messages.
- Reports plan defects instead of silently patching around contradictory, unsafe, untestable, or wrong instructions.

Both skills:

- Treat roles as conventions, not fixed identities.
- Use arbitrary agent ids.
- Prefer artifact links and durable messages over chat assumptions.
- Include concrete message body examples.

Inbox checking is the responsibility of the active agent/session. `agent-comm` does not run a daemon. Skills should instruct agents to check their inbox at natural coordination points and, for implementers, periodically during longer work. If a harness supports a background monitor, the agent may run `python -m agent_comm wait --agent <agent-id> --follow`, but background monitoring is optional and not required for protocol correctness.

## Testing

CLI tests use temporary bus paths and do not touch the user's home directory. The test suite covers:

- `init` creates schema version `1`.
- Commands reject unsupported schema versions.
- `migrate` returns `ERR_NOT_IMPLEMENTED`.
- Thread creation.
- Message posting with unique ids and per-thread sequence numbers.
- Multiple `--reply-to` links.
- Inbox listing by recipient.
- Message display.
- Explicit acknowledgement.
- `wait` exit behavior.
- `wait --follow` reporting without auto-ack.
- Artifact linking.
- Markdown export.

Skill testing uses real fresh agent sessions where available:

- Install or expose the plugin to Claude Code through a skills-directory plugin.
- Install or expose the plugin to Codex through a local marketplace or local plugin path.
- Start one planner session and one implementer session.
- Verify that each skill can discover the CLI, exchange messages, link artifacts, and follow the deliberate-message boundary.

## Open Risks

- Claude Code and Codex plugin manifests differ; the shared `skills/` tree must remain the canonical source to prevent drift.
- Shared references may need duplication per skill for maximum portability.
- Fresh-agent smoke testing may require local machine setup outside normal automated tests.
- `wait --follow` is polling-based in MVP. It is simple and portable, but not as efficient as filesystem notifications or a daemon.
