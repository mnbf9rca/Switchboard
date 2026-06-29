from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from urllib.parse import quote

SCHEMA_VERSION = 1
BUSY_TIMEOUT_MS = 5000


class BusError(RuntimeError):
    """Raised when the SQLite bus cannot be opened safely."""


class UnsupportedSchemaVersion(BusError):
    """Raised when a bus was created by a newer CLI."""


def open_bus(
    path: str | os.PathLike[str],
    *,
    readonly: bool = False,
) -> sqlite3.Connection:
    bus_path = Path(path).expanduser()
    if readonly:
        _require_existing_database_path(bus_path)
        db = sqlite3.connect(_read_only_uri(bus_path), uri=True)
    else:
        _ensure_private_database_path(bus_path)
        db = sqlite3.connect(bus_path)
    try:
        if readonly:
            _configure_read_connection(db)
        else:
            _configure_connection(db)
        _check_supported_version(db)
    except Exception:
        db.close()
        raise
    return db


def initialize_bus(path: str | os.PathLike[str], project_id: str) -> sqlite3.Connection:
    db = open_bus(path)
    try:
        version = _schema_version(db)
        if version == 0:
            _create_schema(db)
            db.execute(f"pragma user_version = {SCHEMA_VERSION}")
            _commit_and_checkpoint(db)
        elif version < SCHEMA_VERSION:
            raise BusError(
                f"schema version {version} requires migration; run switchboard migrate"
            )
        _check_supported_version(db)
    except Exception:
        db.close()
        raise
    return db


def check_bus(path: str | os.PathLike[str]) -> None:
    bus_path = Path(path).expanduser()
    if not bus_path.exists():
        raise BusError(f"bus database does not exist: {bus_path}")
    _require_private_permissions(bus_path.parent, 0o700, "bus directory")
    _require_private_permissions(bus_path, 0o600, "bus database")

    with sqlite3.connect(bus_path) as db:
        db.execute(f"pragma busy_timeout = {BUSY_TIMEOUT_MS}")
        _check_exact_schema_version(db)
        journal_mode = db.execute("pragma journal_mode").fetchone()[0]
        if str(journal_mode).lower() != "wal":
            raise BusError("WAL journal mode is not active")
        integrity = db.execute("pragma integrity_check").fetchone()[0]
        if integrity != "ok":
            raise BusError(f"integrity check failed: {integrity}")


def _ensure_private_database_path(path: Path) -> None:
    parent_existed = path.parent.exists()
    if parent_existed:
        _require_private_permissions(path.parent, 0o700, "bus directory")
    else:
        _make_private_dirs(path.parent)

    if not path.exists():
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
    else:
        _require_private_permissions(path, 0o600, "bus database")


def _require_existing_database_path(path: Path) -> None:
    if not path.exists():
        raise BusError(f"mailbox does not exist; send a message first: {path}")
    _require_private_permissions(path.parent, 0o700, "bus directory")
    _require_private_permissions(path, 0o600, "bus database")


def _make_private_dirs(path: Path) -> None:
    missing = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent

    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
        if os.name == "posix":
            directory.chmod(0o700)


def _require_private_permissions(path: Path, expected_mode: int, label: str) -> None:
    if os.name != "posix":
        return
    actual_mode = stat_mode(path)
    if actual_mode != expected_mode:
        raise BusError(
            f"{label} must have private permissions "
            f"{expected_mode:o}; found {actual_mode:o}: {path}"
        )


def stat_mode(path: Path) -> int:
    return path.stat().st_mode & 0o777


def _configure_connection(db: sqlite3.Connection) -> None:
    db.execute(f"pragma busy_timeout = {BUSY_TIMEOUT_MS}")
    journal_mode = db.execute("pragma journal_mode = WAL").fetchone()[0]
    if str(journal_mode).lower() != "wal":
        raise BusError("failed to enable WAL journal mode")


def _configure_read_connection(db: sqlite3.Connection) -> None:
    db.execute(f"pragma busy_timeout = {BUSY_TIMEOUT_MS}")
    db.execute("pragma query_only = ON")


def _read_only_uri(path: Path) -> str:
    return f"file:{quote(path.resolve().as_posix())}?mode=ro&immutable=1"


def _commit_and_checkpoint(db: sqlite3.Connection) -> None:
    db.commit()
    db.execute("pragma wal_checkpoint(TRUNCATE)")


def _check_supported_version(db: sqlite3.Connection) -> None:
    version = _schema_version(db)
    if version > SCHEMA_VERSION:
        raise UnsupportedSchemaVersion(
            f"unsupported schema version {version}; this CLI supports {SCHEMA_VERSION}"
        )


def _check_exact_schema_version(db: sqlite3.Connection) -> None:
    version = _schema_version(db)
    if version != SCHEMA_VERSION:
        raise UnsupportedSchemaVersion(
            f"unsupported schema version {version}; this CLI requires {SCHEMA_VERSION}"
        )


def _schema_version(db: sqlite3.Connection) -> int:
    return int(db.execute("pragma user_version").fetchone()[0])


def _create_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        create table agents(
          id text primary key,
          display_name text,
          harness text,
          role text,
          created_at text not null,
          last_seen_at text
        );

        create table threads(
          id text primary key,
          project_id text not null,
          title text not null,
          created_at text not null,
          updated_at text not null
        );

        create table messages(
          id text primary key,
          thread_id text not null,
          seq integer not null,
          from_agent text not null,
          to_agent text not null,
          subject text not null,
          body_md text not null,
          created_at text not null,
          acked_at text,
          unique(thread_id, seq)
        );

        create table message_replies(
          message_id text not null,
          reply_to_message_id text not null,
          primary key(message_id, reply_to_message_id)
        );

        create table artifacts(
          id text primary key,
          thread_id text not null,
          message_id text,
          path text,
          git_ref text,
          description text,
          created_at text not null
        );
        """
    )
