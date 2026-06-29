from __future__ import annotations

import argparse
from collections.abc import Sequence
import sys

from . import __version__
from .db import BusError, UnsupportedSchemaVersion, check_bus, initialize_bus
from .paths import BusResolutionError, resolve_bus_path

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


def _handle_migrate(_args: argparse.Namespace) -> int:
    message = "ERR_NOT_IMPLEMENTED: migrate is not implemented yet"
    print(message)
    print(message, file=sys.stderr)
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args)
