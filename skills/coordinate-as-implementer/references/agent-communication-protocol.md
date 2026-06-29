# Agent Communication Protocol

`agent-comm` is a durable mailbox for deliberate coordination between independent agents. It is not a progress log, memory system, task tracker, or workflow engine. Use it to cross an agent boundary: one agent needs another agent to read, decide, answer, review, or accept something.

## Communication Principles

Send a mailbox message when another agent must act on information that is not already obvious from the repository state or current user instruction. Good reasons include a new handoff, a focused implementation question, a blocker that needs a decision, work that is ready for review, review findings that need action, acceptance of completed work, or a clarification request when instructions conflict.

Do not send routine progress updates, private scratch notes, command transcripts, or large working context through the mailbox. Keep those in project artifacts such as plans, review notes, logs, diffs, or handover files, then link the artifact from the message. The mailbox message should say why the artifact matters and what response is expected.

Every message should be addressed, intentional, and useful on its own. A reader should be able to understand who needs to do what, why now, where the durable context lives, and what kind of reply closes the loop.

Agent ids are explicit collaboration handles, not global user identities. Include the worktree name or branch in your agent id when multiple agents may work in different worktrees of the same project, for example `planner-main`, `implementer-feature-a`, or `reviewer-bugfix-123`. This keeps shared-mailbox messages readable without requiring the bus to understand worktree state.

Normal use does not require `--project` or `--bus`; the CLI derives a shared project mailbox. If sandbox permissions block that shared mailbox, ask the user before using a repo-local mailbox.

Each agent identity should include role and worktree when multiple worktrees are active, such as `planner-main` or `implementer-feature-a`.

Do not inspect CLI help before using this normal workflow; use help only after a command fails.

## What To Include

Use short Markdown bodies. Prefer this shape when it fits:

- The requested action or decision.
- The context needed to make that action safe.
- Links or paths to project artifacts.
- Constraints that matter now.
- The expected reply, such as answer, acknowledgement, review result, blocker detail, or acceptance.

Avoid ceremony and rigid headers. The body still has to be read, so write it like a clear note to a specific collaborator rather than a form for a parser.

## Planner Behavior

As planner, use messages to hand work to implementers, answer their questions, redirect blocked work, request review follow-up, and accept or reject ready work. Create or update project artifacts before messaging when the work needs durable detail. The mailbox message should point at those artifacts and state the immediate action.

Before sending new instructions, read your inbox so you do not overwrite a question, blocker, or ready-for-review reply. When reviewing implementation output, read the linked artifacts and repository state before acknowledging or accepting the message.

If you discover new information that changes the task, send a deliberate message to the affected agent. Do not rely on the other agent noticing chat history or unrelated file changes.

## Implementer Behavior

As implementer, read your inbox before starting work and at meaningful boundaries. Show and read the full message before acknowledging it. Acknowledge only after reading the message body and linked artifacts.

Ask a question when you cannot proceed safely from the handoff and repository artifacts. Report a blocker when you tried the expected path and need a decision or intervention. Send ready-for-review only when the requested work is in the repository and the verification evidence is available in a linked artifact or concise message body.

Replies should stay in the same thread and point back to the message being answered. If you answer several prior messages at once, link each relevant prior message as a reply target. Use ack explicitly when you read without replying. Reply automatically acknowledges the message being answered.

## Threads, Replies, and Artifacts

Use one thread for one coherent stream of work or review. Keep handoffs, questions, blockers, review findings, and acceptance for that stream in the same thread. Start a new thread when the work is unrelated or when mixing it into the existing thread would make the history harder to follow.

Use reply links to show which message you are answering. Reply links are not workflow state; they are durable conversation structure.

Use artifact links for project-native files that carry the real context: plans, specs, patches, test logs, review notes, screenshots, handover notes, and acceptance notes. Prefer artifact links over pasted bulk content. Do not paste secrets, credentials, private tokens, or large proprietary logs into mailbox messages.

## Waiting and Monitoring

Check inboxes at the start of work, before changing direction, before final reporting, and after asking another agent for a decision. Use wait or follow only when you are actually blocked on the next mailbox message. Agents may build their own lightweight monitor around the inbox, but the protocol does not require a daemon.

## Conflict Handling

If mailbox messages, repository artifacts, and current user direction disagree, stop and ask for clarification. Send a message to the relevant agent or agents that states the conflict, cites the conflicting messages or artifact paths, and asks for the ordering or intent needed to proceed. Do not invent precedence rules in the tool layer.

## Minimal Command Appendix

Use the command form discovered by the skill. Replace `agent-comm` with `python -m agent_comm` when that is the working runtime.

```sh
agent-comm send --as <sender-id> --to <recipient-id> "short message"
agent-comm send --as <sender-id> --to <recipient-id> --title "<title>" "short message"
agent-comm send --as <sender-id> --to <recipient-id> --artifact <path> "short message"
agent-comm send --as <sender-id> --to <recipient-id> --in-thread <thread-id> "short message"
agent-comm reply <message-id> --as <sender-id> "short reply"
agent-comm next --as <agent-id>
agent-comm inbox --as <agent-id>
agent-comm show <message-id>
agent-comm ack --as <agent-id> <message-id>
agent-comm wait --as <agent-id>
agent-comm wait --as <agent-id> --follow
```
