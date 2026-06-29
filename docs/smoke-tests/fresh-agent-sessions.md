# Fresh Agent Session Smoke Test

Use this manual script to verify that a fresh planner session and a fresh
implementer session can discover the skills and exchange one mailbox handoff.

## Setup

Run from this repository:

```sh
ROOT=/Users/rob/Downloads/git/agents-together
BUS_DIR=$(mktemp -d)
chmod 700 "$BUS_DIR"
BUS="$BUS_DIR/bus.sqlite"
cd "$ROOT"

python scripts/build_codex_plugin.py
python -m agent_comm --version
command -v agent-comm >/dev/null && agent-comm --version

run_agent_comm() {
  python -m agent_comm "$@"
}

run_agent_comm --bus "$BUS" init --project agents-together-smoke
run_agent_comm --bus "$BUS" register --agent planner --display-name "Planner" --harness codex --role planner
run_agent_comm --bus "$BUS" register --agent implementer --display-name "Implementer" --harness claude --role implementer
printf 'BUS=%s\n' "$BUS"
```

Use `python -m agent_comm` for a source checkout smoke test. Use `agent-comm`
instead after installing the package and confirming `agent-comm --version` works.

Add the local Codex marketplace source from:

```text
/Users/rob/Downloads/git/agents-together
```

In Codex, use `/plugins`, add that marketplace source, then install
`agents-together` from the `agents-together-local` marketplace. Start a new Codex
session after installing so the skills are loaded.

The marketplace file lives at `.agents/plugins/marketplace.json`, and its
plugin source points at the generated `plugins/agents-together` bundle. Re-run
`python scripts/build_codex_plugin.py` and reinstall the plugin after source
changes so Codex picks up a new cachebusted plugin version.

Expose the local Claude plugin from:

```text
/Users/rob/Downloads/git/agents-together/.claude-plugin/plugin.json
```

In Claude, plugin installs should expose the skills as
`/agents-together:coordinate-as-planner` and
`/agents-together:coordinate-as-implementer`. Local skills-directory installs may
use a different Claude namespace; if so, use that displayed namespace while
keeping the skill name the same.

In each fresh session, verify the skill invocation is accepted before continuing.
If the harness lists available skills, confirm both skill names appear there.

## Planner Session

Start a fresh planner agent session and invoke:

```text
/agents-together:coordinate-as-planner
```

Tell the planner to use this runtime:

```text
<installed plugin root>/scripts/agent-comm --bus <BUS printed by setup>
```

Then create and send the handoff:

```sh
BUS="<paste BUS printed by setup>"
case "$BUS" in
  *"<paste"*) echo "replace pasted bus value before running"; exit 1 ;;
esac

run_agent_comm() {
  python -m agent_comm "$@"
}

THREAD_ID=$(run_agent_comm --bus "$BUS" start-thread --project agents-together-smoke --title "Fresh session smoke" | awk '/^thread: / {print $2}')
printf 'THREAD_ID=%s\n' "$THREAD_ID"

cat > /tmp/agents-together-planner-handoff.md <<'EOF'
# Smoke handoff

Please acknowledge this handoff and reply that the mailbox round trip works.

Artifact: docs/smoke-tests/fresh-agent-sessions.md
EOF

MSG_PLANNER_TO_IMPLEMENTER=$(run_agent_comm --bus "$BUS" post \
  --thread "$THREAD_ID" \
  --from planner \
  --to implementer \
  --subject "Smoke handoff" \
  --body-file /tmp/agents-together-planner-handoff.md \
  | awk '/^message: / {print $2}')
printf 'MSG_PLANNER_TO_IMPLEMENTER=%s\n' "$MSG_PLANNER_TO_IMPLEMENTER"

run_agent_comm --bus "$BUS" artifact add \
  --thread "$THREAD_ID" \
  --message "$MSG_PLANNER_TO_IMPLEMENTER" \
  --path docs/smoke-tests/fresh-agent-sessions.md \
  --description "Smoke handoff guide"
```

Keep the planner session open.

Copy the printed `THREAD_ID` and `MSG_PLANNER_TO_IMPLEMENTER` values. If the
implementer session uses a separate shell, replace those placeholders manually
in the commands below.

## Implementer Session

Start a fresh implementer agent session and invoke:

```text
/agents-together:coordinate-as-implementer
```

Tell the implementer to use this runtime:

```text
<installed plugin root>/scripts/agent-comm --bus <BUS printed by setup>
```

Then read, show, acknowledge, and reply to the handoff:

```sh
BUS="<paste BUS printed by setup>"
THREAD_ID="<paste THREAD_ID printed by planner>"
MSG_PLANNER_TO_IMPLEMENTER="<paste MSG_PLANNER_TO_IMPLEMENTER printed by planner>"
case "$BUS:$THREAD_ID:$MSG_PLANNER_TO_IMPLEMENTER" in
  *"<paste"*) echo "replace pasted bus and planner values before running"; exit 1 ;;
esac

run_agent_comm() {
  python -m agent_comm "$@"
}

run_agent_comm --bus "$BUS" inbox --agent implementer
run_agent_comm --bus "$BUS" show "$MSG_PLANNER_TO_IMPLEMENTER"
run_agent_comm --bus "$BUS" ack "$MSG_PLANNER_TO_IMPLEMENTER" --agent implementer

cat > /tmp/agents-together-implementer-reply.md <<'EOF'
# Smoke reply

Acknowledged. I read the artifact link and the mailbox round trip works.
EOF

MSG_IMPLEMENTER_TO_PLANNER=$(run_agent_comm --bus "$BUS" post \
  --thread "$THREAD_ID" \
  --from implementer \
  --to planner \
  --subject "Smoke reply" \
  --body-file /tmp/agents-together-implementer-reply.md \
  --reply-to "$MSG_PLANNER_TO_IMPLEMENTER" \
  | awk '/^message: / {print $2}')
printf 'MSG_IMPLEMENTER_TO_PLANNER=%s\n' "$MSG_IMPLEMENTER_TO_PLANNER"
```

Replace the placeholder assignments with the values printed by the planner
session.

## Planner Reads Reply

Return to the planner session:

```sh
BUS="<paste BUS printed by setup>"
THREAD_ID="<paste THREAD_ID printed by planner>"
MSG_IMPLEMENTER_TO_PLANNER="<paste MSG_IMPLEMENTER_TO_PLANNER printed by implementer>"
case "$BUS:$THREAD_ID:$MSG_IMPLEMENTER_TO_PLANNER" in
  *"<paste"*) echo "replace pasted bus, planner, and implementer values before running"; exit 1 ;;
esac

run_agent_comm() {
  python -m agent_comm "$@"
}

run_agent_comm --bus "$BUS" inbox --agent planner
run_agent_comm --bus "$BUS" show "$MSG_IMPLEMENTER_TO_PLANNER"
run_agent_comm --bus "$BUS" status --thread "$THREAD_ID"
run_agent_comm --bus "$BUS" ack "$MSG_IMPLEMENTER_TO_PLANNER" --agent planner
```

The smoke test passes when the planner can read the implementer's reply and the
thread status shows `reply_links:` with the implementer reply pointing back to
the planner handoff.
