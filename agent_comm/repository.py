from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Iterator, Iterable
from uuid import uuid4
from datetime import UTC, datetime

from .db import SCHEMA_VERSION, UnsupportedSchemaVersion, open_bus


@dataclass(frozen=True)
class Agent:
    id: str
    display_name: str | None
    harness: str | None
    role: str | None
    created_at: str
    last_seen_at: str | None


@dataclass(frozen=True)
class Thread:
    id: str
    project_id: str
    title: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Message:
    id: str
    thread_id: str
    seq: int
    from_agent: str
    to_agent: str
    subject: str
    body_md: str
    created_at: str
    acked_at: str | None


@dataclass(frozen=True)
class Artifact:
    id: str
    thread_id: str
    message_id: str | None
    path: str | None
    git_ref: str | None
    description: str | None
    created_at: str


@dataclass(frozen=True)
class ReplyLink:
    message_id: str
    reply_to_message_id: str


class Repository:
    def __init__(self, bus_path: str | Path, *, readonly: bool = False):
        self.bus_path = Path(bus_path)
        self.readonly = readonly

    def register_agent(
        self,
        agent_id: str,
        *,
        display_name: str | None = None,
        harness: str | None = None,
        role: str | None = None,
    ) -> Agent:
        now = _utc_now()
        with self._connection() as db:
            db.execute(
                """
                insert into agents(id, display_name, harness, role, created_at, last_seen_at)
                values(?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                  display_name = excluded.display_name,
                  harness = excluded.harness,
                  role = excluded.role,
                  last_seen_at = excluded.last_seen_at
                """,
                (agent_id, display_name, harness, role, now, now),
            )
            row = _one(
                db,
                """
                select id, display_name, harness, role, created_at, last_seen_at
                from agents
                where id = ?
                """,
                (agent_id,),
            )
            _commit_and_checkpoint(db)
        return _agent(row)

    def get_agent(self, agent_id: str) -> Agent:
        with self._connection() as db:
            row = _one(
                db,
                """
                select id, display_name, harness, role, created_at, last_seen_at
                from agents
                where id = ?
                """,
                (agent_id,),
            )
        return _agent(row)

    def start_thread(self, title: str, project_id: str) -> Thread:
        now = _utc_now()
        thread_id = _new_id("thread")
        with self._connection() as db:
            db.execute(
                """
                insert into threads(id, project_id, title, created_at, updated_at)
                values(?, ?, ?, ?, ?)
                """,
                (thread_id, project_id, title, now, now),
            )
            _commit_and_checkpoint(db)
        return Thread(thread_id, project_id, title, now, now)

    def get_thread(self, thread_id: str) -> Thread:
        with self._connection() as db:
            row = _one(
                db,
                """
                select id, project_id, title, created_at, updated_at
                from threads
                where id = ?
                """,
                (thread_id,),
            )
        return _thread(row)

    def messages_for_thread(self, thread_id: str) -> list[Message]:
        with self._connection() as db:
            self._require_thread(db, thread_id)
            rows = db.execute(
                """
                select id, thread_id, seq, from_agent, to_agent, subject,
                       body_md, created_at, acked_at
                from messages
                where thread_id = ?
                order by seq, id
                """,
                (thread_id,),
            ).fetchall()
        return [_message(row) for row in rows]

    def unread_messages_for_thread(self, thread_id: str) -> list[Message]:
        with self._connection() as db:
            self._require_thread(db, thread_id)
            rows = db.execute(
                """
                select id, thread_id, seq, from_agent, to_agent, subject,
                       body_md, created_at, acked_at
                from messages
                where thread_id = ? and acked_at is null
                order by seq, id
                """,
                (thread_id,),
            ).fetchall()
        return [_message(row) for row in rows]

    def reply_links_for_thread(self, thread_id: str) -> list[ReplyLink]:
        with self._connection() as db:
            self._require_thread(db, thread_id)
            rows = db.execute(
                """
                select r.message_id, r.reply_to_message_id
                from message_replies r
                join messages m on m.id = r.message_id
                where m.thread_id = ?
                order by m.seq, r.reply_to_message_id
                """,
                (thread_id,),
            ).fetchall()
        return [
            ReplyLink(row["message_id"], row["reply_to_message_id"])
            for row in rows
        ]

    def post_message(
        self,
        thread_id: str,
        from_agent: str,
        to_agent: str,
        subject: str,
        body_md: str,
        *,
        reply_to: Iterable[str] | None = None,
    ) -> Message:
        reply_ids = _dedupe(reply_to or [])
        message_id = _new_id("msg")
        with self._connection() as db:
            try:
                db.execute("begin immediate")
                now = _utc_now()
                self._require_thread(db, thread_id)
                self._require_reply_targets_in_thread(db, thread_id, reply_ids)
                seq = (
                    db.execute(
                        "select coalesce(max(seq), 0) + 1 from messages where thread_id = ?",
                        (thread_id,),
                    ).fetchone()[0]
                )
                db.execute(
                    """
                    insert into messages(
                      id, thread_id, seq, from_agent, to_agent, subject,
                      body_md, created_at, acked_at
                    )
                    values(?, ?, ?, ?, ?, ?, ?, ?, null)
                    """,
                    (
                        message_id,
                        thread_id,
                        seq,
                        from_agent,
                        to_agent,
                        subject,
                        body_md,
                        now,
                    ),
                )
                db.executemany(
                    """
                    insert into message_replies(message_id, reply_to_message_id)
                    values(?, ?)
                    """,
                    [(message_id, reply_id) for reply_id in reply_ids],
                )
                db.execute(
                    "update threads set updated_at = ? where id = ?",
                    (now, thread_id),
                )
                _commit_and_checkpoint(db)
            except Exception:
                db.rollback()
                raise
        return Message(
            message_id,
            thread_id,
            seq,
            from_agent,
            to_agent,
            subject,
            body_md,
            now,
            None,
        )

    def get_message(self, message_id: str) -> Message:
        with self._connection() as db:
            row = _one(
                db,
                """
                select id, thread_id, seq, from_agent, to_agent, subject,
                       body_md, created_at, acked_at
                from messages
                where id = ?
                """,
                (message_id,),
            )
        return _message(row)

    def ack_message(self, message_id: str, agent_id: str) -> Message:
        now = _utc_now()
        with self._connection() as db:
            try:
                db.execute("begin immediate")
                row = _one(
                    db,
                    """
                    select id, thread_id, seq, from_agent, to_agent, subject,
                           body_md, created_at, acked_at
                    from messages
                    where id = ?
                    """,
                    (message_id,),
                )
                if row["to_agent"] != agent_id:
                    raise PermissionError("only the message recipient can acknowledge it")
                acked_at = row["acked_at"] or now
                db.execute(
                    "update messages set acked_at = ? where id = ?",
                    (acked_at, message_id),
                )
                _commit_and_checkpoint(db)
            except Exception:
                db.rollback()
                raise
        return Message(
            row["id"],
            row["thread_id"],
            row["seq"],
            row["from_agent"],
            row["to_agent"],
            row["subject"],
            row["body_md"],
            row["created_at"],
            acked_at,
        )

    def inbox(self, agent_id: str) -> list[Message]:
        with self._connection() as db:
            rows = db.execute(
                """
                select id, thread_id, seq, from_agent, to_agent, subject,
                       body_md, created_at, acked_at
                from messages
                where to_agent = ? and acked_at is null
                order by created_at, thread_id, seq, id
                """,
                (agent_id,),
            ).fetchall()
        return [_message(row) for row in rows]

    def add_artifact(
        self,
        thread_id: str,
        message_id: str | None,
        path: str | None,
        git_ref: str | None,
        description: str | None,
    ) -> Artifact:
        artifact_id = _new_id("artifact")
        with self._connection() as db:
            try:
                db.execute("begin immediate")
                now = _utc_now()
                self._require_thread(db, thread_id)
                if message_id is not None:
                    message = _one(
                        db,
                        "select thread_id from messages where id = ?",
                        (message_id,),
                    )
                    if message["thread_id"] != thread_id:
                        raise ValueError("artifact message must belong to the same thread")
                db.execute(
                    """
                    insert into artifacts(id, thread_id, message_id, path, git_ref, description, created_at)
                    values(?, ?, ?, ?, ?, ?, ?)
                    """,
                    (artifact_id, thread_id, message_id, path, git_ref, description, now),
                )
                db.execute(
                    "update threads set updated_at = ? where id = ?",
                    (now, thread_id),
                )
                _commit_and_checkpoint(db)
            except Exception:
                db.rollback()
                raise
        return Artifact(artifact_id, thread_id, message_id, path, git_ref, description, now)

    def artifacts_for_message(self, message_id: str) -> list[Artifact]:
        with self._connection() as db:
            rows = db.execute(
                """
                select id, thread_id, message_id, path, git_ref, description, created_at
                from artifacts
                where message_id = ?
                order by created_at, id
                """,
                (message_id,),
            ).fetchall()
        return [_artifact(row) for row in rows]

    def artifacts_for_thread(self, thread_id: str) -> list[Artifact]:
        with self._connection() as db:
            self._require_thread(db, thread_id)
            rows = db.execute(
                """
                select id, thread_id, message_id, path, git_ref, description, created_at
                from artifacts
                where thread_id = ?
                order by created_at, id
                """,
                (thread_id,),
            ).fetchall()
        return [_artifact(row) for row in rows]

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        db = self._connect()
        try:
            yield db
        finally:
            db.close()

    def _connect(self) -> sqlite3.Connection:
        db = open_bus(self.bus_path, readonly=self.readonly)
        db.row_factory = sqlite3.Row
        version = int(db.execute("pragma user_version").fetchone()[0])
        if version != SCHEMA_VERSION:
            db.close()
            raise UnsupportedSchemaVersion(
                f"unsupported schema version {version}; this CLI requires {SCHEMA_VERSION}"
            )
        return db

    def _require_thread(self, db: sqlite3.Connection, thread_id: str) -> None:
        _one(db, "select id from threads where id = ?", (thread_id,))

    def _require_reply_targets_in_thread(
        self, db: sqlite3.Connection, thread_id: str, reply_ids: list[str]
    ) -> None:
        for reply_id in reply_ids:
            row = _one(
                db,
                "select thread_id from messages where id = ?",
                (reply_id,),
            )
            if row["thread_id"] != thread_id:
                raise ValueError("reply targets must belong to the same thread")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _dedupe(values: Iterable[str]) -> list[str]:
    seen = set()
    deduped = []
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def _commit_and_checkpoint(db: sqlite3.Connection) -> None:
    db.commit()
    db.execute("pragma wal_checkpoint(TRUNCATE)")


def _one(
    db: sqlite3.Connection, query: str, params: tuple[object, ...]
) -> sqlite3.Row:
    row = db.execute(query, params).fetchone()
    if row is None:
        raise ValueError("record not found")
    return row


def _agent(row: sqlite3.Row) -> Agent:
    return Agent(
        row["id"],
        row["display_name"],
        row["harness"],
        row["role"],
        row["created_at"],
        row["last_seen_at"],
    )


def _thread(row: sqlite3.Row) -> Thread:
    return Thread(
        row["id"],
        row["project_id"],
        row["title"],
        row["created_at"],
        row["updated_at"],
    )


def _message(row: sqlite3.Row) -> Message:
    return Message(
        row["id"],
        row["thread_id"],
        row["seq"],
        row["from_agent"],
        row["to_agent"],
        row["subject"],
        row["body_md"],
        row["created_at"],
        row["acked_at"],
    )


def _artifact(row: sqlite3.Row) -> Artifact:
    return Artifact(
        row["id"],
        row["thread_id"],
        row["message_id"],
        row["path"],
        row["git_ref"],
        row["description"],
        row["created_at"],
    )
