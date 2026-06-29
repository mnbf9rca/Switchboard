from __future__ import annotations

from contextlib import closing
import os
import sqlite3
from pathlib import Path
from uuid import uuid4

from .db import BUSY_TIMEOUT_MS, SCHEMA_VERSION, BusError, check_bus

EXPECTED_SCHEMA: dict[str, tuple[tuple[str, str, int, object, int], ...]] = {
    "agents": (
        ("id", "TEXT", 0, None, 1),
        ("display_name", "TEXT", 0, None, 0),
        ("harness", "TEXT", 0, None, 0),
        ("role", "TEXT", 0, None, 0),
        ("created_at", "TEXT", 1, None, 0),
        ("last_seen_at", "TEXT", 0, None, 0),
    ),
    "threads": (
        ("id", "TEXT", 0, None, 1),
        ("project_id", "TEXT", 1, None, 0),
        ("title", "TEXT", 1, None, 0),
        ("created_at", "TEXT", 1, None, 0),
        ("updated_at", "TEXT", 1, None, 0),
    ),
    "messages": (
        ("id", "TEXT", 0, None, 1),
        ("thread_id", "TEXT", 1, None, 0),
        ("seq", "INTEGER", 1, None, 0),
        ("from_agent", "TEXT", 1, None, 0),
        ("to_agent", "TEXT", 1, None, 0),
        ("subject", "TEXT", 1, None, 0),
        ("body_md", "TEXT", 1, None, 0),
        ("created_at", "TEXT", 1, None, 0),
        ("acked_at", "TEXT", 0, None, 0),
    ),
    "message_replies": (
        ("message_id", "TEXT", 1, None, 1),
        ("reply_to_message_id", "TEXT", 1, None, 2),
    ),
    "artifacts": (
        ("id", "TEXT", 0, None, 1),
        ("thread_id", "TEXT", 1, None, 0),
        ("message_id", "TEXT", 0, None, 0),
        ("path", "TEXT", 0, None, 0),
        ("git_ref", "TEXT", 0, None, 0),
        ("description", "TEXT", 0, None, 0),
        ("created_at", "TEXT", 1, None, 0),
    ),
}
EXPECTED_UNIQUE_INDEXES = {
    "messages": {("thread_id", "seq")},
}


def backup_bus(
    source_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
) -> Path:
    source = Path(source_path).expanduser()
    output = Path(output_path).expanduser()
    check_bus(source)
    _ensure_private_parent(output.parent)
    temp = _private_temp_path(output)
    try:
        _create_private_file(temp)
        with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as source_db:
            with sqlite3.connect(temp) as target_db:
                source_db.backup(target_db)
        _make_standalone(temp)
        _validate_database(temp)
        _make_private(temp)
        os.replace(temp, output)
        _make_private(output)
    except Exception:
        _unlink_database_files(temp)
        raise
    return output


def restore_bus(
    target_path: str | os.PathLike[str],
    input_path: str | os.PathLike[str],
) -> Path:
    target = Path(target_path).expanduser()
    backup = Path(input_path).expanduser()
    _validate_database(backup, read_only=True)
    if not target.exists():
        raise BusError(f"bus database does not exist: {target}")
    temp = _private_temp_path(target)
    lock = _acquire_target_lock(target)
    try:
        _create_private_file(temp)
        with sqlite3.connect(f"file:{backup}?mode=ro", uri=True) as source_db:
            with sqlite3.connect(temp) as target_db:
                source_db.backup(target_db)
        _make_standalone(temp)
        _validate_database(temp)
        _unlink_database_side_files(temp)
        _make_private(temp)
        _unlink_database_side_files(target)
        os.replace(temp, target)
        _make_private(target)
        with sqlite3.connect(target) as restored:
            restored.execute("pragma journal_mode = WAL")
    except Exception:
        _unlink_database_files(temp)
        raise
    finally:
        if lock is not None:
            lock.rollback()
            lock.close()
    return target


def _validate_database(path: Path, *, read_only: bool = False) -> None:
    if not path.exists():
        raise BusError(f"backup database does not exist: {path}")
    try:
        db = (
            sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            if read_only
            else sqlite3.connect(path)
        )
        with closing(db):
            db.execute(f"pragma busy_timeout = {BUSY_TIMEOUT_MS}")
            version = int(db.execute("pragma user_version").fetchone()[0])
            if version != SCHEMA_VERSION:
                raise BusError(
                    f"backup has unsupported schema version {version}; "
                    f"this CLI requires {SCHEMA_VERSION}"
                )
            _check_expected_schema(db, path)
            integrity = db.execute("pragma integrity_check").fetchone()[0]
            if integrity != "ok":
                raise BusError(f"backup integrity check failed: {integrity}")
    except sqlite3.DatabaseError as exc:
        raise BusError(f"backup is not a valid SQLite database: {path}") from exc


def _acquire_target_lock(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path, timeout=0)
    try:
        db.execute("pragma busy_timeout = 0")
        db.execute("begin exclusive")
    except sqlite3.OperationalError as exc:
        db.close()
        raise BusError(f"cannot acquire exclusive access to target bus: {path}") from exc
    return db


def _ensure_private_parent(path: Path) -> None:
    if path.exists():
        return
    missing = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
        if os.name == "posix":
            directory.chmod(0o700)


def _private_temp_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.tmp.{os.getpid()}.{uuid4().hex}")


def _create_private_file(path: Path) -> None:
    if os.name == "posix":
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
    else:
        path.touch(exist_ok=False)


def _make_private(path: Path) -> None:
    if os.name == "posix":
        path.chmod(0o600)


def _check_expected_schema(db: sqlite3.Connection, path: Path) -> None:
    tables = {
        row[0]
        for row in db.execute(
            "select name from sqlite_master where type = 'table'"
        )
    }
    expected_tables = set(EXPECTED_SCHEMA)
    if tables != expected_tables:
        raise BusError(
            f"backup schema tables do not match version {SCHEMA_VERSION}: {path}"
        )
    for table, expected_columns in EXPECTED_SCHEMA.items():
        columns = tuple(
            (row[1], row[2].upper(), row[3], row[4], row[5])
            for row in db.execute(f"pragma table_info({table})")
        )
        if columns != expected_columns:
            raise BusError(f"backup schema for table {table} is not supported: {path}")
        expected_unique_indexes = EXPECTED_UNIQUE_INDEXES.get(table, set())
        actual_unique_indexes = set()
        for index in db.execute(f"pragma index_list({table})"):
            if not index[2]:
                continue
            columns_in_index = tuple(
                row[2] for row in db.execute(f"pragma index_info({index[1]})")
            )
            actual_unique_indexes.add(columns_in_index)
        if not expected_unique_indexes <= actual_unique_indexes:
            raise BusError(f"backup schema for table {table} is not supported: {path}")


def _make_standalone(path: Path) -> None:
    with sqlite3.connect(path) as db:
        db.execute("pragma journal_mode = DELETE")
    _unlink_database_side_files(path)


def _unlink_database_files(path: Path) -> None:
    path.unlink(missing_ok=True)
    _unlink_database_side_files(path)


def _unlink_database_side_files(path: Path) -> None:
    path.with_name(f"{path.name}-wal").unlink(missing_ok=True)
    path.with_name(f"{path.name}-shm").unlink(missing_ok=True)
