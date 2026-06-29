from __future__ import annotations

import subprocess

from switchboard.paths import (
    canonical_origin,
    project_key,
    resolve_bus_path,
)


def test_explicit_bus_wins_over_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SWITCHBOARD_BUS", str(tmp_path / "env.sqlite"))
    path = resolve_bus_path(bus=tmp_path / "explicit.sqlite", project=None, cwd=tmp_path)
    assert path.name == "explicit.sqlite"


def test_env_bus_wins_over_project(tmp_path, monkeypatch):
    monkeypatch.setenv("SWITCHBOARD_BUS", str(tmp_path / "env.sqlite"))
    path = resolve_bus_path(bus=None, project="demo", cwd=tmp_path)
    assert path.name == "env.sqlite"


def test_old_agent_comm_env_var_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENT_COMM_BUS", str(tmp_path / "old-env.sqlite"))

    path = resolve_bus_path(bus=None, project="demo", cwd=tmp_path)

    assert path != tmp_path / "old-env.sqlite"
    assert path.parent.parent == tmp_path / "home" / ".switchboard" / "projects"


def test_project_uses_default_state_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    path = resolve_bus_path(bus=None, project="Example Project", cwd=tmp_path)
    assert path.parent.parent == tmp_path / ".switchboard" / "projects"
    assert path.parent.name.startswith("example-project-")
    assert len(path.parent.name.rsplit("-", 1)[-1]) == 12
    assert path.name == "bus.sqlite"


def test_explicit_project_cwd_like_name_is_not_derived_path_tag(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    path = resolve_bus_path(bus=None, project="cwd:/tmp/app", cwd=tmp_path)

    assert path.parent.name == project_key("cwd:/tmp/app")
    assert path.parent.name.startswith("cwd-tmp-app-")


def test_explicit_project_common_dir_like_name_is_not_derived_path_tag(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("HOME", str(tmp_path))

    path = resolve_bus_path(
        bus=None, project="git-common-dir:/tmp/repo/.git", cwd=tmp_path
    )

    assert path.parent.name == project_key("git-common-dir:/tmp/repo/.git")
    assert path.parent.name.startswith("git-common-dir-tmp-repo-.git-")


def test_project_key_treats_cwd_like_project_names_literally():
    assert project_key("cwd:/tmp/app") != project_key("cwd/tmp/app")


def test_project_key_treats_common_dir_like_project_names_literally():
    assert project_key("git-common-dir:/tmp/repo/.git") != project_key(
        "git-common-dir/tmp/repo"
    )


def test_missing_project_outside_git_uses_absolute_cwd(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    workdir = tmp_path / "plain-project"
    workdir.mkdir()

    path = resolve_bus_path(bus=None, project=None, cwd=workdir)

    assert path.parent.parent == home / ".switchboard" / "projects"
    assert path.parent.name.startswith("plain-project-")
    assert len(path.parent.name.rsplit("-", 1)[-1]) == 12
    assert path.name == "bus.sqlite"


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
    assert key.startswith("https-github.com-example-repo-")
    assert len(key.rsplit("-", 1)[-1]) == 12


def test_two_worktrees_with_same_origin_share_default_bus(
    make_git_repo, tmp_path, monkeypatch
):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo_a = make_git_repo("a", origin="git@github.com:Example/Repo.git")
    repo_b = make_git_repo("b", origin="https://github.com/example/repo.git")
    assert resolve_bus_path(None, None, repo_a) == resolve_bus_path(None, None, repo_b)


def test_linked_worktrees_without_origin_share_common_dir_bus(
    make_git_repo, tmp_path, monkeypatch
):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    main = make_git_repo("main")
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=main, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=main, check=True)
    (main / "README.md").write_text("# Main\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=main, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=main, check=True)
    linked = tmp_path / "linked"
    subprocess.run(
        ["git", "-C", str(main), "worktree", "add", str(linked)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert resolve_bus_path(None, None, main) == resolve_bus_path(None, None, linked)


def test_git_unavailable_uses_absolute_cwd(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    def raise_missing_git(*_args, **_kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr("switchboard.paths.subprocess.run", raise_missing_git)

    path = resolve_bus_path(bus=None, project=None, cwd=tmp_path)

    assert path.parent.parent == tmp_path / "home" / ".switchboard" / "projects"
    assert path.name == "bus.sqlite"
