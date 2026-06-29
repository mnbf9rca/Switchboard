# Agent Communication Protocol

`agent-comm` provides a durable local mailbox for independent coding agents. It stores addressed messages, thread relationships, acknowledgements, and artifact links in a project-local bus. It does not require a background daemon.

## Roles and IDs

Planner and implementer are coordination roles, not fixed identities. Any agent can use any agent ID that makes sense for the current collaboration. Keep IDs stable within a task so inboxes and replies remain easy to follow.

## Deliberate Messages

Use addressed messages for intentional coordination. A useful message body states the requested action, current context, constraints, artifact links, and the expected response. Keep messages concise and link to project files for large plans, logs, diffs, or review notes.

Use threads to group related handoffs, questions, blockers, review notes, and acceptance messages. Continue a conversation by replying to the relevant prior message with repeated `--reply-to` use so the thread remains durable and navigable.

## Command Reference

Use the command form discovered by the skill, replacing `agent-comm` with the working module invocation when needed.

Initialize or inspect the bus:

```sh
agent-comm init --project <project-id>
agent-comm doctor
agent-comm backup --out <path>
agent-comm restore --from <path>
```

Register an agent identity:

```sh
agent-comm register --agent <agent-id> --role <role> --harness <harness>
```

Start a thread:

```sh
agent-comm start-thread --project <project-id> --title "<title>"
```

Send a message body from a Markdown file:

```sh
agent-comm post \
  --thread <thread-id> \
  --from <sender-agent-id> \
  --to <recipient-agent-id> \
  --subject "<subject>" \
  --body-file <path>
```

Reply to one or more prior messages in the same thread:

```sh
agent-comm post \
  --thread <thread-id> \
  --from <sender-agent-id> \
  --to <recipient-agent-id> \
  --subject "<subject>" \
  --body-file <path> \
  --reply-to <message-id> \
  --reply-to <message-id>
```

Read and acknowledge messages:

```sh
agent-comm inbox --agent <agent-id>
agent-comm show <message-id>
agent-comm ack <message-id> --agent <agent-id>
```

Wait for messages when useful:

```sh
agent-comm wait --agent <agent-id>
agent-comm wait --agent <agent-id> --follow
agent-comm wait --agent <agent-id> -f
```

Link a project artifact:

```sh
agent-comm artifact add \
  --thread <thread-id> \
  --message <message-id> \
  --path <project-relative-path> \
  --git-ref <git-ref> \
  --description "<why this matters>"
```

## Inbox, Show, Ack, and Wait

Check inboxes at the start of work, at meaningful boundaries, and before final coordination. Use inbox output to identify messages that need attention.

Use show to read the full message before acting. Acknowledge only after reading the body and any linked artifacts. Use wait when coordination depends on another agent's next message and polling would be wasteful.

## Replies and Artifacts

Reply in the same thread when asking questions, reporting blockers, handing back work, or reviewing results. Add artifacts for project-native files that carry durable context, such as plans, patches, test logs, screenshots, review notes, and acceptance notes.

Prefer artifact links over pasted bulk content. Do not paste secrets, credentials, private tokens, or large proprietary logs into mailbox messages.

## Backup and Doctor

Use backup before risky maintenance or when preserving a bus snapshot matters. Use doctor when setup, path resolution, database access, or mailbox behavior appears wrong. Doctor output is diagnostic context; keep the coordination decision in the message thread.

## Conflict Handling

If mailbox messages, repository artifacts, and current user direction disagree, stop and ask for clarification. State the conflict directly, link the relevant artifacts or messages, and wait for a clear decision before continuing.
