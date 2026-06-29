from __future__ import annotations

import argparse
from collections.abc import Sequence

from . import __version__

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
        subparser.set_defaults(handler=_handle_migrate if command == "migrate" else _handle_placeholder)

    return parser


def _handle_placeholder(args: argparse.Namespace) -> int:
    print(f"ERR_NOT_IMPLEMENTED: {args.command} is not implemented yet")
    return 1


def _handle_migrate(_args: argparse.Namespace) -> int:
    print("ERR_NOT_IMPLEMENTED: migrate is not implemented yet")
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args)
