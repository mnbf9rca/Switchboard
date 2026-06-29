from __future__ import annotations

import json
import os
import re
from pathlib import Path
import subprocess
import sys

from scripts.validate_skill_protocols import validate_skill_protocols


ROOT = Path(__file__).resolve().parents[1]

SKILLS = {
    "coordinate-as-planner": {
        "description": "Coordinate as the planning agent using agent-comm. Use when preparing implementation handoffs, sending deliberate messages to implementers, answering implementation questions, reviewing ready work, or accepting completed work through a durable local agent mailbox.",
        "triggers": [
            "preparing implementation handoffs",
            "sending deliberate messages",
            "answering implementation questions",
            "reviewing ready work",
            "accepting completed work",
            "durable local agent mailbox",
        ],
    },
    "coordinate-as-implementer": {
        "description": "Coordinate as the implementation agent using agent-comm. Use when receiving planner handoffs, reading durable agent messages, acknowledging work, asking implementation questions, reporting blockers, or signaling ready-for-review work through a local mailbox.",
        "triggers": [
            "receiving planner handoffs",
            "reading durable agent messages",
            "acknowledging work",
            "asking implementation questions",
            "reporting blockers",
            "signaling ready-for-review work",
            "local mailbox",
        ],
    },
}

FORBIDDEN_TERMS = [
    "post --type",
    "wait --type",
    "allow-unstructured",
    "Intent:",
    "Thread-State:",
    "stale claim",
    "checkpoint",
    ".agent-comm.json",
    ".agent-comm.local.json",
    "events table",
    "status/export",
    "agent-comm status",
    "agent-comm export",
]
EXAMPLE_HEADER_PATTERNS = [
    "Requested action:",
    "Expected reply:",
    "Constraints:",
    "Verification:",
]

EXAMPLES = [
    "planner-handoff.md",
    "implementer-question.md",
    "implementer-blocker.md",
    "ready-for-review.md",
    "review-findings.md",
]


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text()
    assert text.startswith("---\n"), f"{path} is missing YAML frontmatter"
    _, raw_frontmatter, body = text.split("---\n", 2)
    frontmatter: dict[str, str] = {}
    for line in raw_frontmatter.splitlines():
        key, value = line.split(": ", 1)
        frontmatter[key] = value
    return frontmatter, body


def test_skills_have_required_frontmatter_and_trigger_rich_descriptions():
    for skill_name, expected in SKILLS.items():
        path = ROOT / "skills" / skill_name / "SKILL.md"
        frontmatter, body = parse_frontmatter(path)

        assert set(frontmatter) == {"name", "description"}
        assert frontmatter["name"] == skill_name
        assert frontmatter["name"] == path.parent.name
        assert frontmatter["description"] == expected["description"]
        for trigger in expected["triggers"]:
            assert trigger in frontmatter["description"]
        assert "agent-comm --version" in body


def test_each_skill_has_protocol_reference_and_validator_confirms_duplication():
    paths = [
        ROOT / "skills" / skill_name / "references" / "agent-communication-protocol.md"
        for skill_name in SKILLS
    ]
    for path in paths:
        assert path.exists()

    validate_skill_protocols(ROOT)


def test_protocol_guides_agent_communication_not_cli_help():
    protocol = (
        ROOT
        / "skills"
        / "coordinate-as-planner"
        / "references"
        / "agent-communication-protocol.md"
    ).read_text()

    for section in (
        "## Communication Principles",
        "## What To Include",
        "## Planner Behavior",
        "## Implementer Behavior",
        "## Threads, Replies, and Artifacts",
        "## Waiting and Monitoring",
        "## Conflict Handling",
        "## Minimal Command Appendix",
    ):
        assert section in protocol

    for guidance in (
        "Send a mailbox message when another agent must act",
        "Do not send routine progress updates",
        "Every message should be addressed, intentional, and useful on its own",
        "The requested action or decision.",
        "Avoid ceremony and rigid headers",
        "Create or update project artifacts before messaging",
        "read your inbox before starting work",
        "Acknowledge only after reading",
        "Use one thread for one coherent stream of work or review",
        "Use wait or follow only when you are actually blocked",
        "Do not invent precedence rules in the tool layer",
    ):
        assert guidance in protocol

    command_appendix = protocol.split("## Minimal Command Appendix", 1)[1]
    before_appendix = protocol.split("## Minimal Command Appendix", 1)[0]
    assert before_appendix.count("agent-comm ") == 0
    assert command_appendix.count("agent-comm ") <= 14


def test_plugin_manifests_expose_skills_as_harness_adapters():
    claude_expected = {
        "name": "agents-together",
        "version": "0.1.0",
        "description": "Durable local coordination workflows for independent coding agents",
        "skills": "./skills/",
    }
    assert json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text()) == claude_expected

    codex = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
    assert codex["name"] == claude_expected["name"]
    assert codex["version"] == claude_expected["version"]
    assert codex["description"] == claude_expected["description"]
    assert codex["skills"] == claude_expected["skills"]
    assert isinstance(codex["author"], dict)
    assert codex["author"]["name"]
    assert isinstance(codex["interface"], dict)
    for key in (
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
        "capabilities",
    ):
        assert codex["interface"][key]


def test_repo_local_codex_marketplace_exposes_plugin_root():
    marketplace_root = ROOT / ".agents" / "plugins"
    marketplace = json.loads((marketplace_root / "marketplace.json").read_text())

    assert marketplace == {
        "name": "agents-together-local",
        "interface": {
            "displayName": "Agents Together Local",
        },
        "plugins": [
            {
                "name": "agents-together",
                "source": {
                    "source": "local",
                    "path": "./plugins/agents-together",
                },
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": "Productivity",
            }
        ],
    }

    assert (ROOT / ".codex-plugin" / "plugin.json").is_file()
    assert (ROOT / "skills" / "coordinate-as-planner" / "SKILL.md").is_file()


def test_plugin_launcher_runs_from_outside_repo(tmp_path):
    launcher = ROOT / "scripts" / "agent-comm"

    assert launcher.is_file()
    assert os.access(launcher, os.X_OK)

    result = subprocess.run(
        [str(launcher), "--version"],
        cwd=tmp_path,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.stdout.strip() == "agent-comm 0.1.0"


def test_plugin_launcher_rejects_python_bin_below_supported_version(tmp_path):
    launcher = ROOT / "scripts" / "agent-comm"
    fake_python = tmp_path / "python"
    fake_python.write_text(
        "#!/usr/bin/env sh\n"
        "case \"$1\" in\n"
        "  -c) exit 1 ;;\n"
        "  *) echo 'unsupported python should not run agent_comm' >&2; exit 42 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    result = subprocess.run(
        [str(launcher), "--version"],
        cwd=tmp_path,
        env={**os.environ, "PYTHON_BIN": str(fake_python)},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 127
    assert result.stdout == ""
    assert "requires Python 3.12 or newer" in result.stderr
    assert "unsupported python should not run agent_comm" not in result.stderr


def test_codex_plugin_bundle_builds_from_single_source_tree(tmp_path):
    output = tmp_path / "agents-together"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "build_codex_plugin.py"),
            "--output",
            str(output),
            "--cachebuster",
            "test-123",
        ],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert "Built Codex plugin" in result.stdout
    manifest = json.loads((output / ".codex-plugin" / "plugin.json").read_text())
    assert manifest["version"] == "0.1.0+codex.test-123"

    expected_files = [
        ".codex-plugin/plugin.json",
        ".generated.json",
        "README.md",
        "agent_comm/__main__.py",
        "agent_comm/cli.py",
        "scripts/agent-comm",
        "skills/coordinate-as-planner/SKILL.md",
        "skills/coordinate-as-planner/references/agent-communication-protocol.md",
        "skills/coordinate-as-implementer/SKILL.md",
    ]
    for relative_path in expected_files:
        assert (output / relative_path).is_file()

    for forbidden in (
        ".git",
        ".venv",
        ".pytest_cache",
        "dist",
        "tests",
        "handover.md",
        "plugins",
        "uv.lock",
    ):
        assert not (output / forbidden).exists()

    launcher = output / "scripts" / "agent-comm"
    assert os.access(launcher, os.X_OK)
    version = subprocess.run(
        [str(launcher), "--version"],
        cwd=tmp_path,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert version.stdout.strip() == "agent-comm 0.1.0"


def test_examples_exist_as_markdown_message_bodies():
    for name in EXAMPLES:
        path = ROOT / "examples" / name
        text = path.read_text()
        assert text.startswith("# ")
        assert "agent-comm" not in text.lower() or "```" not in text
        for pattern in EXAMPLE_HEADER_PATTERNS:
            assert pattern not in text


def test_skill_layer_does_not_reference_unimplemented_or_forbidden_protocol_terms():
    paths = [
        *ROOT.glob("skills/**/SKILL.md"),
        *ROOT.glob("skills/**/references/*.md"),
        *ROOT.glob("examples/*.md"),
        ROOT / ".codex-plugin" / "plugin.json",
        ROOT / ".claude-plugin" / "plugin.json",
    ]
    assert paths
    for path in paths:
        text = path.read_text()
        for term in FORBIDDEN_TERMS:
            assert term not in text, f"{path} contains forbidden term {term!r}"
