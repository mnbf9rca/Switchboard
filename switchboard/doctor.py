from __future__ import annotations

import os
from pathlib import Path
import sqlite3

from .db import (
    BUSY_TIMEOUT_MS,
    SCHEMA_VERSION,
    BusError,
    UnsupportedSchemaVersion,
    stat_mode,
)


def core_health(path: str | os.PathLike[str]) -> list[str]:
    bus_path = Path(path).expanduser()
    if not bus_path.exists():
        raise BusError(f"bus database does not exist: {bus_path}")

    permission_status = _check_private_permissions(bus_path)
    try:
        with sqlite3.connect(bus_path) as db:
            db.execute(f"pragma busy_timeout = {BUSY_TIMEOUT_MS}")
            version = int(db.execute("pragma user_version").fetchone()[0])
            if version != SCHEMA_VERSION:
                raise UnsupportedSchemaVersion(
                    f"unsupported schema version {version}; "
                    f"this CLI requires {SCHEMA_VERSION}"
                )
            integrity = db.execute("pragma integrity_check").fetchone()[0]
            if integrity != "ok":
                raise BusError(f"integrity check failed: {integrity}")
            journal_mode = db.execute("pragma journal_mode").fetchone()[0]
            if str(journal_mode).lower() != "wal":
                raise BusError("WAL journal mode is not active")
    except UnsupportedSchemaVersion:
        raise
    except sqlite3.DatabaseError as exc:
        raise BusError(f"bus is not a valid SQLite database: {bus_path}") from exc

    return [
        "switchboard doctor: ok",
        "db opens: ok",
        f"schema version: {version}",
        "integrity: ok",
        "wal: active",
        f"permissions: {permission_status}",
    ]


def _check_private_permissions(path: Path) -> str:
    if os.name != "posix":
        return "not checked"
    parent_mode = stat_mode(path.parent)
    if parent_mode != 0o700:
        raise BusError(
            f"bus directory must have private permissions 700; "
            f"found {parent_mode:o}: {path.parent}"
        )
    db_mode = stat_mode(path)
    if db_mode != 0o600:
        raise BusError(
            f"bus database must have private permissions 600; found {db_mode:o}: {path}"
        )
    return "private"
