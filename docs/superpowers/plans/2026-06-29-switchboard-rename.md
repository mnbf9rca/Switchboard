# Switchboard Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the project from Agents Together / agent-comm to Switchboard across active package, CLI, plugin, skills, docs, tests, and generated bundles.

**Architecture:** Treat `switchboard` as the only supported public name: package, Python module, CLI command, plugin, marketplace, cache bundle, and mailbox directory all move together. Do not keep `agent-comm`, `agent_comm`, or `agents-together` compatibility aliases in this pre-release cleanup; failing fast is simpler than carrying two identities.

**Tech Stack:** Python 3.12 stdlib, SQLite, argparse, pytest, Codex/Claude plugin manifests.

---

## Rename Decisions

- Product name: `Switchboard`
- Python project/package name: `switchboard`
- Python module directory: `switchboard/`
- CLI command: `switchboard`
- Launcher script: `scripts/switchboard`
- User-local mailbox root: `~/.switchboard/projects/<project-key>/bus.sqlite`
- Environment override: `SWITCHBOARD_BUS`
- Codex/Claude plugin name: `switchboard`
- Local marketplace name: `switchboard-local`
- Generated local bundle: `plugins/switchboard`
- Skill namespace after install: `switchboard:coordinate-as-planner` and `switchboard:coordinate-as-implementer`
- Skill directory names stay `coordinate-as-planner` and `coordinate-as-implementer`
- Protocol reference filename: `switchboard-protocol.md`
- Version: bump to `0.2.0`

Do not add compatibility aliases for the old CLI, module, plugin name, marketplace name, environment variable, or mailbox root. If an old command is invoked, normal command-not-found or import failure is acceptable.

Historical plans/specs under `docs/superpowers/` may keep old names because they document how the project evolved. Active user-facing docs, tests, examples, manifests, scripts, package files, and skills must use Switchboard naming.

The untracked workspace file `handover.md` is out of scope for this rename plan unless the user explicitly asks to track it. If it later becomes active tracked documentation, either move it under `docs/superpowers/` as historical material or rename its active content to Switchboard.

## File Structure

- Rename directory `agent_comm/` to `switchboard/`.
- Rename launcher `scripts/agent-comm` to `scripts/switchboard`.
- Rename generated bundle output `plugins/agents-together/` to `plugins/switchboard/` through `scripts/build_codex_plugin.py`.
- Rename protocol references:
  - `skills/coordinate-as-planner/references/agent-communication-protocol.md` -> `skills/coordinate-as-planner/references/switchboard-protocol.md`
  - `skills/coordinate-as-implementer/references/agent-communication-protocol.md` -> `skills/coordinate-as-implementer/references/switchboard-protocol.md`
- Modify package metadata: `pyproject.toml`, `uv.lock`, `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json`, `.agents/plugins/marketplace.json`.
- Modify ignore rules: `.gitignore`.
- Modify active docs: `README.md`, `docs/smoke-tests/fresh-agent-sessions.md`, `examples/*.md`, skill `SKILL.md` files, protocol references.
- Modify tests and helpers: `tests/conftest.py`, `tests/test_ci_precommit_config.py`, package/CLI tests, path tests, docs smoke tests, plugin/skill manifest tests, import paths across all tests.

## Task 1: Rename Contract Tests

**Files:**
- Modify: `tests/test_package_cli.py`
- Modify: `tests/test_skills_manifests_examples.py`
- Modify: `tests/test_docs_smoke.py`
- Modify: `tests/test_paths.py`

- [ ] **Step 1: Update package CLI tests first**

In `tests/test_package_cli.py`, change version and command expectations to Switchboard:

```python
def test_help_and_version_work(run_cli):
    help_result = run_cli("--help")
    version_result = run_cli("--version")
    assert help_result.returncode == 0
    assert "switchboard" in help_result.stdout
    assert "init" in help_result.stdout
    assert version_result.returncode == 0
    assert "switchboard 0.2.0" in version_result.stdout
```

Change unsupported Python assertion:

```python
assert "switchboard 0.2.0" not in captured.out + captured.err
```

Change ignored local SQLite root assertion:

```python
assert ".switchboard/" in ignored_patterns
assert ".agent-comm/" not in ignored_patterns
```

Change missing script assertion:

```python
assert str(missing_python.with_name("switchboard")) in str(exc)
```

- [ ] **Step 2: Update plugin and skill manifest tests**

In `tests/test_skills_manifests_examples.py`, update `SKILLS` descriptions to mention Switchboard instead of `agent-comm`.

Change command discovery assertions:

```python
assert "switchboard --version" in body
assert "python3.12 -m switchboard --version" in body
assert "py -3.12 -m switchboard --version" in body
assert "uv run switchboard --version" in body
assert "agent-comm --version" not in body
assert "python3.12 -m agent_comm --version" not in body
assert "python3 -m agent_comm --version" not in body
assert "python -m agent_comm --version" not in body
```

Update protocol path expectation:

```python
ROOT / "skills" / skill_name / "references" / "switchboard-protocol.md"
```

Update command appendix checks:

```python
for guidance in (
    "switchboard send --as",
    "switchboard reply <message-id> --as",
    "switchboard next --as",
    "Use ack explicitly when you read without replying",
):
    assert guidance in protocol

for old_command in (
    "agent-comm",
    "agent_comm",
    "agents-together",
    "switchboard register",
    "switchboard start-thread",
    "switchboard post",
    "--body-file <path>",
):
    assert old_command not in command_appendix
```

Update manifest expectations:

```python
claude_expected = {
    "name": "switchboard",
    "version": "0.2.0",
    "description": "A local mailbox for deliberate agent coordination",
    "skills": "./skills/",
}
```

Update marketplace expectations:

```python
assert marketplace == {
    "name": "switchboard-local",
    "interface": {"displayName": "Switchboard Local"},
    "plugins": [
        {
            "name": "switchboard",
            "source": {"source": "local", "path": "./plugins/switchboard"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Productivity",
        }
    ],
}
```

Update launcher tests:

```python
launcher = ROOT / "scripts" / "switchboard"
assert result.stdout.strip() == "switchboard 0.2.0"
```

Update generated bundle expectations:

```python
output = tmp_path / "switchboard"
assert manifest["version"] == "0.2.0+codex.test-123"
expected_files = [
    ".codex-plugin/plugin.json",
    ".generated.json",
    "README.md",
    "switchboard/__main__.py",
    "switchboard/cli.py",
    "scripts/switchboard",
    "skills/coordinate-as-planner/SKILL.md",
    "skills/coordinate-as-planner/references/switchboard-protocol.md",
    "skills/coordinate-as-implementer/SKILL.md",
    "skills/coordinate-as-implementer/references/switchboard-protocol.md",
]
assert version.stdout.strip() == "switchboard 0.2.0"
```

- [ ] **Step 3: Update smoke docs tests**

In `tests/test_docs_smoke.py`, update skill invocation and command strings:

```python
assert "/switchboard:coordinate-as-planner" in text
assert "/switchboard:coordinate-as-implementer" in text
assert "python3.12 -m switchboard --version" in text
assert "python -m switchboard --version" not in text
assert "python3.12 -m agent_comm --version" not in text
assert "command -v switchboard >/dev/null && switchboard --version" in text
assert "<installed plugin root>/scripts/switchboard --bus <BUS printed by setup>" in text
```

Update v2 flow snippets to use `switchboard`:

```python
required_snippets = (
    'switchboard --bus "$BUS" next --as implementer-feature-a',
    'switchboard --bus "$BUS" inbox --as planner-main',
)
```

Update forbidden old names:

```python
for forbidden in (
    "agent-comm",
    "agent_comm",
    "agents-together",
    "THREAD_ID",
    "register",
    "start-thread",
    " post ",
    "artifact add",
    "status --thread",
    "--reply-to",
):
    assert forbidden not in text
```

Update the round-trip smoke test helper:

```python
def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "switchboard", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
```

- [ ] **Step 4: Update path tests**

In `tests/test_paths.py`, update default mailbox root assertions:

```python
assert path.parent.parent == home / ".switchboard" / "projects"
```

Add env override rename test:

```python
def test_switchboard_bus_env_overrides_default(tmp_path, monkeypatch):
    bus = tmp_path / "custom.sqlite"
    monkeypatch.setenv("SWITCHBOARD_BUS", str(bus))

    assert resolve_bus_path(bus=None, project=None, cwd=tmp_path) == bus
```

Add old env var ignored test:

```python
def test_agent_comm_bus_env_is_not_supported(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENT_COMM_BUS", str(tmp_path / "old.sqlite"))

    path = resolve_bus_path(bus=None, project="demo", cwd=tmp_path)

    assert path != tmp_path / "old.sqlite"
    assert path.parent.parent == tmp_path / "home" / ".switchboard" / "projects"
```

- [ ] **Step 5: Run rename contract tests and verify red**

Run:

```bash
uv run --python 3.12 pytest \
  tests/test_package_cli.py \
  tests/test_skills_manifests_examples.py \
  tests/test_docs_smoke.py \
  tests/test_paths.py \
  -q
```

Expected before implementation: failures showing old package name, old launcher, old plugin names, old mailbox root, old docs, and old import paths.

## Task 2: Package, Module, CLI, and Mailbox Root

**Files:**
- Rename: `agent_comm/` -> `switchboard/`
- Rename: `scripts/agent-comm` -> `scripts/switchboard`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `.gitignore`
- Modify: `tests/conftest.py`
- Modify: all `tests/*.py` imports and subprocess module invocations

- [ ] **Step 1: Rename the Python module**

Run:

```bash
git mv agent_comm switchboard
```

Update `switchboard/__init__.py`:

```python
from __future__ import annotations

__version__ = "0.2.0"
```

Do not leave an `agent_comm/` compatibility package.

- [ ] **Step 2: Update package metadata**

In `pyproject.toml`:

```toml
[project]
name = "switchboard"
version = "0.2.0"
description = "A local mailbox for deliberate agent coordination"
readme = "README.md"
requires-python = ">=3.12"
dependencies = []

[project.scripts]
switchboard = "switchboard.cli:main"
```

Remove the old `agent-comm = "agent_comm.cli:main"` script entry.

- [ ] **Step 3: Rename the launcher script**

Run:

```bash
git mv scripts/agent-comm scripts/switchboard
```

Update `scripts/switchboard` so it runs the new module:

```sh
PYTHONPATH="$PLUGIN_ROOT${PYTHONPATH:+:$PYTHONPATH}" exec "$PYTHON_BIN" -m switchboard "$@"
```

Update all other occurrences in the script:

```sh
echo "switchboard requires Python 3.12 or newer on PATH" >&2
PYTHONPATH="$PLUGIN_ROOT${PYTHONPATH:+:$PYTHONPATH}" exec "$candidate" -m switchboard "$@"
```

- [ ] **Step 4: Update CLI display strings**

In `switchboard/cli.py`, change parser metadata:

```python
prog="switchboard"
```

Change version output:

```python
version=f"switchboard {__version__}"
```

Change runtime guard:

```python
f"ERROR: switchboard requires Python {required} or newer; "
```

- [ ] **Step 5: Rename default mailbox root and env override**

In `switchboard/paths.py`, replace old names:

```python
env_bus = os.environ.get("SWITCHBOARD_BUS")
```

```python
return Path.home() / ".switchboard" / "projects" / project_key(project) / "bus.sqlite"
```

Remove support for `AGENT_COMM_BUS`.

- [ ] **Step 6: Update `.gitignore`**

Replace:

```gitignore
.agent-comm/
plugins/agents-together/
```

with:

```gitignore
.switchboard/
plugins/switchboard/
```

Keep:

```gitignore
*.sqlite
*.sqlite-wal
*.sqlite-shm
```

- [ ] **Step 7: Update tests and imports**

Use `rg` to find old imports and module invocations:

```bash
rg -n "agent_comm|agent-comm|AGENT_COMM_BUS|\\.agent-comm" tests switchboard scripts pyproject.toml README.md .gitignore
```

Apply these mechanical changes in active code/tests:

- `from agent_comm` -> `from switchboard`
- `import agent_comm` -> `import switchboard`
- `python -m agent_comm` -> `python -m switchboard`
- `agent-comm` -> `switchboard`
- `_agent_comm_script` -> `_switchboard_script`
- `AGENT_COMM_BUS` -> `SWITCHBOARD_BUS`
- `.agent-comm` -> `.switchboard`

Do not update historical `docs/superpowers/**` in this task.

- [ ] **Step 8: Refresh lockfile**

Run:

```bash
uv lock
```

Expected: `uv.lock` contains package `switchboard` version `0.2.0`.

- [ ] **Step 9: Run package/path tests and verify green**

Run:

```bash
uv run --python 3.12 pytest tests/test_package_cli.py tests/test_paths.py tests/test_db_schema.py -q
```

Expected: all selected tests pass.

- [ ] **Step 10: Commit package rename**

Run:

```bash
git add .gitignore pyproject.toml uv.lock switchboard scripts tests
git add -u agent_comm scripts/agent-comm
git commit -m "Rename package and CLI to Switchboard"
```

## Task 3: Plugin, Marketplace, Skills, and Protocol

**Files:**
- Modify: `.codex-plugin/plugin.json`
- Modify: `.claude-plugin/plugin.json`
- Modify: `.agents/plugins/marketplace.json`
- Modify: `scripts/build_codex_plugin.py`
- Modify: `skills/coordinate-as-planner/SKILL.md`
- Modify: `skills/coordinate-as-implementer/SKILL.md`
- Rename: protocol reference files to `switchboard-protocol.md`
- Modify: `scripts/validate_skill_protocols.py`
- Modify: `tests/test_ci_precommit_config.py`
- Modify: `tests/test_skills_manifests_examples.py`

- [ ] **Step 1: Update plugin manifests**

In `.codex-plugin/plugin.json`:

```json
{
  "name": "switchboard",
  "version": "0.2.0",
  "description": "A local mailbox for deliberate agent coordination",
  "author": {
    "name": "switchboard"
  },
  "skills": "./skills/",
  "interface": {
    "displayName": "Switchboard",
    "shortDescription": "A local mailbox for deliberate agent coordination",
    "longDescription": "Coordinate planner, implementer, and reviewer agents through local Agent Skills and the Switchboard mailbox.",
    "developerName": "switchboard",
    "category": "Productivity",
    "capabilities": ["Skills"],
    "defaultPrompt": [
      "Coordinate this task as planner.",
      "Coordinate this task as implementer."
    ]
  }
}
```

In `.claude-plugin/plugin.json`:

```json
{"name":"switchboard","version":"0.2.0","description":"A local mailbox for deliberate agent coordination","skills":"./skills/"}
```

- [ ] **Step 2: Update local marketplace**

In `.agents/plugins/marketplace.json`:

```json
{
  "name": "switchboard-local",
  "interface": {
    "displayName": "Switchboard Local"
  },
  "plugins": [
    {
      "name": "switchboard",
      "source": {
        "source": "local",
        "path": "./plugins/switchboard"
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

- [ ] **Step 3: Rename protocol references**

Run:

```bash
git mv skills/coordinate-as-planner/references/agent-communication-protocol.md skills/coordinate-as-planner/references/switchboard-protocol.md
git mv skills/coordinate-as-implementer/references/agent-communication-protocol.md skills/coordinate-as-implementer/references/switchboard-protocol.md
```

In both `SKILL.md` files, change:

```markdown
See `references/switchboard-protocol.md` for command-level protocol notes.
```

- [ ] **Step 4: Update skill prose**

In both `SKILL.md` files:

- Replace `agent-comm` with `switchboard`
- Replace `<plugin-root>/scripts/agent-comm --version` with `<plugin-root>/scripts/switchboard --version`
- Replace `python3.12 -m agent_comm --version` with `python3.12 -m switchboard --version`
- Replace `py -3.12 -m agent_comm --version` with `py -3.12 -m switchboard --version`
- Replace `uv run agent-comm --version` with `uv run switchboard --version`

Keep the hard rules:

```text
Do not use a repo-local mailbox.
If the user explicitly assigns a role that conflicts with this skill, STOP and ask for clarification before using the mailbox.
```

- [ ] **Step 5: Update protocol prose and appendix**

In both `switchboard-protocol.md` files, update the title and command appendix:

```markdown
# Switchboard Protocol

`switchboard` is a durable mailbox for deliberate coordination between independent agents.
```

Command appendix:

```sh
switchboard send --as <sender-id> --to <recipient-id> "short message"
switchboard send --as <sender-id> --to <recipient-id> --title "<title>" "short message"
switchboard send --as <sender-id> --to <recipient-id> --artifact <path> "short message"
switchboard send --as <sender-id> --to <recipient-id> --in-thread <thread-id> "short message"
switchboard reply <message-id> --as <sender-id> "short reply"
switchboard next --as <agent-id>
switchboard inbox --as <agent-id>
switchboard show <message-id>
switchboard ack --as <agent-id> <message-id>
switchboard wait --as <agent-id>
switchboard wait --as <agent-id> --follow
```

- [ ] **Step 6: Update protocol validator and CI/precommit checks**

In `scripts/validate_skill_protocols.py`, update expected filenames from `agent-communication-protocol.md` to `switchboard-protocol.md`.

Keep the byte-identical requirement for the two protocol files.

In `tests/test_ci_precommit_config.py`, update every expected protocol validation command/path from `agent-communication-protocol.md` to `switchboard-protocol.md`. This is required, not optional, because CI and precommit must enforce the same byte-identical protocol files as the local validator.

- [ ] **Step 7: Update plugin bundle builder**

In `scripts/build_codex_plugin.py`, change the default output directory to `plugins/switchboard` and copied package directory to `switchboard`.

Expected copied source list includes:

```python
"switchboard",
"scripts/switchboard",
"skills",
".codex-plugin",
```

- [ ] **Step 8: Run skill/plugin tests and verify green**

Run:

```bash
uv run --python 3.12 pytest tests/test_skills_manifests_examples.py -q
uv run --python 3.12 python scripts/validate_skill_protocols.py
```

Expected: tests pass and validator reports two `switchboard-protocol.md` references.

- [ ] **Step 9: Build and validate plugin bundle**

Run:

```bash
python3 scripts/build_codex_plugin.py
python3 /Users/rob/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/switchboard
git status --short --ignored plugins/switchboard
```

Expected:

```text
Built Codex plugin: .../plugins/switchboard
Version: 0.2.0+codex.<cachebuster>
Plugin validation passed
!! plugins/switchboard/
```

- [ ] **Step 10: Commit plugin and skill rename**

Run:

```bash
git add .codex-plugin/plugin.json .claude-plugin/plugin.json .agents/plugins/marketplace.json scripts/build_codex_plugin.py scripts/validate_skill_protocols.py skills tests/test_ci_precommit_config.py tests/test_skills_manifests_examples.py
git add -u skills/coordinate-as-planner/references/agent-communication-protocol.md skills/coordinate-as-implementer/references/agent-communication-protocol.md
git commit -m "Rename plugin and skills to Switchboard"
```

## Task 4: Active Docs, Examples, and Smoke Tests

**Files:**
- Modify: `README.md`
- Modify: `docs/smoke-tests/fresh-agent-sessions.md`
- Modify: `examples/*.md`
- Modify: `tests/test_docs_smoke.py`
- Modify if needed: `tests/test_ci_precommit_config.py`

- [ ] **Step 1: Rewrite README**

Replace `README.md` with clean Switchboard-oriented content:

```markdown
# Switchboard

Switchboard is a local mailbox for deliberate coordination between independent coding agents.

It is intentionally small. Agents send addressed messages, replies, acknowledgements, and artifact links through a shared SQLite mailbox. Plans, review notes, logs, and working context stay in normal project files.

## What It Is

- A local SQLite mailbox for agents working in separate sessions, worktrees, or harnesses.
- A small CLI for deliberate agent-to-agent messages.
- A pair of planner and implementer skills for Codex and Claude plugin workflows.

## What It Is Not

- Not a daemon.
- Not a chat app.
- Not agent memory.
- Not a workflow engine.
- Not a progress log.

## Quick Start

```sh
switchboard send --as planner-main --to implementer-feature-a --title "Smoke test" "Please acknowledge this message."
switchboard next --as implementer-feature-a
switchboard reply <message-id> --as implementer-feature-a "Acknowledged."
switchboard inbox --as planner-main
```

## Runtime

```sh
switchboard --help
python3.12 -m switchboard --help
```

Development uses `uv` as a convenience:

```sh
uv run --python 3.12 pytest -q
uv run --python 3.12 python scripts/validate_skill_protocols.py
uv run --python 3.12 switchboard --help
```

## Mailbox Location

By default Switchboard derives a project key from the current checkout and stores the mailbox at:

```text
~/.switchboard/projects/<project-key>/bus.sqlite
```

Agents in linked worktrees of the same project share one mailbox. Switchboard does not fall back to a repo-local mailbox.

## Plugin Smoke Test

See `docs/smoke-tests/fresh-agent-sessions.md`.
```

- [ ] **Step 2: Update smoke guide**

In `docs/smoke-tests/fresh-agent-sessions.md`, replace active names:

- `agents-together` -> `switchboard`
- `agents-together-local` -> `switchboard-local`
- `Agents Together` -> `Switchboard`
- `/agents-together:coordinate-as-planner` -> `/switchboard:coordinate-as-planner`
- `/agents-together:coordinate-as-implementer` -> `/switchboard:coordinate-as-implementer`
- `agent-comm` -> `switchboard`
- `python3.12 -m agent_comm` -> `python3.12 -m switchboard`
- `plugins/agents-together` -> `plugins/switchboard`
- `.agent-comm` -> `.switchboard`

Do not mechanically rewrite absolute checkout paths to `/Users/rob/Downloads/git/switchboard`. Replace hard-coded local paths such as `/Users/rob/Downloads/git/agents-together` with `<repo root>` so the smoke guide remains valid even before the repository directory itself is renamed.

- [ ] **Step 3: Update examples**

In every file under `examples/`, replace active names:

- `agent-comm` -> `switchboard`
- `agent_comm` -> `switchboard`
- `agents-together` -> `switchboard`
- `Agents Together` -> `Switchboard`
- `agent-communication-protocol.md` -> `switchboard-protocol.md`

- [ ] **Step 4: Update docs smoke tests**

Apply the test changes from Task 1 and ensure the round-trip test uses:

```python
[sys.executable, "-m", "switchboard", *args]
```

Expected active skill invocations:

```python
assert "/switchboard:coordinate-as-planner" in text
assert "/switchboard:coordinate-as-implementer" in text
```

- [ ] **Step 5: Run docs tests and verify green**

Run:

```bash
uv run --python 3.12 pytest tests/test_docs_smoke.py tests/test_ci_precommit_config.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit active docs rename**

Run:

```bash
git add README.md docs/smoke-tests examples tests/test_docs_smoke.py tests/test_ci_precommit_config.py
git commit -m "Rename active docs to Switchboard"
```

## Task 5: Final Cleanup, Install, and Verification

**Files:**
- Modify only if final scans find active stale references.

- [ ] **Step 1: Scan active files for stale names**

Run:

```bash
rg -n "agents-together|Agents Together|agent-comm|agent_comm|\\.agent-comm|AGENT_COMM_BUS|plugins/agents-together|agent-communication-protocol" \
  README.md pyproject.toml .gitignore .codex-plugin .claude-plugin .agents scripts switchboard skills examples docs/smoke-tests tests
```

Expected: no matches except negative assertions in tests that intentionally forbid old names.

- [ ] **Step 2: Run full verification**

Run:

```bash
uv run --python 3.12 pytest -q
uv run --python 3.12 python scripts/validate_skill_protocols.py
python3 /Users/rob/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/switchboard
```

Expected:

```text
all pytest tests pass
Validated 2 skill protocol references
Plugin validation passed
```

- [ ] **Step 3: Install and verify Codex plugin cache**

Run:

```bash
codex plugin add switchboard@switchboard-local --json
```

From the JSON output, verify the installed path:

```bash
<installedPath>/scripts/switchboard --version
rg -n "Switchboard|switchboard send --as|STOP and ask for clarification|Do not use a repo-local mailbox" <installedPath>/skills
rg -n "agents-together|agent-comm|agent_comm" <installedPath>/skills <installedPath>/.codex-plugin/plugin.json
```

Expected:

```text
switchboard 0.2.0
installed plugin version is 0.2.0+codex.<cachebuster>
positive Switchboard guidance is present
old active names are absent from installed skills and manifest
```

This writes to `~/.codex`; request sandbox escalation before running if needed.

- [ ] **Step 4: Run local smoke**

Run:

```bash
BUS=$(mktemp -t switchboard.XXXXXX.sqlite)
switchboard --bus "$BUS" send --as planner-main --to implementer-feature-a --title "Switchboard smoke" "Please acknowledge this smoke test."
switchboard --bus "$BUS" next --as implementer-feature-a
MSG=$(switchboard --bus "$BUS" inbox --as implementer-feature-a | awk '/^message: / {print $2; exit}')
switchboard --bus "$BUS" reply "$MSG" --as implementer-feature-a "Acknowledged."
switchboard --bus "$BUS" inbox --as planner-main
```

Expected:

```text
send prints message and thread ids
next prints the message body
reply prints a new message id and acked original id
planner inbox includes the reply
```

- [ ] **Step 5: Commit final cleanup if needed**

If Step 1 found stale active references and they were fixed, commit:

```bash
git add README.md pyproject.toml .codex-plugin .claude-plugin .agents scripts switchboard skills examples docs/smoke-tests tests
git commit -m "Finish Switchboard rename cleanup"
```

Skip this commit if no files changed after prior tasks.

## Self-Review

Spec coverage:

- Canonical name `Switchboard`: covered by package, plugin, docs, tests, and smoke guide tasks.
- CLI/module rename: covered by Task 2.
- Plugin/marketplace rename: covered by Task 3.
- Mailbox root rename: covered by Task 2 path tests.
- No compatibility aliases: covered by test negative assertions and final stale-name scan.
- Active docs/examples cleanup: covered by Task 4.
- Generated bundle and installed cache: covered by Task 5.

Placeholder scan:

- No placeholder markers are present.
- Historical `docs/superpowers/**` files are intentionally out of scope and may retain old names as design history.

Type/name consistency:

- Product, package, module, CLI, plugin, marketplace, generated bundle, and mailbox root consistently use `switchboard`.
- Skill directory names remain role-oriented and do not include the product name.
