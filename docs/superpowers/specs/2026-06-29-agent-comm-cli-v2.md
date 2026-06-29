# agent-comm CLI v2 Spec

## Purpose

`agent-comm` is a stateless command-line query tool over a local SQLite mailbox.
It helps independent agents send deliberate addressed messages to each other.
It is not a workflow engine, progress tracker, runtime manager, daemon, or agent memory.

Every command should be usable from a fresh shell with explicit arguments. The
CLI must not depend on hidden session state such as "current agent", "current
thread", or stored command context.

## Design Goals

- Make the normal agent path one command, not a sequence of setup commands.
- Keep all agent identity explicit with `--as`.
- Derive project identity from the current checkout instead of requiring agents
  to pass `--project`.
- Use one shared mailbox for all worktrees of the same project.
- Let short messages be sent inline.
- Make artifact references optional.
- Keep lower-level commands available for diagnostics and tests, but do not teach
  agents to use them for normal coordination.

## Defaults

The normal path does not require `--project` or `--bus`.

The CLI derives a project key from the current working directory:

1. If inside a Git repository with git remote `origin`, canonicalize the origin
   URL and derive the key from that.
2. If inside a Git repository without `origin`, use
   `git rev-parse --git-common-dir` so linked worktrees of the same local repo
   share one mailbox.
3. If not inside Git, derive the key from the absolute current directory path.

The default bus path is user-local:

```text
~/.agent-comm/projects/<project-key>/bus.sqlite
```

That means agents in multiple worktrees of the same project share one mailbox.
The CLI creates the directory and initializes the schema automatically when a
command needs the bus. It sets private file permissions where the platform
supports that.

`--bus PATH` remains available for tests, diagnostics, and emergencies, but
normal agent-facing instructions should not use it.

If the shared user-local bus is blocked by a harness sandbox, the agent should
ask for permission to use the shared mailbox. It should not silently create a
worktree-local mailbox, because that would split communication across agents.

`--local` may be added to force `.agent-comm/bus.sqlite` for isolated experiments.
It should not be the default.

## Primary Command

Send a message:

```sh
agent-comm send --as <sender> --to <recipient> [options] <message>
```

Example:

```sh
agent-comm send --as planner-main --to implementer-feature-a \
  --thread "Coordination test" \
  "Please acknowledge this test and reply."
```

`send` automatically:

- creates or opens the bus
- initializes the schema if needed
- ensures sender and recipient agent rows exist
- creates a thread when needed
- posts the message
- attaches any artifact paths passed with `--artifact`
- prints the thread id and message id
- waits for a reply when `--wait` is passed

## Message Bodies

Inline text is the default:

```sh
agent-comm send --as planner-main --to implementer-feature-a "Short message."
```

File bodies are optional:

```sh
agent-comm send --as planner-main --to implementer-feature-a --body-file handoff.md
```

Stdin is optional:

```sh
printf "Short message.\n" | agent-comm send --as planner-main --to implementer-feature-a --stdin
```

Exactly one body source is required: inline message, `--body-file`, or `--stdin`.

Agents should not create a file just to send a short message.

## Threads

`--thread` accepts either an existing thread id or a title.

```sh
agent-comm send --as planner-main --to implementer-feature-a \
  --thread "Implement login fix" \
  "Please review the failing test and propose a fix."
```

If `--thread` is omitted, `send` creates a thread with the message subject or a
short derived title. Agents may pass `--thread` when the conversation should
continue in a known work stream.

Thread ids remain printed in command output so agents can reuse them when useful.

## Artifacts

Artifacts are optional links to project files:

```sh
agent-comm send --as planner-main --to implementer-feature-a \
  --artifact docs/plan.md \
  "Please review the linked plan."
```

Artifacts should be used for durable project context such as plans, review notes,
test logs, or patches. They are not required for short coordination messages.

Multiple artifacts are allowed by repeating `--artifact`.

## Replies

Reply to a message:

```sh
agent-comm reply <message-id> --as <sender> <message>
```

Example:

```sh
agent-comm reply msg_123 --as implementer-feature-a \
  "Received. The mailbox round trip works."
```

`reply` automatically:

- looks up the original message
- uses the original thread
- addresses the reply to the original sender unless `--to` is supplied
- links the reply to the original message
- accepts `--artifact`, `--body-file`, `--stdin`, and `--wait`

## Reading

List unread messages:

```sh
agent-comm inbox --as <agent>
```

Show the next unread message:

```sh
agent-comm next --as <agent>
```

Show and acknowledge the next unread message:

```sh
agent-comm next --as <agent> --ack
```

Show a specific message:

```sh
agent-comm show <message-id>
```

Acknowledge a specific message:

```sh
agent-comm ack --as <agent> <message-id>
```

Wait for unread mail:

```sh
agent-comm wait --as <agent>
agent-comm wait --as <agent> --follow
```

`wait` should only be used when the agent is blocked on another agent.

## Advanced Commands

The lower-level commands may remain for tests, debugging, and compatibility:

- `init`
- `register`
- `start-thread`
- `post`
- `artifact add`
- `backup`
- `restore`
- `migrate`
- `doctor`

Skills should prefer `send`, `reply`, `next`, `inbox`, `show`, `ack`, and `wait`.

## Skill Guidance

The skills should show only the high-level stateless commands.

Planner example:

```sh
agent-comm send --as planner-main --to implementer-feature-a \
  --thread "<work title>" \
  "Please review this handoff and reply with questions or acknowledgement."
```

Implementer example:

```sh
agent-comm next --as implementer-feature-a --ack
agent-comm reply <message-id> --as implementer-feature-a \
  "Received. I will proceed and report blockers in this thread."
```

Skills must state:

- Choose an `--as` id that identifies both role and worktree when working across
  worktrees, for example `planner-main`, `implementer-feature-a`, or
  `reviewer-bugfix-123`.
- Use `--artifact` only when useful durable context already exists or should
  exist as a project artifact.
- Do not create a file just to satisfy the CLI.
- Use `--wait` only when blocked on a reply.
- Do not inspect CLI help for the normal path unless a command fails.

## Critical Review

This v2 shape is better because it keeps the CLI stateless while removing
needless setup choreography. `send` and `reply` are still explicit about sender,
recipient, and message, while project identity is derived from stable repository
facts.

Main risks:

- `--thread` accepting both title and id can be ambiguous. This is acceptable if
  thread ids have a reserved prefix such as `thread_`; otherwise split into
  `--thread-id` and `--thread`.
- Auto-registering agents is convenient but may hide typos in agent ids. The CLI
  should print when it creates an agent row so mistakes are visible.
- A shared user-local bus is semantically right for multi-worktree coordination
  but may require sandbox approval. That approval is better than silently using a
  separate worktree-local mailbox.
- `--wait` can still hang if no other agent is running. It should print the
  message id, thread id, and clear interrupt guidance before blocking.
- Inline shell messages can be awkward for long Markdown. That is fine because
  `--body-file` and `--stdin` remain available.

The important simplification is that agents no longer need to know about schema
initialization, registration, thread creation, body-file plumbing, or artifact
subcommands for the common case.
