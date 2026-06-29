from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROTOCOL_RELATIVE_PATH = Path("references") / "agent-communication-protocol.md"


class SkillProtocolValidationError(ValueError):
    pass


def validate_skill_protocols(root: Path | str = ".") -> list[Path]:
    repo_root = Path(root)
    protocol_paths = sorted((repo_root / "skills").glob(f"*/{PROTOCOL_RELATIVE_PATH}"))

    if len(protocol_paths) < 2:
        paths = ", ".join(str(path) for path in protocol_paths) or "none found"
        raise SkillProtocolValidationError(
            "expected at least two skill protocol references; found " + paths
        )

    expected_bytes = protocol_paths[0].read_bytes()
    differing_paths = [
        path for path in protocol_paths[1:] if path.read_bytes() != expected_bytes
    ]
    if differing_paths:
        all_paths = "\n".join(str(path) for path in protocol_paths)
        different = "\n".join(str(path) for path in differing_paths)
        raise SkillProtocolValidationError(
            "skill protocol references differ.\n"
            f"All protocol paths:\n{all_paths}\n"
            f"Differing paths:\n{different}"
        )

    return protocol_paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate duplicated agent-comm skill protocol references."
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        type=Path,
        help="Repository root to validate.",
    )
    args = parser.parse_args(argv)

    try:
        paths = validate_skill_protocols(args.root)
    except SkillProtocolValidationError as exc:
        print(f"ERR_SKILL_PROTOCOLS: {exc}", file=sys.stderr)
        return 1

    print(f"Validated {len(paths)} skill protocol references.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
