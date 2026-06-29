# agent-comm

`agent-comm` is a durable local mailbox for independent coding agents working in
separate sessions, worktrees, or harnesses. It is intentionally small: the CLI
coordinates addressed messages and related records, while project plans, review
notes, logs, and working context stay in normal project files.

Runtime invocation:

```sh
agent-comm --help
python3 -m agent_comm --help
python -m agent_comm --help
```

Development invocation uses `uv` only as a developer convenience:

```sh
uv run --python 3.12 python --version
uv run pytest
uv run agent-comm --help
```

Do not paste secrets, credentials, private tokens, or large proprietary logs into
mailbox messages. Prefer linking to project artifacts when large or sensitive
context is needed.
