from __future__ import annotations

import pytest

from agent_comm.paths import (
    BusResolutionError,
    canonical_origin,
    project_key,
    resolve_bus_path,
)


def test_explicit_bus_wins_over_env(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_COMM_BUS", str(tmp_path / "env.sqlite"))
    path = resolve_bus_path(bus=tmp_path / "explicit.sqlite", project=None, cwd=tmp_path)
    assert path.name == "explicit.sqlite"


def test_env_bus_wins_over_project(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_COMM_BUS", str(tmp_path / "env.sqlite"))
    path = resolve_bus_path(bus=None, project="demo", cwd=tmp_path)
    assert path.name == "env.sqlite"


def test_project_uses_default_state_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    path = resolve_bus_path(bus=None, project="Example Project", cwd=tmp_path)
    assert path.parent.parent == tmp_path / ".agent-comm" / "projects"
    assert path.parent.name.startswith("example-project-")
    assert len(path.parent.name.rsplit("-", 1)[-1]) == 12
    assert path.name == "bus.sqlite"


def test_missing_project_outside_git_fails(tmp_path):
    with pytest.raises(BusResolutionError, match="--project or --bus"):
        resolve_bus_path(bus=None, project=None, cwd=tmp_path)


def test_origin_canonicalizes_ssh_and_https_forms():
    assert canonical_origin("git@github.com:Example/Repo.git") == canonical_origin(
        "https://github.com/example/repo"
    )


def test_origin_preserves_non_default_url_ports():
    default_port = canonical_origin("ssh://git@example.com/org/repo.git")
    explicit_default_port = canonical_origin("ssh://git@example.com:22/org/repo.git")
    non_default_port = canonical_origin("ssh://git@example.com:2222/org/repo.git")
    assert explicit_default_port == default_port
    assert non_default_port != default_port
    assert non_default_port == "example.com:2222/org/repo"


def test_project_key_includes_slug_and_stable_hash():
    key = project_key("https://github.com/example/repo")
    assert key.startswith("github.com-example-repo-")
    assert len(key.rsplit("-", 1)[-1]) == 12


def test_two_worktrees_with_same_origin_share_default_bus(
    make_git_repo, tmp_path, monkeypatch
):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo_a = make_git_repo("a", origin="git@github.com:Example/Repo.git")
    repo_b = make_git_repo("b", origin="https://github.com/example/repo.git")
    assert resolve_bus_path(None, None, repo_a) == resolve_bus_path(None, None, repo_b)


def test_git_unavailable_falls_through_to_bus_resolution_error(tmp_path, monkeypatch):
    def raise_missing_git(*_args, **_kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr("agent_comm.paths.subprocess.run", raise_missing_git)
    with pytest.raises(BusResolutionError, match="--project or --bus"):
        resolve_bus_path(bus=None, project=None, cwd=tmp_path)
