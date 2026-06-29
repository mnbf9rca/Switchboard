from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sqlite3
import sys
import time

from . import __version__
from .backup import backup_bus, restore_bus
from .db import BusError, UnsupportedSchemaVersion, initialize_bus
from .doctor import core_health
from .export import load_thread_records, write_thread_export
from .paths import BusResolutionError, resolve_bus_path
from .repository import Artifact, Message, Repository, ReplyLink, Thread

POLL_INTERVAL_SECONDS = 1.0

COMMANDS = (
    "init",
    "doctor",
    "backup",
    "restore",
    "send",
    "register",
    "start-thread",
    "post",
    "inbox",
    "show",
    "reply",
    "next",
    "ack",
    "wait",
    "artifact",
    "status",
    "export",
    "migrate",
)

MIN_PYTHON = (3, 12)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="switchboard",
        description="Durable local mailbox for independent coding agents.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"switchboard {__version__}",
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
        elif command == "backup":
            subparser.add_argument("--out", required=True)
            subparser.set_defaults(handler=_handle_backup)
        elif command == "restore":
            subparser.add_argument("--from", dest="from_path", required=True)
            subparser.set_defaults(handler=_handle_restore)
        elif command == "send":
            subparser.add_argument("--as", dest="as_agent", required=True)
            subparser.add_argument("--to", required=True)
            subparser.add_argument("--title")
            subparser.add_argument("--in-thread")
            subparser.add_argument("--artifact", action="append", default=[])
            subparser.add_argument("--body-file")
            subparser.add_argument("--stdin", action="store_true")
            subparser.add_argument("--wait", action="store_true")
            subparser.add_argument("--timeout", type=float, help=argparse.SUPPRESS)
            subparser.add_argument("message", nargs="*")
            subparser.set_defaults(handler=_handle_send)
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
            subparser.add_argument("--agent", dest="agent")
            subparser.add_argument("--as", dest="as_agent")
            subparser.set_defaults(handler=_handle_inbox)
        elif command == "show":
            subparser.add_argument("message")
            subparser.set_defaults(handler=_handle_show)
        elif command == "reply":
            subparser.add_argument("message_id")
            subparser.add_argument("--as", dest="as_agent", required=True)
            subparser.add_argument("--artifact", action="append", default=[])
            subparser.add_argument("--body-file")
            subparser.add_argument("--stdin", action="store_true")
            subparser.add_argument("--wait", action="store_true")
            subparser.add_argument("--timeout", type=float, help=argparse.SUPPRESS)
            subparser.add_argument("message", nargs="*")
            subparser.set_defaults(handler=_handle_reply)
        elif command == "next":
            subparser.add_argument("--as", dest="as_agent", required=True)
            subparser.set_defaults(handler=_handle_next)
        elif command == "ack":
            subparser.add_argument("message")
            subparser.add_argument("--agent", dest="agent")
            subparser.add_argument("--as", dest="as_agent")
            subparser.set_defaults(handler=_handle_ack)
        elif command == "wait":
            subparser.add_argument("--agent", dest="agent")
            subparser.add_argument("--as", dest="as_agent")
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
        elif command == "status":
            subparser.add_argument("--thread", required=True)
            subparser.set_defaults(handler=_handle_status)
        elif command == "export":
            subparser.add_argument("--thread", required=True)
            subparser.add_argument("--redacted", action="store_true")
            subparser.add_argument("--bodyless", action="store_true")
            subparser.set_defaults(handler=_handle_export)
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
    print(f"Initialized switchboard bus at {path}")
    return 0


def _handle_doctor(args: argparse.Namespace) -> int:
    try:
        path = resolve_bus_path(args.bus, args.project, cwd=None)
        lines = core_health(path)
    except UnsupportedSchemaVersion as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except (BusResolutionError, BusError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("\n".join(lines))
    return 0


def _handle_backup(args: argparse.Namespace) -> int:
    try:
        path = resolve_bus_path(args.bus, args.project, cwd=None)
        output = backup_bus(path, args.out)
    except _CLI_ERRORS as exc:
        return _print_error(exc)
    print(f"backup: {output}")
    return 0


def _handle_restore(args: argparse.Namespace) -> int:
    try:
        path = resolve_bus_path(args.bus, args.project, cwd=None)
        restored = restore_bus(path, args.from_path)
    except _CLI_ERRORS as exc:
        return _print_error(exc)
    print(f"restored: {restored}")
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


def _handle_send(args: argparse.Namespace) -> int:
    try:
        body = _read_body(args)
        repo = _repo_create(args)
        created_agents = [
            agent_id
            for agent_id in (args.as_agent, args.to)
            if _ensure_agent(repo, agent_id)
        ]
        if args.in_thread:
            try:
                thread = repo.get_thread(args.in_thread)
            except ValueError as exc:
                raise ValueError(f"thread not found: {args.in_thread}") from exc
        else:
            title = args.title or _derive_title(body)
            thread = repo.start_thread(title, _bus_path(args).parent.name)
        message = repo.post_message(
            thread.id,
            args.as_agent,
            args.to,
            args.title or thread.title,
            body,
        )
        artifacts = _attach_artifacts(repo, thread.id, message.id, args.artifact)
    except (OSError, UnicodeDecodeError) as exc:
        return _print_error(exc)
    except _CLI_ERRORS as exc:
        return _print_error(exc)

    _print_message(message, include_body=False)
    for agent_id in created_agents:
        print(f"agent_created: {agent_id}")
    for artifact in artifacts:
        _print_artifact(artifact)
    if args.wait:
        return _wait_for_reply_to_message(
            repo,
            waiting_agent=args.as_agent,
            thread_id=message.thread_id,
            after_seq=message.seq,
            timeout=args.timeout,
        )
    return 0


def _derive_title(body: str) -> str:
    first_line = body.strip().splitlines()[0] if body.strip() else "Message"
    return first_line[:80] or "Message"


def _handle_inbox(args: argparse.Namespace) -> int:
    try:
        agent = _agent_arg(args)
        messages = _repo_read(args).inbox(agent)
    except _CLI_ERRORS as exc:
        return _print_error(exc)
    _print_messages(messages, include_body=False)
    return 0


def _handle_show(args: argparse.Namespace) -> int:
    try:
        repo = _repo_read(args)
        message = repo.get_message(args.message)
        artifacts = repo.artifacts_for_message(args.message)
    except _CLI_ERRORS as exc:
        return _print_error(exc)
    _print_message(message, include_body=True)
    _print_artifacts(artifacts)
    return 0


def _handle_ack(args: argparse.Namespace) -> int:
    try:
        agent = _agent_arg(args)
        message = _repo(args).ack_message(args.message, agent)
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
        agent = _agent_arg(args)
        repo = _repo_read(args)
        messages = _wait_for_messages(
            repo,
            agent,
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


def _handle_reply(args: argparse.Namespace) -> int:
    try:
        body = _read_body(args)
        repo = _repo(args)
        original = repo.get_message(args.message_id)
        if original.to_agent != args.as_agent:
            raise PermissionError("only the message recipient can reply")
        _ensure_agent(repo, args.as_agent)
        message = repo.post_message(
            original.thread_id,
            args.as_agent,
            original.from_agent,
            f"Re: {original.subject}",
            body,
            reply_to=[original.id],
        )
        acked = repo.ack_message(original.id, args.as_agent)
        artifacts = _attach_artifacts(repo, original.thread_id, message.id, args.artifact)
    except (OSError, UnicodeDecodeError) as exc:
        return _print_error(exc)
    except _CLI_ERRORS as exc:
        return _print_error(exc)

    _print_message(message, include_body=False)
    print(f"acked: {acked.id}")
    for artifact in artifacts:
        _print_artifact(artifact)
    if args.wait:
        return _wait_for_reply_to_message(
            repo,
            waiting_agent=args.as_agent,
            thread_id=message.thread_id,
            after_seq=message.seq,
            timeout=args.timeout,
        )
    return 0


def _handle_next(args: argparse.Namespace) -> int:
    try:
        messages = _repo_read(args).inbox(args.as_agent)
    except _CLI_ERRORS as exc:
        return _print_error(exc)
    if not messages:
        return 0
    _print_message(messages[0], include_body=True)
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


def _handle_status(args: argparse.Namespace) -> int:
    try:
        records = load_thread_records(_repo(args), args.thread)
    except _CLI_ERRORS as exc:
        return _print_error(exc)
    _print_status(
        records.thread,
        records.unread_messages,
        records.messages,
        records.reply_links,
        records.artifacts,
    )
    return 0


def _handle_export(args: argparse.Namespace) -> int:
    try:
        repo = _repo(args)
        records = load_thread_records(repo, args.thread)
        output_path = write_thread_export(
            _bus_path(args),
            records,
            include_bodies=not (args.redacted or args.bodyless),
        )
    except OSError as exc:
        return _print_error(exc)
    except _CLI_ERRORS as exc:
        return _print_error(exc)
    print(f"export: {output_path}")
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
    sqlite3.Error,
)


def _repo(args: argparse.Namespace) -> Repository:
    path = _bus_path(args)
    if not path.exists():
        raise BusError(f"mailbox does not exist; send a message first: {path}")
    return Repository(path)


def _repo_read(args: argparse.Namespace) -> Repository:
    path = _bus_path(args)
    return Repository(path, readonly=True)


def _repo_create(args: argparse.Namespace) -> Repository:
    path = _bus_path(args)
    project_id = path.parent.name
    with initialize_bus(path, project_id):
        pass
    return Repository(path)


def _agent_arg(args: argparse.Namespace) -> str:
    agent = getattr(args, "as_agent", None) or getattr(args, "agent", None)
    if not agent:
        raise ValueError("--as or --agent is required")
    return agent


def _bus_path(args: argparse.Namespace) -> Path:
    return resolve_bus_path(args.bus, args.project, cwd=None)


def _read_body(args: argparse.Namespace) -> str:
    body_sources = (
        int(bool(args.message))
        + int(bool(args.body_file))
        + int(bool(args.stdin))
    )
    if body_sources != 1:
        raise ValueError("send/reply requires exactly one body source")
    if args.body_file:
        return Path(args.body_file).read_bytes().decode("utf-8")
    if args.stdin:
        return sys.stdin.read()
    return " ".join(args.message)


def _ensure_agent(repo: Repository, agent_id: str) -> bool:
    try:
        repo.get_agent(agent_id)
        return False
    except ValueError:
        repo.register_agent(agent_id)
        return True


def _attach_artifacts(
    repo: Repository,
    thread_id: str,
    message_id: str,
    paths: list[str],
) -> list[Artifact]:
    return [
        repo.add_artifact(
            thread_id,
            message_id,
            path,
            None,
            "linked artifact",
        )
        for path in paths
    ]


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


def _wait_for_reply_to_message(
    repo: Repository,
    *,
    waiting_agent: str,
    thread_id: str,
    after_seq: int,
    timeout: float | None,
) -> int:
    print(f"waiting_for_reply_in_thread: {thread_id}")
    print("interrupt: press Ctrl-C to stop waiting")
    deadline = None if timeout is None else time.monotonic() + timeout
    while True:
        messages = [
            message
            for message in repo.inbox(waiting_agent)
            if message.thread_id == thread_id and message.seq > after_seq
        ]
        if messages:
            _print_messages(messages, include_body=False)
            return 0
        if deadline is not None and time.monotonic() >= deadline:
            print("ERROR: timed out waiting for reply", file=sys.stderr)
            return 1
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


def _print_status(
    thread: Thread,
    unread_messages: list[Message],
    recent_messages: list[Message],
    reply_links: list[ReplyLink],
    artifacts: list[Artifact],
) -> None:
    _print_thread(thread)
    print()
    print("unread_messages:")
    if unread_messages:
        for message in unread_messages:
            _print_status_message_item(message)
    else:
        print("- none")
    print()
    print("recent_messages:")
    if recent_messages:
        for message in recent_messages:
            _print_status_message_item(message)
    else:
        print("- none")
    print()
    print("reply_links:")
    if reply_links:
        for link in reply_links:
            print(f"- message: {link.message_id}")
            print(f"  replies_to: {link.reply_to_message_id}")
    else:
        print("- none")
    print()
    print("artifacts:")
    if artifacts:
        for artifact in artifacts:
            print(f"- artifact: {artifact.id}")
            print(f"  message: {artifact.message_id or ''}")
            print(f"  path: {artifact.path or ''}")
            print(f"  git_ref: {artifact.git_ref or ''}")
            print(f"  description: {artifact.description or ''}")
            print(f"  created_at: {artifact.created_at}")
    else:
        print("- none")


def _print_status_message_item(message: Message) -> None:
    print(f"- message: {message.id}")
    print(f"  seq: {message.seq}")
    print(f"  from: {message.from_agent}")
    print(f"  to: {message.to_agent}")
    print(f"  subject: {message.subject}")
    print(f"  created_at: {message.created_at}")
    print(f"  acked_at: {message.acked_at or ''}")


def main(argv: Sequence[str] | None = None) -> int:
    if sys.version_info < MIN_PYTHON:
        current = ".".join(str(part) for part in sys.version_info[:3])
        required = ".".join(str(part) for part in MIN_PYTHON)
        print(
            f"ERROR: switchboard requires Python {required} or newer; "
            f"{sys.executable} is Python {current}.",
            file=sys.stderr,
        )
        return 1
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    try:
        return handler(args)
    except _CLI_ERRORS as exc:
        return _print_error(exc)
