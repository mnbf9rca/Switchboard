# Fresh Agent Session Smoke Test

Use this manual script to verify that a fresh planner session and a fresh
implementer session can discover the skills and exchange one mailbox handoff.

## Setup

Run from this repository:

```sh
ROOT="<repo root>"
BUS_DIR=$(mktemp -d)
chmod 700 "$BUS_DIR"
BUS="$BUS_DIR/bus.sqlite"
cd "$ROOT"

python scripts/build_codex_plugin.py
python3.12 -m switchboard --version

printf 'BUS=%s\n' "$BUS"
```

Use `uv run --python 3.12 python -m switchboard` instead if `python3.12`
does not have the checkout dependencies available.

Add the local Codex marketplace source from:

```text
<repo root>
```

In Codex, use `/plugins`, add that marketplace source, then install
`switchboard` from the `switchboard-local` marketplace. Start a new Codex
session after installing so the skills are loaded.

The marketplace file lives at `.agents/plugins/marketplace.json`, and its
plugin source points at the generated `plugins/switchboard` bundle. Re-run
`python scripts/build_codex_plugin.py` and reinstall the plugin after source
changes so Codex picks up a new cachebusted plugin version.

Expose the local Claude plugin from:

```text
<repo root>/.claude-plugin/plugin.json
```

In Claude, plugin installs should expose the skills as
`/switchboard:coordinate-as-planner` and
`/switchboard:coordinate-as-implementer`. Local skills-directory installs may
use a different Claude namespace; if so, use that displayed namespace while
keeping the skill name the same.

In each fresh session, verify the skill invocation is accepted before continuing.
If the harness lists available skills, confirm both skill names appear there.

## Planner Session

Start a fresh planner agent session and invoke:

```text
/switchboard:coordinate-as-planner
```

Tell the planner to use this runtime:

```text
<installed plugin root>/scripts/switchboard --bus <BUS printed by setup>
```

Then create and send the handoff:

```sh
BUS="<paste BUS printed by setup>"
case "$BUS" in
  *"<paste"*) echo "replace pasted bus value before running"; exit 1 ;;
esac

MSG_PLANNER_TO_IMPLEMENTER=$(python3.12 -m switchboard --bus "$BUS" send \
  --as planner-main \
  --to implementer-feature-a \
  --title "Fresh session smoke" \
  "Please acknowledge this handoff and reply that the mailbox round trip works." \
  | awk '/^message: / {print $2}')
printf 'MSG_PLANNER_TO_IMPLEMENTER=%s\n' "$MSG_PLANNER_TO_IMPLEMENTER"
```

Keep the planner session open.

Copy the printed `MSG_PLANNER_TO_IMPLEMENTER` value. If the implementer session
uses a separate shell, replace that placeholder manually in the commands below.

## Implementer Session

Start a fresh implementer agent session and invoke:

```text
/switchboard:coordinate-as-implementer
```

Tell the implementer to use this runtime:

```text
<installed plugin root>/scripts/switchboard --bus <BUS printed by setup>
```

Then read and reply to the handoff:

```sh
BUS="<paste BUS printed by setup>"
MSG_PLANNER_TO_IMPLEMENTER="<paste MSG_PLANNER_TO_IMPLEMENTER printed by planner>"
case "$BUS:$MSG_PLANNER_TO_IMPLEMENTER" in
  *"<paste"*) echo "replace pasted bus and planner values before running"; exit 1 ;;
esac

python3.12 -m switchboard --bus "$BUS" next --as implementer-feature-a
MSG_IMPLEMENTER_TO_PLANNER=$(python3.12 -m switchboard --bus "$BUS" reply "$MSG_PLANNER_TO_IMPLEMENTER" \
  --as implementer-feature-a \
  "Received. The mailbox round trip works." \
  | awk '/^message: / {print $2}')
printf 'MSG_IMPLEMENTER_TO_PLANNER=%s\n' "$MSG_IMPLEMENTER_TO_PLANNER"
```

Replace the placeholder assignments with the values printed by the planner
session.

## Planner Reads Reply

Return to the planner session:

```sh
BUS="<paste BUS printed by setup>"
MSG_IMPLEMENTER_TO_PLANNER="<paste MSG_IMPLEMENTER_TO_PLANNER printed by implementer>"
case "$BUS:$MSG_IMPLEMENTER_TO_PLANNER" in
  *"<paste"*) echo "replace pasted bus and implementer values before running"; exit 1 ;;
esac

python3.12 -m switchboard --bus "$BUS" inbox --as planner-main
```

The smoke test passes when the planner inbox includes the implementer's reply.
