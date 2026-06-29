from __future__ import annotations

from pathlib import Path
import sys

import agent_comm.cli


def test_help_and_version_work(run_cli):
    help_result = run_cli("--help")
    version_result = run_cli("--version")
    assert help_result.returncode == 0
    assert "agent-comm" in help_result.stdout
    assert "init" in help_result.stdout
    assert version_result.returncode == 0
    assert "agent-comm 0.1.0" in version_result.stdout


def test_python_module_entrypoint_matches_cli(run_cli, run_module_cli):
    cli_result = run_cli("--help")
    result = run_module_cli("--help")
    assert result.returncode == 0
    assert cli_result.returncode == 0
    assert "durable local mailbox" in result.stdout.lower()


def test_cli_rejects_unsupported_python_before_version(monkeypatch, capsys):
    monkeypatch.setattr(agent_comm.cli.sys, "version_info", (3, 11, 9, "final", 0))
    monkeypatch.setattr(
        agent_comm.cli.sys,
        "version",
        "3.11.9 (test unsupported interpreter)",
    )

    result = agent_comm.cli.main(["--version"])
    captured = capsys.readouterr()

    assert result == 1
    assert captured.out == ""
    assert "requires Python 3.12 or newer" in captured.err
    assert sys.executable in captured.err
    assert "agent-comm 0.1.0" not in captured.out + captured.err


def test_local_sqlite_bus_artifacts_are_ignored():
    gitignore = Path(__file__).resolve().parents[1] / ".gitignore"
    ignored_patterns = set(gitignore.read_text().splitlines())
    assert "*.sqlite" in ignored_patterns
    assert "*.sqlite-wal" in ignored_patterns
    assert "*.sqlite-shm" in ignored_patterns
    assert ".agent-comm/" in ignored_patterns


def test_implemented_commands_without_required_arguments_show_usage(run_cli):
    result = run_cli("status")
    assert result.returncode != 0
    assert "ERR_NOT_IMPLEMENTED" not in result.stdout
    assert "usage:" in result.stderr
    assert "--thread" in result.stderr


def test_migrate_uses_spec_required_error(run_cli):
    result = run_cli("migrate")
    assert result.returncode != 0
    assert "ERR_NOT_IMPLEMENTED: migrate is not implemented yet" in result.stdout


def test_console_script_path_is_required(tmp_path):
    from conftest import _agent_comm_script

    missing_python = tmp_path / "bin" / "python"
    try:
        _agent_comm_script(missing_python)
    except RuntimeError as exc:
        assert str(missing_python.with_name("agent-comm")) in str(exc)
    else:
        raise AssertionError("expected missing console script to fail clearly")
