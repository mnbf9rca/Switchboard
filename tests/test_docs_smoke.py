from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


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
    assert "/Users/rob/Downloads/git/agents-together" in text
    assert "/plugins" in text
    assert "agents-together-local" in text
    assert ".claude-plugin/plugin.json" in text
    assert "Claude" in text
    assert "local skills-directory installs may use a different claude namespace" in normalized


def test_fresh_agent_smoke_guide_uses_exact_skill_invocations():
    text = _guide_text()

    assert "/agents-together:coordinate-as-planner" in text
    assert "/agents-together:coordinate-as-implementer" in text


def test_fresh_agent_smoke_guide_documents_runtime_commands():
    text = _guide_text()

    assert "python -m agent_comm --version" in text
    assert "python scripts/build_codex_plugin.py" in text
    assert "command -v agent-comm >/dev/null && agent-comm --version" in text
    assert "BUS_DIR=$(mktemp -d)" in text
    assert "chmod 700 \"$BUS_DIR\"" in text
    assert "BUS=\"$BUS_DIR/bus.sqlite\"" in text
    assert "printf 'BUS=%s\\n' \"$BUS\"" in text
    assert "<installed plugin root>/scripts/agent-comm --bus <BUS printed by setup>" in text
    assert "run_agent_comm() {" in text


def test_fresh_agent_smoke_guide_exercises_mailbox_handoff_flow():
    text = _guide_text()

    for snippet in (
        "--subject \"Smoke handoff\"",
        "Artifact: docs/smoke-tests/fresh-agent-sessions.md",
        "BUS=\"<paste BUS printed by setup>\"",
        "replace pasted bus value before running",
        "printf 'THREAD_ID=%s\\n' \"$THREAD_ID\"",
        "printf 'MSG_PLANNER_TO_IMPLEMENTER=%s\\n' \"$MSG_PLANNER_TO_IMPLEMENTER\"",
        "printf 'MSG_IMPLEMENTER_TO_PLANNER=%s\\n' \"$MSG_IMPLEMENTER_TO_PLANNER\"",
        "artifact add",
        "--message \"$MSG_PLANNER_TO_IMPLEMENTER\"",
        "--path docs/smoke-tests/fresh-agent-sessions.md",
        "THREAD_ID=\"<paste THREAD_ID printed by planner>\"",
        "MSG_PLANNER_TO_IMPLEMENTER=\"<paste MSG_PLANNER_TO_IMPLEMENTER printed by planner>\"",
        "MSG_IMPLEMENTER_TO_PLANNER=\"<paste MSG_IMPLEMENTER_TO_PLANNER printed by implementer>\"",
        "replace pasted bus and planner values before running",
        "replace pasted bus, planner, and implementer values before running",
        "status --thread \"$THREAD_ID\"",
        "reply_links:",
        "--reply-to \"$MSG_PLANNER_TO_IMPLEMENTER\"",
    ):
        assert snippet in text

    for pattern in (
        r"run_agent_comm\s+--bus\s+\"\$BUS\"\s+post",
        r"run_agent_comm\s+--bus\s+\"\$BUS\"\s+inbox\s+--agent\s+implementer",
        r"run_agent_comm\s+--bus\s+\"\$BUS\"\s+show\s+\"\$MSG_PLANNER_TO_IMPLEMENTER\"",
        r"run_agent_comm\s+--bus\s+\"\$BUS\"\s+ack\s+\"\$MSG_PLANNER_TO_IMPLEMENTER\"\s+--agent\s+implementer",
        r"run_agent_comm\s+--bus\s+\"\$BUS\"\s+inbox\s+--agent\s+planner",
        r"run_agent_comm\s+--bus\s+\"\$BUS\"\s+show\s+\"\$MSG_IMPLEMENTER_TO_PLANNER\"",
        r"run_agent_comm\s+--bus\s+\"\$BUS\"\s+status\s+--thread\s+\"\$THREAD_ID\"",
    ):
        assert re.search(pattern, text)


def test_fresh_agent_smoke_flow_commands_round_trip(tmp_path):
    bus = tmp_path / "smoke.db"
    planner_body = tmp_path / "planner.md"
    implementer_body = tmp_path / "implementer.md"
    planner_body.write_text(
        "# Smoke handoff\n\nArtifact: docs/smoke-tests/fresh-agent-sessions.md\n",
        encoding="utf-8",
    )
    implementer_body.write_text("# Smoke reply\n\nMailbox round trip works.\n", encoding="utf-8")

    def run_agent_comm(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "agent_comm", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

    run_agent_comm("--bus", str(bus), "init", "--project", "agents-together-smoke")
    run_agent_comm(
        "--bus",
        str(bus),
        "register",
        "--agent",
        "planner",
        "--display-name",
        "Planner",
        "--harness",
        "codex",
        "--role",
        "planner",
    )
    run_agent_comm(
        "--bus",
        str(bus),
        "register",
        "--agent",
        "implementer",
        "--display-name",
        "Implementer",
        "--harness",
        "claude",
        "--role",
        "implementer",
    )
    thread_id = _field(
        run_agent_comm(
            "--bus",
            str(bus),
            "start-thread",
            "--project",
            "agents-together-smoke",
            "--title",
            "Fresh session smoke",
        ).stdout,
        "thread",
    )
    planner_message_id = _field(
        run_agent_comm(
            "--bus",
            str(bus),
            "post",
            "--thread",
            thread_id,
            "--from",
            "planner",
            "--to",
            "implementer",
            "--subject",
            "Smoke handoff",
            "--body-file",
            str(planner_body),
        ).stdout,
        "message",
    )
    run_agent_comm(
        "--bus",
        str(bus),
        "artifact",
        "add",
        "--thread",
        thread_id,
        "--message",
        planner_message_id,
        "--path",
        "docs/smoke-tests/fresh-agent-sessions.md",
        "--description",
        "Smoke handoff guide",
    )

    assert planner_message_id in run_agent_comm(
        "--bus", str(bus), "inbox", "--agent", "implementer"
    ).stdout
    shown_handoff = run_agent_comm("--bus", str(bus), "show", planner_message_id).stdout
    assert "Artifact: docs/smoke-tests/fresh-agent-sessions.md" in shown_handoff
    assert "Smoke handoff guide" in shown_handoff
    run_agent_comm("--bus", str(bus), "ack", planner_message_id, "--agent", "implementer")

    implementer_message_id = _field(
        run_agent_comm(
            "--bus",
            str(bus),
            "post",
            "--thread",
            thread_id,
            "--from",
            "implementer",
            "--to",
            "planner",
            "--subject",
            "Smoke reply",
            "--body-file",
            str(implementer_body),
            "--reply-to",
            planner_message_id,
        ).stdout,
        "message",
    )
    assert implementer_message_id in run_agent_comm(
        "--bus", str(bus), "inbox", "--agent", "planner"
    ).stdout
    assert "Mailbox round trip works." in run_agent_comm(
        "--bus", str(bus), "show", implementer_message_id
    ).stdout
    status = run_agent_comm("--bus", str(bus), "status", "--thread", thread_id).stdout
    assert "reply_links:" in status
    assert f"message: {implementer_message_id}" in status
    assert f"replies_to: {planner_message_id}" in status
    run_agent_comm("--bus", str(bus), "ack", implementer_message_id, "--agent", "planner")


def _field(output: str, key: str) -> str:
    prefix = f"{key}: "
    for line in output.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix)
    raise AssertionError(f"{key!r} not found in output:\n{output}")
