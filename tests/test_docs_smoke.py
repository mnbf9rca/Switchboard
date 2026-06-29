from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from conftest import OLD_ACTIVE_NAMES


ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "smoke-tests" / "fresh-agent-sessions.md"


def _guide_text() -> str:
    return GUIDE.read_text()


def test_fresh_agent_smoke_guide_exists():
    assert GUIDE.exists()


def test_fresh_agent_smoke_guide_documents_local_installs():
    text = _guide_text()
    normalized = " ".join(text.lower().split())

    assert ".agents/plugins" in text
    assert "/plugins" in text
    assert "switchboard-local" in text
    assert ".claude-plugin/plugin.json" in text
    assert "Claude" in text
    assert "local skills-directory installs may use a different claude namespace" in normalized


def test_fresh_agent_smoke_guide_uses_exact_skill_invocations():
    text = _guide_text()

    assert "/switchboard:coordinate-as-planner" in text
    assert "/switchboard:coordinate-as-implementer" in text


def test_fresh_agent_smoke_guide_documents_runtime_commands():
    text = _guide_text()

    assert "python3.12 -m switchboard --version" in text
    assert "uv run --python 3.12 python -m switchboard" in text
    assert "python -m switchboard --version" not in text
    assert "python3.12 -m agent_comm --version" not in text
    assert "python scripts/build_codex_plugin.py" in text
    assert "command -v switchboard" not in text
    assert "\nswitchboard --version" not in text
    assert "BUS_DIR=$(mktemp -d)" in text
    assert "chmod 700 \"$BUS_DIR\"" in text
    assert "BUS=\"$BUS_DIR/bus.sqlite\"" in text
    assert "printf 'BUS=%s\\n' \"$BUS\"" in text
    assert "<installed plugin root>/scripts/switchboard --bus <BUS printed by setup>" in text


def test_fresh_agent_smoke_guide_exercises_mailbox_handoff_flow():
    text = _guide_text()

    required_snippets = (
        "BUS=\"<paste BUS printed by setup>\"",
        "replace pasted bus value before running",
        "printf 'MSG_PLANNER_TO_IMPLEMENTER=%s\\n' \"$MSG_PLANNER_TO_IMPLEMENTER\"",
        "printf 'MSG_IMPLEMENTER_TO_PLANNER=%s\\n' \"$MSG_IMPLEMENTER_TO_PLANNER\"",
        "MSG_PLANNER_TO_IMPLEMENTER=\"<paste MSG_PLANNER_TO_IMPLEMENTER printed by planner>\"",
        "MSG_IMPLEMENTER_TO_PLANNER=\"<paste MSG_IMPLEMENTER_TO_PLANNER printed by implementer>\"",
        "replace pasted bus and planner values before running",
        "replace pasted bus and implementer values before running",
        'python3.12 -m switchboard --bus "$BUS" next --as implementer-feature-a',
        'python3.12 -m switchboard --bus "$BUS" inbox --as planner-main',
    )
    for snippet in required_snippets:
        assert snippet in text

    compact = " ".join(text.replace("\\\n", " ").split())
    assert (
        'python3.12 -m switchboard --bus "$BUS" send --as planner-main '
        '--to implementer-feature-a --title "Fresh session smoke"'
    ) in compact
    assert (
        'python3.12 -m switchboard --bus "$BUS" reply '
        '"$MSG_PLANNER_TO_IMPLEMENTER" --as implementer-feature-a'
    ) in compact

    forbidden_snippets = (
        *OLD_ACTIVE_NAMES,
        "THREAD_ID",
        "register",
        "start-thread",
        " post ",
        "run_agent_comm",
        "artifact add",
        "status --thread",
        "--reply-to",
        "--agent implementer",
        "--agent planner",
    )
    for snippet in forbidden_snippets:
        assert snippet not in text

    assert 'switchboard --bus "$BUS" post' not in text
    assert "replace pasted bus, planner, and implementer values before running" not in text
    assert re.search(r"(?m)^(?!<installed plugin root>/scripts/)switchboard --bus", text) is None
    assert "(switchboard --bus" not in text


def test_fresh_agent_smoke_flow_commands_round_trip(tmp_path):
    bus = tmp_path / "smoke.db"

    def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "switchboard", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

    planner_message_id = _field(
        run_cli(
            "--bus",
            str(bus),
            "send",
            "--as",
            "planner-main",
            "--to",
            "implementer-feature-a",
            "--title",
            "Fresh session smoke",
            "Please acknowledge this handoff and reply that the mailbox round trip works.",
        ).stdout,
        "message",
    )
    next_message = run_cli(
        "--bus",
        str(bus),
        "next",
        "--as",
        "implementer-feature-a",
    ).stdout
    assert planner_message_id in next_message
    assert "Please acknowledge this handoff" in next_message

    implementer_message_id = _field(
        run_cli(
            "--bus",
            str(bus),
            "reply",
            planner_message_id,
            "--as",
            "implementer-feature-a",
            "Received. The mailbox round trip works.",
        ).stdout,
        "message",
    )
    assert implementer_message_id in run_cli(
        "--bus", str(bus), "inbox", "--as", "planner-main"
    ).stdout
    shown_reply = run_cli(
        "--bus", str(bus), "show", implementer_message_id
    ).stdout
    assert "Received. The mailbox round trip works." in shown_reply


def _field(output: str, key: str) -> str:
    prefix = f"{key}: "
    for line in output.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix)
    raise AssertionError(f"{key!r} not found in output:\n{output}")
