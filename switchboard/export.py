from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import tempfile

from .repository import Artifact, Message, ReplyLink, Repository, Thread


@dataclass(frozen=True)
class ThreadRecords:
    thread: Thread
    messages: list[Message]
    unread_messages: list[Message]
    reply_links: list[ReplyLink]
    artifacts: list[Artifact]


def load_thread_records(repo: Repository, thread_id: str) -> ThreadRecords:
    return ThreadRecords(
        thread=repo.get_thread(thread_id),
        messages=repo.messages_for_thread(thread_id),
        unread_messages=repo.unread_messages_for_thread(thread_id),
        reply_links=repo.reply_links_for_thread(thread_id),
        artifacts=repo.artifacts_for_thread(thread_id),
    )


def render_thread_markdown(records: ThreadRecords, *, include_bodies: bool) -> str:
    thread = records.thread
    lines = [
        f"# {thread.title} ({thread.id})",
        "",
        "## Thread Metadata",
        f"- thread: {thread.id}",
        f"- project: {thread.project_id}",
        f"- title: {thread.title}",
        f"- created_at: {thread.created_at}",
        f"- updated_at: {thread.updated_at}",
        "",
        "## Unread Messages",
    ]
    if records.unread_messages:
        for message in records.unread_messages:
            lines.extend(_message_summary_markdown(message))
    else:
        lines.append("No unread messages.")
    lines.extend(
        [
            "",
            "## Recent Messages",
        ]
    )
    if records.messages:
        for message in records.messages:
            lines.extend(_message_summary_markdown(message))
    else:
        lines.append("No recent messages.")
    lines.extend(
        [
            "",
            "## Messages",
        ]
    )
    if not records.messages:
        lines.append("No messages.")
    for message in records.messages:
        lines.extend(_message_markdown(message, include_body=include_bodies))
    lines.extend(["", "## Reply References"])
    if records.reply_links:
        for link in records.reply_links:
            lines.append(f"- message: {link.message_id}")
            lines.append(f"  replies_to: {link.reply_to_message_id}")
    else:
        lines.append("No reply references.")
    lines.extend(["", "## Artifacts"])
    if records.artifacts:
        for artifact in records.artifacts:
            lines.extend(_artifact_markdown(artifact))
    else:
        lines.append("No artifacts.")
    lines.append("")
    return "\n".join(lines)


def write_thread_export(
    bus_path: Path,
    records: ThreadRecords,
    *,
    include_bodies: bool,
) -> Path:
    export_dir = bus_path.parent / "exports"
    export_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    output_path = export_dir / f"{records.thread.id}.md"
    content = render_thread_markdown(records, include_bodies=include_bodies)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.tmp.",
        dir=export_dir,
        text=True,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(tmp_path, output_path)
    except Exception:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        raise
    return output_path


def _message_markdown(message: Message, *, include_body: bool) -> list[str]:
    lines = [
        "",
        f"### Message {message.seq}",
        f"- message: {message.id}",
        f"- seq: {message.seq}",
        f"- from: {message.from_agent}",
        f"- to: {message.to_agent}",
        f"- subject: {message.subject}",
        f"- created_at: {message.created_at}",
        f"- acked_at: {message.acked_at or ''}",
    ]
    if include_body:
        fence = _markdown_fence(message.body_md)
        lines.extend(["", f"{fence}markdown", message.body_md.rstrip("\n"), fence])
    else:
        lines.append("- body: omitted")
    return lines


def _message_summary_markdown(message: Message) -> list[str]:
    return [
        f"- message: {message.id}",
        f"  seq: {message.seq}",
        f"  from: {message.from_agent}",
        f"  to: {message.to_agent}",
        f"  subject: {message.subject}",
        f"  created_at: {message.created_at}",
        f"  acked_at: {message.acked_at or ''}",
    ]


def _markdown_fence(body: str) -> str:
    longest = 2
    current = 0
    for char in body:
        if char == "`":
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return "`" * (longest + 1)


def _artifact_markdown(artifact: Artifact) -> list[str]:
    return [
        f"- artifact: {artifact.id}",
        f"  message: {artifact.message_id or ''}",
        f"  path: {artifact.path or ''}",
        f"  git_ref: {artifact.git_ref or ''}",
        f"  description: {artifact.description or ''}",
        f"  created_at: {artifact.created_at}",
    ]
