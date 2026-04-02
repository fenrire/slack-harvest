"""NexusEvent JSONL 변환 — work-nexus 연동."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from ..db.repository import Repository

# 감지 패턴
JIRA_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
CONFLUENCE_PATTERN = re.compile(r"https?://\w+\.atlassian\.net/wiki/\S+")
MENTION_PATTERN = re.compile(r"<@(\w+)>")


class NexusExporter:
    SCHEMA_VERSION = "1.0.0"

    def __init__(self, repo: Repository, workspace: str):
        self.repo = repo
        self.workspace = workspace

    def export_to_jsonl(
        self,
        outbox_dir: Path,
        channel_ids: list[str] | None = None,
    ) -> int:
        """NexusEvent JSONL 파일 생성."""
        outbox_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = outbox_dir / f"slack_{self.workspace}_{ts}.jsonl"

        channels = self.repo.list_channels()
        if channel_ids:
            channels = [c for c in channels if c["id"] in channel_ids]

        count = 0
        with open(str(path), "w", encoding="utf-8") as f:
            for ch in channels:
                msgs = self.repo.get_messages_by_channel(ch["id"])
                for msg in msgs:
                    event = self._to_event(msg, ch)
                    f.write(json.dumps(event, ensure_ascii=False) + "\n")
                    count += 1
        return count

    def _to_event(self, msg: dict, ch: dict) -> dict:
        ts_float = float(msg["ts"])
        dt = datetime.fromtimestamp(ts_float, tz=timezone.utc)

        # type
        if msg.get("thread_ts") and msg["thread_ts"] != msg["ts"]:
            event_type = "thread_reply"
        else:
            event_type = "message"

        return {
            "id": f"slack:{ch['id']}-{msg['ts']}",
            "source": "slack",
            "type": event_type,
            "timestamp": dt.isoformat(),
            "author": {
                "source_id": msg.get("user_id", ""),
                "display_name": msg.get("display_name", ""),
                "email": msg.get("email", ""),
            },
            "channel": {
                "source_id": ch["id"],
                "name": ch["name"],
                "type": "private_channel" if ch.get("is_private") else "channel",
            },
            "content": {
                "text": msg.get("text", ""),
                "format": "plain",
            },
            "metadata": {
                "thread_ts": msg.get("thread_ts"),
                "reactions": json.loads(msg.get("reactions", "[]")),
                "reply_count": msg.get("reply_count", 0),
                "workspace": self.workspace,
            },
            "references": self._extract_refs(msg),
            "collected_at": datetime.now(tz=timezone.utc).isoformat(),
            "schema_version": self.SCHEMA_VERSION,
        }

    def _extract_refs(self, msg: dict) -> list[dict]:
        refs: list[dict] = []
        text = msg.get("text", "")

        for m in JIRA_PATTERN.finditer(text):
            refs.append({
                "type": "links_to",
                "target_id": f"jira:{m.group(1)}",
                "target_source": "jira",
            })

        for m in CONFLUENCE_PATTERN.finditer(text):
            refs.append({
                "type": "links_to",
                "target_id": f"confluence:{m.group(0)}",
                "target_source": "confluence",
            })

        for m in MENTION_PATTERN.finditer(text):
            refs.append({
                "type": "mentions",
                "target_id": f"slack:{m.group(1)}",
                "target_source": "slack",
            })

        # 스레드 답글
        if msg.get("thread_ts") and msg.get("thread_ts") != msg.get("ts"):
            ch_id = msg.get("channel_id", "")
            refs.append({
                "type": "reply_to",
                "target_id": f"slack:{ch_id}-{msg['thread_ts']}",
                "target_source": "slack",
            })

        return refs
