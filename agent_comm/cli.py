from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys
import time

from . import __version__
from .db import BusError, UnsupportedSchemaVersion, check_bus, initialize_bus
from .paths import BusResolutionError, resolve_bus_path
from .repository import Artifact, Message, Repository, Thread

POLL_INTERVAL_SECONDS = 1.0

COMMANDS = (
    "init",
    "doctor",
    "backup",
    "restore",
    "register",
    "start-thread",
    "post",
    "inbox",
    "show",
    "ack",
    "wait",
    "artifact",
    "status",
    "export",
    "migrate",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-comm",
        description="Durable local mailbox for independent coding agents.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"agent-comm {__version__}",
    )
    parser.add_argument("--bus", help=argparse.SUPPRESS)
    parser.add_argument("--project", help=argparse.SUPPRESS)

    subparsers = parser.add_subparsers(dest="command")
    for command in COMMANDS:
        subparser = subparsers.add_parser(command)
        if command in {"init", "doctor"}:
            subparser.add_argument("--project", default=argparse.SUPPRESS)
        if command == "init":
            subparser.set_defaults(handler=_handle_init)
        elif command == "doctor":
            subparser.set_defaults(handler=_handle_doctor)
        elif command == "migrate":
            subparser.set_defaults(handler=_handle_migrate)
        elif command == "register":
            subparser.add_argument("--agent", required=True)
            subparser.add_argument("--display-name")
            subparser.add_argument("--harness")
            subparser.add_argument("--role")
            subparser.set_defaults(handler=_handle_register)
        elif command == "start-thread":
            subparser.add_argument("--project", required=True)
            subparser.add_argument("--title", required=True)
            subparser.set_defaults(handler=_handle_start_thread)
        elif command == "post":
            subparser.add_argument("--thread", required=True)
            subparser.add_argument("--from", dest="from_agent", required=True)
            subparser.add_argument("--to", dest="to_agent", required=True)
            subparser.add_argument("--subject", required=True)
            subparser.add_argument("--body-file", required=True)
            subparser.add_argument("--reply-to", action="append", default=[])
            subparser.set_defaults(handler=_handle_post)
        elif command == "inbox":
            subparser.add_argument("--agent", required=True)
            subparser.set_defaults(handler=_handle_inbox)
        elif command == "show":
            subparser.add_argument("message")
            subparser.set_defaults(handler=_handle_show)
        elif command == "ack":
            subparser.add_argument("message")
            subparser.add_argument("--agent", required=True)
            subparser.set_defaults(handler=_handle_ack)
        elif command == "wait":
            subparser.add_argument("--agent", required=True)
            subparser.add_argument("-f", "--follow", action="store_true")
            subparser.add_argument("--timeout", type=float, help=argparse.SUPPRESS)
            subparser.set_defaults(handler=_handle_wait)
        elif command == "artifact":
            artifact_subparsers = subparser.add_subparsers(
                dest="artifact_command",
                required=True,
            )
            add = artifact_subparsers.add_parser("add")
            add.add_argument("--thread", required=True)
            add.add_argument("--message")
            add.add_argument("--path")
            add.add_argument("--git-ref")
            add.add_argument("--description")
            add.set_defaults(handler=_handle_artifact_add)
        else:
            subparser.set_defaults(handler=_handle_placeholder)

    return parser


def _handle_placeholder(args: argparse.Namespace) -> int:
    print(f"ERR_NOT_IMPLEMENTED: {args.command} is not implemented yet")
    return 1


def _handle_init(args: argparse.Namespace) -> int:
    try:
        path = resolve_bus_path(args.bus, args.project, cwd=None)
        project_id = args.project or path.parent.name
        with initialize_bus(path, project_id):
            pass
    except (BusResolutionError, BusError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Initialized agent-comm bus at {path}")
    return 0


def _handle_doctor(args: argparse.Namespace) -> int:
    try:
        path = resolve_bus_path(args.bus, args.project, cwd=None)
        check_bus(path)
    except UnsupportedSchemaVersion as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except (BusResolutionError, BusError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("agent-comm doctor: ok")
    return 0


def _handle_register(args: argparse.Namespace) -> int:
    try:
        agent = _repo(args).register_agent(
            args.agent,
            display_name=args.display_name,
            harness=args.harness,
            role=args.role,
        )
    except _CLI_ERRORS as exc:
        return _print_error(exc)
    print(f"agent: {agent.id}")
    return 0


def _handle_start_thread(args: argparse.Namespace) -> int:
    try:
        path = _bus_path(args)
        project_id = args.project or path.parent.name
        thread = _repo(args).start_thread(args.title, project_id)
    except _CLI_ERRORS as exc:
        return _print_error(exc)
    _print_thread(thread)
    return 0


def _handle_post(args: argparse.Namespace) -> int:
    try:
        body = Path(args.body_file).read_bytes().decode("utf-8")
        message = _repo(args).post_message(
            args.thread,
            args.from_agent,
            args.to_agent,
            args.subject,
            body,
            reply_to=args.reply_to,
        )
    except (OSError, UnicodeDecodeError) as exc:
        return _print_error(exc)
    except _CLI_ERRORS as exc:
        return _print_error(exc)
    _print_message(message, include_body=False)
    return 0


def _handle_inbox(args: argparse.Namespace) -> int:
    try:
        messages = _repo(args).inbox(args.agent)
    except _CLI_ERRORS as exc:
        return _print_error(exc)
    _print_messages(messages, include_body=False)
    return 0


def _handle_show(args: argparse.Namespace) -> int:
    try:
        repo = _repo(args)
        message = repo.get_message(args.message)
        artifacts = repo.artifacts_for_message(args.message)
    except _CLI_ERRORS as exc:
        return _print_error(exc)
    _print_message(message, include_body=True)
    _print_artifacts(artifacts)
    return 0


def _handle_ack(args: argparse.Namespace) -> int:
    try:
        message = _repo(args).ack_message(args.message, args.agent)
    except _CLI_ERRORS as exc:
        return _print_error(exc)
    print(f"message: {message.id}")
    print(f"acked_at: {message.acked_at}")
    return 0


def _handle_wait(args: argparse.Namespace) -> int:
    if args.timeout is not None and args.timeout < 0:
        print("ERROR: --timeout must be non-negative", file=sys.stderr)
        return 1
    try:
        repo = _repo(args)
        messages = _wait_for_messages(
            repo,
            args.agent,
            timeout=args.timeout,
            follow=args.follow,
        )
    except _CLI_ERRORS as exc:
        return _print_error(exc)
    if args.follow:
        return 0
    if not messages:
        print("ERROR: timed out waiting for messages", file=sys.stderr)
        return 1
    _print_messages(messages, include_body=False)
    return 0


def _handle_artifact_add(args: argparse.Namespace) -> int:
    try:
        artifact = _repo(args).add_artifact(
            args.thread,
            args.message,
            args.path,
            args.git_ref,
            args.description,
        )
    except _CLI_ERRORS as exc:
        return _print_error(exc)
    _print_artifact(artifact)
    return 0


def _handle_migrate(_args: argparse.Namespace) -> int:
    message = "ERR_NOT_IMPLEMENTED: migrate is not implemented yet"
    print(message)
    print(message, file=sys.stderr)
    return 1


_CLI_ERRORS = (
    BusResolutionError,
    BusError,
    UnsupportedSchemaVersion,
    ValueError,
    PermissionError,
)


def _repo(args: argparse.Namespace) -> Repository:
    path = _bus_path(args)
    if not path.exists():
        raise BusError(f"bus database does not exist: {path}")
    return Repository(path)


def _bus_path(args: argparse.Namespace) -> Path:
    return resolve_bus_path(args.bus, args.project, cwd=None)


def _print_error(exc: BaseException) -> int:
    print(f"ERROR: {exc}", file=sys.stderr)
    return 1


def _wait_for_messages(
    repo: Repository,
    agent_id: str,
    *,
    timeout: float | None,
    follow: bool,
) -> list[Message]:
    deadline = None if timeout is None else time.monotonic() + timeout
    printed_ids: set[str] = set()
    collected: list[Message] = []

    while True:
        messages = [
            message
            for message in repo.inbox(agent_id)
            if follow or message.id not in printed_ids
        ]
        new_messages = [message for message in messages if message.id not in printed_ids]
        if new_messages:
            collected.extend(new_messages)
            if not follow:
                return collected
            _print_messages(new_messages, include_body=False)
            sys.stdout.flush()
            printed_ids.update(message.id for message in new_messages)
        if deadline is not None and time.monotonic() >= deadline:
            return collected
        sleep_for = POLL_INTERVAL_SECONDS
        if deadline is not None:
            sleep_for = min(
                POLL_INTERVAL_SECONDS,
                max(0.0, deadline - time.monotonic()),
            )
        time.sleep(sleep_for)


def _print_thread(thread: Thread) -> None:
    print(f"thread: {thread.id}")
    print(f"project: {thread.project_id}")
    print(f"title: {thread.title}")
    print(f"created_at: {thread.created_at}")
    print(f"updated_at: {thread.updated_at}")


def _print_messages(messages: list[Message], *, include_body: bool) -> None:
    for index, message in enumerate(messages):
        if index:
            print()
        _print_message(message, include_body=include_body)


def _print_message(message: Message, *, include_body: bool) -> None:
    print(f"message: {message.id}")
    print(f"thread: {message.thread_id}")
    print(f"seq: {message.seq}")
    print(f"from: {message.from_agent}")
    print(f"to: {message.to_agent}")
    print(f"subject: {message.subject}")
    print(f"created_at: {message.created_at}")
    print(f"acked_at: {message.acked_at or ''}")
    if include_body:
        print()
        print(message.body_md, end="" if message.body_md.endswith("\n") else "\n")


def _print_artifact(artifact: Artifact) -> None:
    print(f"artifact: {artifact.id}")
    print(f"thread: {artifact.thread_id}")
    print(f"message: {artifact.message_id or ''}")
    print(f"path: {artifact.path or ''}")
    print(f"git_ref: {artifact.git_ref or ''}")
    print(f"description: {artifact.description or ''}")
    print(f"created_at: {artifact.created_at}")


def _print_artifacts(artifacts: list[Artifact]) -> None:
    if not artifacts:
        return
    print()
    print("artifacts:")
    for artifact in artifacts:
        print(f"- artifact: {artifact.id}")
        print(f"  thread: {artifact.thread_id}")
        print(f"  message: {artifact.message_id or ''}")
        print(f"  path: {artifact.path or ''}")
        print(f"  git_ref: {artifact.git_ref or ''}")
        print(f"  description: {artifact.description or ''}")
        print(f"  created_at: {artifact.created_at}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args)
