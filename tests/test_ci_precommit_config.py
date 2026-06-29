from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_ci_runs_pytest_and_skill_protocol_validator():
    workflow = ROOT / ".github" / "workflows" / "ci.yml"
    text = workflow.read_text()

    assert "jobs:" in text
    assert "steps:" in text
    assert "uses: actions/checkout@v4" in text
    assert "uses: astral-sh/setup-uv@v5" in text
    assert "uv run pytest" in text
    assert "uv run python scripts/validate_skill_protocols.py" in text


def test_pre_commit_runs_skill_protocol_validator_as_local_hook():
    config = ROOT / ".pre-commit-config.yaml"
    text = config.read_text()

    assert "repo: local" in text
    assert "id: validate-skill-protocols" in text
    assert "entry: python3 scripts/validate_skill_protocols.py" in text
    assert "language: system" in text
    assert "pass_filenames: false" in text


def test_readme_documents_skill_protocol_validator():
    readme = ROOT / "README.md"

    assert "uv run python scripts/validate_skill_protocols.py" in readme.read_text()


def test_protocol_validator_cli_prints_compared_paths():
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "validate_skill_protocols.py"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Validated 2 skill protocol references:" in result.stdout
    assert "skills/coordinate-as-planner/references/agent-communication-protocol.md" in result.stdout
    assert "skills/coordinate-as-implementer/references/agent-communication-protocol.md" in result.stdout


def test_protocol_validator_cli_reports_byte_mismatches(tmp_path):
    first = tmp_path / "skills" / "one" / "references"
    second = tmp_path / "skills" / "two" / "references"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    protocol = "agent-communication-protocol.md"
    (first / protocol).write_bytes(b"same text\n")
    (second / protocol).write_bytes(b"same text\r\n")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "validate_skill_protocols.py"),
            str(tmp_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "ERR_SKILL_PROTOCOLS" in result.stderr
    assert str(second / protocol) in result.stderr
