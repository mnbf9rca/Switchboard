from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

from agent_comm import repository
from agent_comm.repository import Repository


def test_register_upserts_agent_and_last_seen(bus):
    repo = Repository(bus)

    first = repo.register_agent(
        "implementer:codex:abc", role="implementer", harness="codex"
    )
    second = repo.register_agent(
        "implementer:codex:abc", role="implementer", harness="codex"
    )
    agent = repo.get_agent("implementer:codex:abc")

    assert agent.id == "implementer:codex:abc"
    assert agent.role == "implementer"
    assert agent.harness == "codex"
    assert agent.created_at == first.created_at
    assert second.last_seen_at is not None
    assert agent.last_seen_at is not None


def test_start_thread_creates_thread(bus):
    repo = Repository(bus)

    thread = repo.start_thread(title="Issue #304 adaptive limiter", project_id="demo")

    assert thread.title == "Issue #304 adaptive limiter"
    assert thread.project_id == "demo"
    assert thread.created_at is not None
    assert thread.updated_at == thread.created_at


def test_post_assigns_per_thread_sequence_and_stores_body_as_is(bus):
    repo = Repository(bus)
    thread = repo.start_thread("Title", "demo")

    msg1 = repo.post_message(
        thread.id,
        "planner",
        "implementer",
        "Handoff",
        "Requested action: read this.\n\nBody",
    )
    msg2 = repo.post_message(
        thread.id,
        "implementer",
        "planner",
        "Question",
        "No structured headers here.",
    )

    assert msg1.seq == 1
    assert msg2.seq == 2
    assert repo.get_message(msg2.id).body_md == "No structured headers here."


def test_reply_targets_must_be_in_same_thread(bus):
    repo = Repository(bus)
    one = repo.start_thread("One", "demo")
    two = repo.start_thread("Two", "demo")
    original = repo.post_message(one.id, "planner", "implementer", "A", "body")

    with pytest.raises(ValueError, match="same thread"):
        repo.post_message(
            two.id,
            "implementer",
            "planner",
            "B",
            "body",
            reply_to=[original.id],
        )


def test_duplicate_reply_targets_are_deduped(bus):
    repo = Repository(bus)
    thread = repo.start_thread("Title", "demo")
    original = repo.post_message(thread.id, "planner", "implementer", "A", "body")

    reply = repo.post_message(
        thread.id,
        "implementer",
        "planner",
        "B",
        "body",
        reply_to=[original.id, original.id],
    )

    with sqlite3.connect(bus) as db:
        rows = db.execute(
            """
            select reply_to_message_id
            from message_replies
            where message_id = ?
            """,
            (reply.id,),
        ).fetchall()
    assert rows == [(original.id,)]


def test_ack_only_recipient_can_ack(bus):
    repo = Repository(bus)
    thread = repo.start_thread("Title", "demo")
    msg = repo.post_message(thread.id, "planner", "implementer", "Handoff", "body")

    with pytest.raises(PermissionError):
        repo.ack_message(msg.id, "planner")

    repo.ack_message(msg.id, "implementer")

    assert repo.get_message(msg.id).acked_at is not None
    assert repo.inbox("implementer") == []


def test_inbox_orders_messages_deterministically_by_thread_sequence(bus):
    repo = Repository(bus)
    one = repo.start_thread("One", "demo")
    two = repo.start_thread("Two", "demo")
    msg1 = repo.post_message(one.id, "planner", "implementer", "One 1", "body")
    msg2 = repo.post_message(one.id, "planner", "implementer", "One 2", "body")
    msg3 = repo.post_message(two.id, "planner", "implementer", "Two 1", "body")

    inbox = repo.inbox("implementer")

    assert [message.id for message in inbox] == [msg1.id, msg2.id, msg3.id]
    assert [(message.thread_id, message.seq) for message in inbox][:2] == [
        (one.id, 1),
        (one.id, 2),
    ]


def test_artifact_links_thread_and_optional_message(bus):
    repo = Repository(bus)
    thread = repo.start_thread("Title", "demo")
    msg = repo.post_message(thread.id, "planner", "implementer", "Handoff", "body")

    artifact = repo.add_artifact(
        thread.id,
        msg.id,
        "docs/handoff.md",
        None,
        "Approved handoff",
    )

    assert artifact.thread_id == thread.id
    assert artifact.message_id == msg.id
    assert artifact.path == "docs/handoff.md"
    assert artifact.git_ref is None
    assert artifact.description == "Approved handoff"


def test_artifact_updates_thread_updated_at(bus):
    repo = Repository(bus)
    thread = repo.start_thread("Title", "demo")
    before = repo.get_thread(thread.id).updated_at

    artifact = repo.add_artifact(
        thread.id,
        None,
        "docs/handoff.md",
        "HEAD",
        "Approved handoff",
    )

    after = repo.get_thread(thread.id).updated_at
    assert after == artifact.created_at
    assert after >= before


def test_concurrent_posts_get_unique_thread_sequences(bus):
    repo = Repository(bus)
    thread = repo.start_thread("Title", "demo")

    def post(index: int):
        return Repository(bus).post_message(
            thread.id,
            "planner",
            "implementer",
            f"Subject {index}",
            f"Body {index}",
        )

    count = 40
    with ThreadPoolExecutor(max_workers=8) as pool:
        messages = list(pool.map(post, range(count)))

    assert sorted(message.seq for message in messages) == list(range(1, count + 1))
    assert repo.get_thread(thread.id).updated_at >= max(
        message.created_at for message in messages
    )


def test_repository_connection_context_closes(monkeypatch, temp_bus):
    closed = []

    class FakeCursor:
        def fetchone(self):
            return [repository.SCHEMA_VERSION]

    class FakeConnection:
        row_factory = None

        def execute(self, query, params=()):
            return FakeCursor()

        def close(self):
            closed.append(True)

    monkeypatch.setattr(repository, "open_bus", lambda path: FakeConnection())

    repo = Repository(temp_bus)

    with repo._connection() as db:
        assert isinstance(db, FakeConnection)

    assert closed == [True]
