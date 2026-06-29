from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


OLD_ACTIVE_NAMES = (
    "agent-comm",
    "agent_comm",
    "agents-together",
    "Agents Together",
    "agent-communication-protocol.md",
)


@pytest.fixture
def temp_bus(tmp_path: Path) -> Path:
    return tmp_path / "bus.sqlite"


@pytest.fixture
def bus(temp_bus: Path) -> Path:
    from switchboard.db import initialize_bus

    with initialize_bus(temp_bus):
        pass
    return temp_bus


@pytest.fixture
def make_git_repo(tmp_path: Path):
    def _make_git_repo(name: str, origin: str | None = None) -> Path:
        repo = tmp_path / name
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
        if origin is not None:
            subprocess.run(
                ["git", "remote", "add", "origin", origin],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            )
        return repo

    return _make_git_repo


@pytest.fixture
def cli_env() -> dict[str, str]:
    env = os.environ.copy()
    repo_root = Path(__file__).resolve().parents[1]
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(repo_root)
        if not existing_pythonpath
        else os.pathsep.join([str(repo_root), existing_pythonpath])
    )
    return env


@pytest.fixture
def run_cli(tmp_path: Path, cli_env: dict[str, str]):
    def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
        script = _switchboard_script(Path(sys.executable))
        return subprocess.run(
            [str(script), *args],
            cwd=tmp_path,
            env=cli_env,
            text=True,
            capture_output=True,
            check=False,
        )

    return _run_cli


def _switchboard_script(python_executable: Path) -> Path:
    script = python_executable.with_name("switchboard")
    if not script.exists():
        raise RuntimeError(f"switchboard console script is missing: {script}")
    return script


@pytest.fixture
def run_module_cli(tmp_path: Path, cli_env: dict[str, str]):
    def _run_module_cli(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "switchboard", *args],
            cwd=tmp_path,
            env=cli_env,
            text=True,
            capture_output=True,
            check=False,
        )

    return _run_module_cli
