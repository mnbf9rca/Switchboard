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
- Basic health, backup, and privacy safeguards for local coordination state.
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

Each `SKILL.md` must conform to the Agent Skills specification:

- YAML frontmatter must include `name` and `description`.
- `name` must match the parent directory name.
- `description` must be trigger-rich enough for implicit invocation.

Required frontmatter:

```yaml
---
name: coordinate-as-planner
description: Coordinate as the planning agent using agent-comm. Use when preparing implementation handoffs, sending deliberate messages to implementers, answering implementation questions, reviewing ready work, or accepting/rejecting completed work through a durable local agent mailbox.
---
```

```yaml
---
name: coordinate-as-implementer
description: Coordinate as the implementation agent using agent-comm. Use when receiving planner handoffs, reading durable agent messages, acknowledging work, asking implementation questions, reporting plan defects, or signaling ready-for-review work through a local mailbox.
---
```

The shared protocol reference should be present inside each skill's `references/` directory. This duplicates a small document, but keeps each skill self-contained and portable across clients that resolve references relative to the skill root.

Codex adapter manifest:

```json
{
  "name": "agents-together",
  "version": "0.1.0",
  "description": "Durable local coordination workflows for independent coding agents",
  "skills": "./skills/"
}
```

Claude Code adapter manifest:

```json
{
  "name": "agents-together",
  "version": "0.1.0",
  "description": "Durable local coordination workflows for independent coding agents",
  "skills": "./skills/"
}
```

Fresh-agent smoke tests must cover the actual local install paths for each harness. Codex tests should use a local marketplace fixture, for example `~/.agents/plugins/marketplace.json` or `$REPO_ROOT/.agents/plugins/marketplace.json`, with a `plugins[]` entry whose `source.path` is `./`-prefixed and relative to the marketplace root:

```json
{
  "name": "agents-together-local",
  "interface": {
    "displayName": "Agents Together Local"
  },
  "plugins": [
    {
      "name": "agents-together",
      "source": {
        "source": "local",
        "path": "./plugins/agents-together"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

Claude tests should cover either a skills-directory plugin or a local marketplace install, and should invoke the namespaced plugin skill form, for example `/agents-together:coordinate-as-planner`; skills-directory installs may expose a namespace such as `/agents-together@skills-dir:coordinate-as-planner`.

## Storage

The canonical SQLite database lives outside the git worktree by default:

```text
~/.agent-comm/projects/<project-key>/bus.sqlite
~/.agent-comm/projects/<project-key>/exports/
```

Resolution order:

1. Explicit `--bus PATH`.
2. `AGENT_COMM_BUS`.
3. Local pointer config, `.agent-comm.local.json`.
4. Repo project config `.agent-comm.json`, which supplies only `project_id`.
5. Default path derived from `--project`, canonical git remote, or repository root.

Project key derivation must be deterministic across worktrees:

1. If `--project` is supplied, use it as the project id.
2. Otherwise, if `.agent-comm.json` contains `project_id`, use that value.
3. Otherwise, if `--remote` is supplied, canonicalize that remote.
4. Otherwise, canonicalize `origin` when it exists.
5. Otherwise, if exactly one git remote exists, canonicalize it.
6. Otherwise, fail and ask for `agent-comm init --project`.
7. Outside a git repo, use the resolved current directory plus a stable hash only when the user explicitly confirms or supplies `--project`.

Canonicalization must treat common SSH and HTTPS forms as equivalent, strip trailing `.git`, normalize host case, handle default ports, and include a hash of the canonical id to avoid slug collisions.

The filesystem directory should be a safe slug plus a short stable hash, not a raw project id. Tests must prove that two worktrees with the same canonical remote resolve to the same bus path.

Committed pointer config schema:

```json
{
  "project_id": "github.com/example/project"
}
```

Local pointer config schema:

```json
{
  "bus": "~/.agent-comm/projects/github.com-example-project-<hash>/bus.sqlite"
}
```

Committed `.agent-comm.json` may contain only portable project identity. Local path overrides belong in `.agent-comm.local.json`, environment variables, or CLI flags. `.agent-comm.local.json` must be gitignored. If `bus` appears in a tracked config, the CLI must refuse to use it unless an explicit override such as `--allow-committed-bus` is supplied. The CLI must warn when a configured bus path resolves inside a git worktree.

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
  message_id text,
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

Timestamps are timezone-aware UTC display metadata, not causal ordering. Within a thread, message order is `seq`. Cross-thread displays may sort by timestamp, but they must tolerate clock skew and should include ids and sequence numbers where available.

SQLite connection behavior:

- Enable WAL mode with `PRAGMA journal_mode=WAL` for same-host reader/writer behavior.
- Set `PRAGMA busy_timeout` to a nonzero value such as 5000 ms.
- Keep write transactions short.
- Assign per-thread `seq` inside a write transaction using `BEGIN IMMEDIATE` around `max(seq)+1` and insert.
- Add a concurrent posting test proving unique sequence assignment and no uncaught `database is locked` errors under multiple writers.
- WAL requires local same-host storage. The CLI must verify that `PRAGMA journal_mode=WAL` actually returns `wal`. If it cannot enable WAL, it must fail with a clear diagnostic unless the user explicitly chooses a degraded journal mode. The CLI should warn for obvious network-mounted or synced storage locations when they can be detected.

Security and file permissions:

- Create agent-comm state directories as user-private where supported: POSIX `0700` directories and `0600` DB/export/backup files.
- Document equivalent Windows ACL intent.
- Warn agents not to paste secrets, credentials, private tokens, or large proprietary logs into message bodies.
- Message bodies should link to controlled project artifacts instead of duplicating sensitive content.
- Exports should support a redacted/bodyless mode so agents can share coordination summaries without full message bodies.

Corruption and recovery behavior:

- If `PRAGMA integrity_check` fails or SQLite reports corruption/malformed pages, normal mutating commands must refuse to run.
- `doctor` must report the failing bus path, likely recovery steps, and latest backup/export candidates if discoverable.
- No command may auto-repair or overwrite a corrupt bus except explicit `restore`.
- `restore` must refuse unless it can acquire an exclusive lock or otherwise prove no active writer is using the bus.
- Restore writes to a replacement path first, validates schema and integrity, then atomically swaps where supported.

## Protocol Boundaries

Agent ids, thread owners, artifact kinds, thread statuses, and message priorities are strings. The protocol may recommend values, but the database does not enforce project-specific enums.

Agents should register before participating:

```text
agent-comm register --agent implementer:codex:abc123 --role implementer --harness codex
```

Simple role aliases such as `planner` and `implementer` are acceptable for one-planner/one-implementer smoke tests. Real multi-agent work should use stable ids such as `implementer:<harness>:<shortid>`. Skills must not assume every session using `implementer` is the same actor. Taking over work from another agent requires a deliberate takeover/claim message.

Messages are deliberate cross-agent signals. They are for cases where the recipient needs to notice, decide, act, review, or acknowledge. Routine progress updates do not go through the bus.

The MVP intentionally does not require DB-level message-type routing. This supersedes the typed-message vocabulary in the original handover. Routing is based on `to_agent` and acknowledgement state. `wait --types` and `post --type` are out of MVP scope.

Every message body must start with a small structured header so agents do not have to infer critical intent from prose:

```text
Intent: handoff | question | answer | defect | claim | decision | plan-amendment | ready-for-review | review-findings | fixes-ready | accepted | closed | takeover | other
Requested-Action: none | answer | implement | review | fix | accept | acknowledge
Blocking: yes | no
Thread-State: optional short state label
```

The header is not an enum in SQLite. It is a required body convention enforced by skills and by `agent-comm post`.

Header grammar:

- The first four non-empty lines must be `Intent`, `Requested-Action`, `Blocking`, and `Thread-State` in that exact order.
- Header keys are case-sensitive.
- Required keys may appear only once.
- One blank line must separate the header from the Markdown body.
- Unknown required-key values are invalid.
- Extra extension headers must be prefixed with `X-` and appear after the required keys, before the blank separator.
- `agent-comm post` rejects missing or malformed headers by default.
- `--allow-unstructured` is the explicit escape hatch; such messages appear in an “unclassified messages” section in status/export.

Status/export summaries must parse these headers rather than scan arbitrary prose.

Project artifacts remain canonical in the project filesystem and git history. Examples include specs, implementation plans, handoff documents, status notes, test logs, review reports, branches, commits, and PR links. Bus messages point to these artifacts when context is needed.

Messages are immutable. Replies are new messages. A message can reply to zero or more earlier messages in the same thread through `message_replies`.

Artifacts may be linked to a thread and optionally to a specific message. Message bodies remain the canonical place to explain why an artifact matters; artifact rows make important files and refs discoverable in status/export views.

`acked_at` means the recipient has read the message. It does not mean work was claimed, started, or completed. For action messages, the recipient must post a separate `Intent: claim` reply before starting substantial work. A claim body must include agent id, repo root, git common dir, worktree path, branch or detached state, HEAD SHA, and `Checkpoint-Due-At: <UTC ISO-8601>` as an extension header. `status` and `export` must surface stale claims when no follow-up message appears after that timestamp.

Every `Intent: ready-for-review` or `Intent: fixes-ready` message must include current repo root, git common dir, worktree path, branch/detached state, HEAD SHA, diff or commit summary, verification commands/results, review status, known risks, and artifact/log paths.

Conflict precedence:

1. Latest durable message with `Intent: decision`, `Intent: accepted`, `Intent: closed`, or `Intent: takeover` wins for coordination state.
2. Referenced project artifacts are canonical for detailed technical content at the referenced path/ref.
3. Newer plan-amendment or decision messages supersede older handoff text.
4. Casual chat is non-authoritative unless captured in a durable message or artifact.
5. If a message, artifact, and current workspace conflict, skills must stop and post a `question` or `defect` message instead of guessing.

Review lifecycle:

```text
ready-for-review -> review-findings -> claim/fix -> ready-for-review -> accepted -> closed
```

The planner, a named reviewer, or `human` may post review findings. The planner or `human` closes the thread unless a thread explicitly delegates closure. Repeated review failures, disputed findings, stale claims, or ownership confusion should be escalated to `human`.

## CLI

The CLI package exposes `agent-comm`.

During package development, commands may be run with `uv run agent-comm ...`.
Agent-facing instructions must not assume `uv`, and must not assume the agent's current working directory is the plugin root.

Runtime command resolution:

1. Prefer installed `agent-comm` on `PATH`; verify with `agent-comm --version`.
2. If the package is installed into the active Python environment, try `python3 -m agent_comm`, then `python -m agent_comm`.
3. On Windows, try `py -3.12 -m agent_comm` when the Python launcher is available.
4. In a development checkout only, use `uv run agent-comm`.
5. If none of these work, stop with explicit setup instructions rather than guessing a plugin cache path.

Portable invocation after installation:

```text
python -m agent_comm ...
```

Installed console script invocation:

```text
agent-comm ...
```

```text
agent-comm init --project <project-id>
```

Create or open the shared project bus, initialize schema version `1`, and optionally write `.agent-comm.json`.

```text
agent-comm doctor
```

Check CLI availability, Python version, SQLite version, schema version, WAL support, DB integrity, file permissions, bus location, and whether configured paths point inside a git worktree.

```text
agent-comm backup --out <path>
```

Create a SQLite backup using SQLite's backup API, not raw file copying. Raw copying is unsafe in WAL mode because the DB, WAL, and shared-memory files can represent one logical state.

```text
agent-comm restore --from <path>
```

Restore from a backup after confirming the target bus path. Restore must refuse unless it can acquire an exclusive lock or otherwise prove no active writer is using the bus.

```text
agent-comm register --agent <agent-id> --role <role> --harness <harness>
```

Register or update a stable logical agent identity and `last_seen_at`.

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

Every `--reply-to` message must belong to the same thread as the new message.

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

`wait --follow` must avoid long read transactions. On start it should print process metadata and the bus path. A future `--state-file` or `--since-seq` option may reduce duplicate output across restarts; MVP documentation must make duplicate output after restart explicit and harmless because ack remains the durable boundary.

```text
agent-comm artifact add \
  --thread <thread-id> \
  --message <message-id> \
  --kind handoff \
  --path docs/handoffs/issue-304.md \
  --description "Approved implementation handoff"
```

Link an external project artifact to a thread and optionally to a message.

```text
agent-comm status --thread <thread-id>
```

Show thread metadata, unacknowledged messages, recent messages, and linked artifacts. This is coordination status, not project progress tracking.

```text
agent-comm export --thread <thread-id>
```

Generate a Markdown export under the project bus export directory.

Exports must include:

- thread state and owner
- latest unacknowledged messages
- linked artifacts
- event timeline
- recent message timeline
- active claims and stale claims
- sections summarizing open questions, defects, ready-for-review signals, review findings, decisions, accepted work, and closures by parsing structured message headers

Exports must be generated from a consistent read transaction. Write exports to a temporary file in the export directory, flush where practical, then atomically replace the destination. Export should offer a redacted/bodyless mode.

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
- Requires claim messages before treating implementation work as owned.
- Verifies branch/worktree/HEAD metadata from ready-for-review messages before accepting.
- Does not rely on chat history as the handoff.

`coordinate-as-implementer`:

- Ensures `agent-comm` is available.
- Reads implementer inbox for deliberate work signals.
- Uses `show` to inspect message bodies and linked artifacts.
- Acknowledges messages only after reading them.
- Posts a `claim` reply before starting substantial work, including agent id, repo root, git common dir, worktree path, branch/detached state, HEAD SHA, and `Checkpoint-Due-At`.
- Implements independently using project-native artifacts for working notes, status, logs, and evidence.
- Posts questions, defects, ready-for-review notices, or completion signals as deliberate messages.
- Reports plan defects instead of silently patching around contradictory, unsafe, untestable, or wrong instructions.
- Checks that the current checkout still matches the claimed thread/worktree before committing, reviewing, or posting ready-for-review.

Both skills:

- Treat roles as conventions, not fixed identities.
- Use arbitrary agent ids.
- Prefer artifact links and durable messages over chat assumptions.
- Include concrete message body examples.
- Require structured message headers.
- Stop on contradictions between chat, messages, artifacts, branch/worktree, or current repo state.

Inbox checking is the responsibility of the active agent/session. `agent-comm` does not run a daemon. Skills must instruct agents to check their inbox:

- at session start
- before acking or claiming work
- after long-running commands
- before committing
- before posting ready-for-review, accepted, or closed messages
- before final user-facing responses

If work is expected to exceed a documented threshold, the agent should either use `wait --follow`, post a checkpoint/claim with the next expected check-in, or tell the other agent when to check back. Background monitoring is optional and not required for protocol correctness.

## Testing

CLI tests use temporary bus paths and do not touch the user's home directory. The test suite covers:

- `init` creates schema version `1`.
- `doctor` reports schema, WAL, permissions, and path health.
- `backup` uses SQLite backup behavior and creates a readable backup.
- Commands reject unsupported schema versions.
- `migrate` returns `ERR_NOT_IMPLEMENTED`.
- Project-key derivation is stable across worktrees sharing a canonical remote.
- Remote selection handles explicit project id, `origin`, ambiguous multi-remote failure, SSH/HTTPS canonicalization, and slug/hash collisions.
- SQLite concurrent posting assigns unique per-thread sequences without uncaught lock errors.
- POSIX file permissions for state directories/files are private where supported.
- Export writes are atomic enough that concurrent readers never see truncated Markdown.
- Timestamp display does not control message ordering; per-thread ordering uses `seq`.
- Thread creation.
- Message posting with unique ids and per-thread sequence numbers.
- Multiple `--reply-to` links.
- Structured header rejection by default, with `--allow-unstructured` escape hatch.
- `--reply-to` same-thread validation.
- Inbox listing by recipient.
- Message display.
- Explicit acknowledgement.
- Claim replies and stale-claim reporting.
- `wait` exit behavior.
- `wait --follow` reporting without auto-ack.
- Artifact linking.
- Markdown export.

Skill testing uses real fresh agent sessions where available:

- Install or expose the plugin to Claude Code through a skills-directory plugin.
- Install or expose the plugin to Codex through the local marketplace fixture.
- Start one planner session and one implementer session.
- Verify that each skill can discover the CLI, exchange messages, link artifacts, and follow the deliberate-message boundary.
- Cover clean temporary HOME, missing CLI, Python below 3.12, older DB schema, plugin update/reinstall, two worktrees with the same remote, stale watcher restart, multiple implementers, ack-then-crash, stale artifact ref, contradictory artifact/message instructions, worktree mismatch, review rejection, and human takeover where the harness makes those cases practical.

Example message bodies must cover:

- planner handoff
- implementer question
- plan defect
- ready for review
- review findings

## Open Risks

- Claude Code and Codex plugin manifests differ; the shared `skills/` tree must remain the canonical source to prevent drift.
- Shared references may need duplication per skill for maximum portability.
- Fresh-agent smoke testing may require local machine setup outside normal automated tests.
- `wait --follow` is polling-based in MVP. It is simple and portable, but not as efficient as filesystem notifications or a daemon.
- WAL mode is appropriate only on local same-host storage; network filesystems require explicit degraded behavior or refusal.
- Local message bodies and exports can contain sensitive coordination data; skills must prefer artifact links and avoid secrets.
