"""SQLite CRUD — 모든 쓰기는 INSERT OR REPLACE (멱등성 보장)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone


class Repository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ── channels ──────────────────────────────────────────────

    def upsert_channel(self, ch: dict) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO channels
               (id, name, topic, purpose, is_private, is_archived,
                member_count, raw_json, fetched_at, latest_ts)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                        COALESCE((SELECT latest_ts FROM channels WHERE id = ?), NULL))""",
            (
                ch["id"],
                ch.get("name", ""),
                (ch.get("topic") or {}).get("value", ""),
                (ch.get("purpose") or {}).get("value", ""),
                int(ch.get("is_private", False)),
                int(ch.get("is_archived", False)),
                ch.get("num_members", 0),
                json.dumps(ch, ensure_ascii=False),
                _now(),
                ch["id"],
            ),
        )

    def upsert_channels(self, channels: list[dict]) -> int:
        with self.conn:
            for ch in channels:
                self.upsert_channel(ch)
        return len(channels)

    # ── users ─────────────────────────────────────────────────

    def upsert_user(self, user: dict) -> None:
        profile = user.get("profile", {})
        self.conn.execute(
            """INSERT OR REPLACE INTO users
               (id, display_name, real_name, email, title,
                avatar_url, is_bot, raw_json, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user["id"],
                profile.get("display_name") or user.get("name", ""),
                profile.get("real_name", ""),
                profile.get("email", ""),
                profile.get("title", ""),
                profile.get("image_72", ""),
                int(user.get("is_bot", False)),
                json.dumps(user, ensure_ascii=False),
                _now(),
            ),
        )

    def upsert_users(self, users: list[dict]) -> int:
        with self.conn:
            for u in users:
                self.upsert_user(u)
        return len(users)

    # ── messages ──────────────────────────────────────────────

    def upsert_message(self, channel_id: str, msg: dict) -> None:
        edited = msg.get("edited")
        self.conn.execute(
            """INSERT OR REPLACE INTO messages
               (channel_id, ts, thread_ts, user_id, text, subtype,
                edited_ts, reply_count, reactions, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                channel_id,
                msg["ts"],
                msg.get("thread_ts"),
                msg.get("user"),
                msg.get("text", ""),
                msg.get("subtype", ""),
                edited.get("ts") if edited else None,
                msg.get("reply_count", 0),
                json.dumps(msg.get("reactions", []), ensure_ascii=False),
                json.dumps(msg, ensure_ascii=False),
            ),
        )

    def upsert_messages(self, channel_id: str, messages: list[dict]) -> int:
        with self.conn:
            for msg in messages:
                self.upsert_message(channel_id, msg)
        return len(messages)

    # ── files ─────────────────────────────────────────────────

    def upsert_file(self, f: dict, channel_id: str, message_ts: str) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO files
               (id, channel_id, message_ts, user_id, name, mimetype,
                url_private, size, downloaded, local_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                        COALESCE((SELECT downloaded FROM files WHERE id = ?), 0),
                        COALESCE((SELECT local_path FROM files WHERE id = ?), ''))""",
            (
                f["id"],
                channel_id,
                message_ts,
                f.get("user"),
                f.get("name", "unknown"),
                f.get("mimetype", ""),
                f.get("url_private", ""),
                f.get("size", 0),
                f["id"],
                f["id"],
            ),
        )

    # ── sync_state ────────────────────────────────────────────

    def get_latest_ts(self, channel_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT latest_ts FROM channels WHERE id = ?", (channel_id,)
        ).fetchone()
        return row["latest_ts"] if row else None

    def update_latest_ts(self, channel_id: str, ts: str) -> None:
        self.conn.execute(
            "UPDATE channels SET latest_ts = ? WHERE id = ?", (ts, channel_id)
        )
        self.conn.commit()

    def set_sync_status(self, channel_id: str, status: str) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO sync_state (channel_id, last_synced_ts, status)
               VALUES (?, ?, ?)""",
            (channel_id, _now(), status),
        )
        self.conn.commit()

    def get_missing_user_ids(self) -> list[str]:
        """messages에 등장하지만 users 테이블에 없는 user_id 목록."""
        rows = self.conn.execute(
            """SELECT DISTINCT m.user_id FROM messages m
               LEFT JOIN users u ON m.user_id = u.id
               WHERE m.user_id IS NOT NULL AND u.id IS NULL"""
        ).fetchall()
        return [r[0] for r in rows]

    # ── 조회 ──────────────────────────────────────────────────

    def list_channels(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM channels ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_channel_by_name(self, name: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM channels WHERE name = ?", (name,)
        ).fetchone()
        return dict(row) if row else None

    def get_channel_by_id(self, channel_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM channels WHERE id = ?", (channel_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_messages_by_channel(
        self, channel_id: str, date: str | None = None
    ) -> list[dict]:
        if date:
            rows = self.conn.execute(
                """SELECT m.*, u.display_name, u.real_name, u.email, u.title
                   FROM messages m LEFT JOIN users u ON m.user_id = u.id
                   WHERE m.channel_id = ?
                     AND date(CAST(m.ts AS REAL), 'unixepoch') = ?
                   ORDER BY m.ts""",
                (channel_id, date),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT m.*, u.display_name, u.real_name, u.email, u.title
                   FROM messages m LEFT JOIN users u ON m.user_id = u.id
                   WHERE m.channel_id = ?
                   ORDER BY m.ts""",
                (channel_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_thread_messages(
        self, channel_id: str, thread_ts: str
    ) -> list[dict]:
        rows = self.conn.execute(
            """SELECT m.*, u.display_name, u.real_name, u.email, u.title
               FROM messages m LEFT JOIN users u ON m.user_id = u.id
               WHERE m.channel_id = ? AND m.thread_ts = ?
               ORDER BY m.ts""",
            (channel_id, thread_ts),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_thread_parents(self, channel_id: str) -> list[dict]:
        rows = self.conn.execute(
            """SELECT m.*, u.display_name, u.real_name, u.email, u.title
               FROM messages m LEFT JOIN users u ON m.user_id = u.id
               WHERE m.channel_id = ? AND m.reply_count > 0
               ORDER BY m.ts""",
            (channel_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_users(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM users ORDER BY display_name"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_user(self, user_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_pending_files(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM files WHERE downloaded = 0"
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_file_downloaded(self, file_id: str, local_path: str) -> None:
        self.conn.execute(
            "UPDATE files SET downloaded = 1, local_path = ? WHERE id = ?",
            (local_path, file_id),
        )
        self.conn.commit()

    def count_edited_updates(
        self, channel_id: str, messages: list[dict]
    ) -> int:
        """upsert 전에 호출 — DB 대비 edited_ts가 변경된 메시지 수를 반환."""
        count = 0
        for msg in messages:
            edited = msg.get("edited")
            new_edited_ts = edited.get("ts") if edited else None
            row = self.conn.execute(
                "SELECT edited_ts FROM messages WHERE channel_id = ? AND ts = ?",
                (channel_id, msg["ts"]),
            ).fetchone()
            if row is None:
                continue  # 신규 메시지 — 수정이 아님
            old_edited_ts = row["edited_ts"]
            if new_edited_ts != old_edited_ts:
                count += 1
        return count

    def get_message_count(self, channel_id: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE channel_id = ?",
            (channel_id,),
        ).fetchone()
        return row["cnt"]

    # ── workspace_meta ─────────────────────────────────────

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO workspace_meta (key, value) VALUES (?, ?)",
            (key, value),
        )
        self.conn.commit()

    def get_meta(self, key: str) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM workspace_meta WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    # ── thread_summaries ─────────────────────────────────────

    def get_unsummarized_threads(self, channel_id: str | None = None) -> list[dict]:
        """LLM 요약이 없는 스레드 부모 목록."""
        if channel_id:
            rows = self.conn.execute(
                """SELECT m.channel_id, m.ts as thread_ts, m.text, m.reply_count,
                          c.name as channel_name
                   FROM messages m
                   JOIN channels c ON m.channel_id = c.id
                   LEFT JOIN thread_summaries s
                     ON m.channel_id = s.channel_id AND m.ts = s.thread_ts
                   WHERE m.channel_id = ? AND m.reply_count > 0 AND s.summary IS NULL
                   ORDER BY m.ts""",
                (channel_id,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT m.channel_id, m.ts as thread_ts, m.text, m.reply_count,
                          c.name as channel_name
                   FROM messages m
                   JOIN channels c ON m.channel_id = c.id
                   LEFT JOIN thread_summaries s
                     ON m.channel_id = s.channel_id AND m.ts = s.thread_ts
                   WHERE m.reply_count > 0 AND s.summary IS NULL
                   ORDER BY c.name, m.ts"""
            ).fetchall()
        return [dict(r) for r in rows]

    def upsert_thread_summary(
        self, channel_id: str, thread_ts: str, summary: str, method: str = "llm"
    ) -> None:
        """스레드 요약 저장/갱신."""
        self.conn.execute(
            """INSERT OR REPLACE INTO thread_summaries
               (channel_id, thread_ts, summary, method, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (channel_id, thread_ts, summary, method, _now()),
        )

    def get_thread_summary(self, channel_id: str, thread_ts: str) -> str | None:
        """캐시된 요약 조회. 없으면 None."""
        row = self.conn.execute(
            "SELECT summary FROM thread_summaries WHERE channel_id = ? AND thread_ts = ?",
            (channel_id, thread_ts),
        ).fetchone()
        return row["summary"] if row else None

    def get_all_thread_summaries(self, channel_id: str) -> dict[str, str]:
        """채널의 모든 스레드 요약을 dict로 반환. {thread_ts: summary}"""
        rows = self.conn.execute(
            "SELECT thread_ts, summary FROM thread_summaries WHERE channel_id = ?",
            (channel_id,),
        ).fetchall()
        return {r["thread_ts"]: r["summary"] for r in rows}

    def get_dates_for_channel(self, channel_id: str) -> list[str]:
        rows = self.conn.execute(
            """SELECT DISTINCT date(CAST(ts AS REAL), 'unixepoch') as d
               FROM messages WHERE channel_id = ? ORDER BY d""",
            (channel_id,),
        ).fetchall()
        return [r["d"] for r in rows]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
