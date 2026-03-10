"""SQLite 데이터베이스 관리 모듈"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import SlackChannel, SlackFile, SlackMessage, SlackReaction, SlackUser

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    real_name TEXT,
    display_name TEXT,
    email TEXT,
    is_bot INTEGER NOT NULL DEFAULT 0,
    is_admin INTEGER NOT NULL DEFAULT 0,
    team_id TEXT,
    avatar_url TEXT,
    status_text TEXT,
    status_emoji TEXT,
    timezone TEXT,
    deleted INTEGER NOT NULL DEFAULT 0,
    raw_json TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS channels (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_normalized TEXT,
    topic TEXT,
    purpose TEXT,
    is_archived INTEGER NOT NULL DEFAULT 0,
    is_private INTEGER NOT NULL DEFAULT 0,
    is_general INTEGER NOT NULL DEFAULT 0,
    creator_id TEXT,
    created INTEGER,
    num_members INTEGER,
    raw_json TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    channel_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    user_id TEXT,
    text TEXT,
    thread_ts TEXT,
    reply_count INTEGER DEFAULT 0,
    reply_users_count INTEGER DEFAULT 0,
    subtype TEXT,
    bot_id TEXT,
    edited_ts TEXT,
    is_starred INTEGER NOT NULL DEFAULT 0,
    has_files INTEGER NOT NULL DEFAULT 0,
    raw_json TEXT,
    PRIMARY KEY (channel_id, ts)
);

CREATE TABLE IF NOT EXISTS reactions (
    channel_id TEXT NOT NULL,
    message_ts TEXT NOT NULL,
    emoji TEXT NOT NULL,
    user_id TEXT NOT NULL,
    PRIMARY KEY (channel_id, message_ts, emoji, user_id)
);

CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    name TEXT,
    title TEXT,
    mimetype TEXT,
    filetype TEXT,
    size INTEGER,
    url_private TEXT,
    url_private_download TEXT,
    permalink TEXT,
    channel_id TEXT,
    message_ts TEXT,
    user_id TEXT,
    created INTEGER,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS sync_state (
    channel_id TEXT PRIMARY KEY,
    last_synced_ts TEXT NOT NULL,
    last_sync_at TEXT NOT NULL DEFAULT (datetime('now')),
    total_messages INTEGER DEFAULT 0,
    status TEXT DEFAULT 'idle'
);

CREATE TABLE IF NOT EXISTS export_state (
    channel_id TEXT NOT NULL,
    year_month TEXT NOT NULL,
    last_exported_ts TEXT NOT NULL,
    exported_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (channel_id, year_month)
);
"""

INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_messages_channel_ts ON messages(channel_id, ts);
CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(channel_id, thread_ts);
CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_reactions_message ON reactions(channel_id, message_ts);
CREATE INDEX IF NOT EXISTS idx_reactions_emoji ON reactions(emoji);
CREATE INDEX IF NOT EXISTS idx_files_message ON files(channel_id, message_ts);
"""


class SlackHarvestDB:
    """SQLite 데이터베이스 매니저"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.conn.executescript(SCHEMA_SQL)
        self.conn.executescript(INDEX_SQL)
        # 버전 기록
        existing = self.conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()[0]
        if existing is None or existing < SCHEMA_VERSION:
            self.conn.execute(
                "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
            self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ─── Users ───

    def upsert_users(self, users: list[SlackUser]) -> int:
        sql = """
            INSERT OR REPLACE INTO users
            (id, name, real_name, display_name, email, is_bot, is_admin,
             team_id, avatar_url, status_text, status_emoji, timezone,
             deleted, raw_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        now = _now_iso()
        rows = [
            (
                u.id, u.name, u.real_name, u.display_name, u.email,
                int(u.is_bot), int(u.is_admin), u.team_id, u.avatar_url,
                u.status_text, u.status_emoji, u.timezone,
                int(u.deleted), u.raw_json, now,
            )
            for u in users
        ]
        self.conn.executemany(sql, rows)
        self.conn.commit()
        return len(rows)

    def get_user(self, user_id: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_all_users(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM users ORDER BY name").fetchall()
        return [dict(r) for r in rows]

    def get_user_display_map(self) -> dict[str, str]:
        """user_id → 표시 이름 매핑"""
        rows = self.conn.execute(
            "SELECT id, display_name, real_name, name FROM users"
        ).fetchall()
        result = {}
        for r in rows:
            result[r["id"]] = r["display_name"] or r["real_name"] or r["name"]
        return result

    # ─── Channels ───

    def upsert_channels(self, channels: list[SlackChannel]) -> int:
        sql = """
            INSERT OR REPLACE INTO channels
            (id, name, name_normalized, topic, purpose, is_archived,
             is_private, is_general, creator_id, created, num_members,
             raw_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        now = _now_iso()
        rows = [
            (
                c.id, c.name, c.name_normalized, c.topic, c.purpose,
                int(c.is_archived), int(c.is_private), int(c.is_general),
                c.creator_id, c.created, c.num_members, c.raw_json, now,
            )
            for c in channels
        ]
        self.conn.executemany(sql, rows)
        self.conn.commit()
        return len(rows)

    def get_all_channels(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM channels ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_channel_by_name(self, name: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM channels WHERE name = ?", (name,)
        ).fetchone()
        return dict(row) if row else None

    # ─── Messages ───

    def upsert_messages(self, messages: list[SlackMessage]) -> int:
        sql = """
            INSERT OR REPLACE INTO messages
            (channel_id, ts, user_id, text, thread_ts, reply_count,
             reply_users_count, subtype, bot_id, edited_ts,
             is_starred, has_files, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        rows = [
            (
                m.channel_id, m.ts, m.user_id, m.text, m.thread_ts,
                m.reply_count, m.reply_users_count, m.subtype, m.bot_id,
                m.edited_ts, int(m.is_starred), int(m.has_files), m.raw_json,
            )
            for m in messages
        ]
        self.conn.executemany(sql, rows)
        self.conn.commit()
        return len(rows)

    def get_thread_parents(
        self, channel_id: str, since_ts: Optional[str] = None
    ) -> list[str]:
        """reply_count > 0인 스레드 부모 ts 목록"""
        if since_ts:
            rows = self.conn.execute(
                """SELECT ts FROM messages
                   WHERE channel_id = ? AND reply_count > 0 AND ts >= ?
                   ORDER BY ts""",
                (channel_id, since_ts),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT ts FROM messages
                   WHERE channel_id = ? AND reply_count > 0
                   ORDER BY ts""",
                (channel_id,),
            ).fetchall()
        return [r["ts"] for r in rows]

    def get_messages_for_period(
        self, channel_id: str, year_month: str
    ) -> list[dict]:
        """특정 채널의 특정 월 메시지 조회 (스레드 포함)"""
        # year_month: "2025-01" → ts 범위 계산
        from datetime import datetime as dt

        start = dt.strptime(year_month, "%Y-%m")
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)

        start_ts = str(start.timestamp())
        end_ts = str(end.timestamp())

        rows = self.conn.execute(
            """SELECT m.*, u.display_name, u.real_name, u.name as user_name
               FROM messages m
               LEFT JOIN users u ON m.user_id = u.id
               WHERE m.channel_id = ?
                 AND m.ts >= ? AND m.ts < ?
               ORDER BY m.ts""",
            (channel_id, start_ts, end_ts),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_thread_replies(self, channel_id: str, thread_ts: str) -> list[dict]:
        """스레드의 답글 조회"""
        rows = self.conn.execute(
            """SELECT m.*, u.display_name, u.real_name, u.name as user_name
               FROM messages m
               LEFT JOIN users u ON m.user_id = u.id
               WHERE m.channel_id = ? AND m.thread_ts = ? AND m.ts != ?
               ORDER BY m.ts""",
            (channel_id, thread_ts, thread_ts),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_message_periods(self, channel_id: str) -> list[str]:
        """채널의 메시지가 존재하는 년-월 목록"""
        rows = self.conn.execute(
            """SELECT DISTINCT strftime('%Y-%m', ts, 'unixepoch') as period
               FROM messages
               WHERE channel_id = ?
               ORDER BY period""",
            (channel_id,),
        ).fetchall()
        return [r["period"] for r in rows]

    def get_latest_ts_for_period(
        self, channel_id: str, year_month: str
    ) -> Optional[str]:
        from datetime import datetime as dt

        start = dt.strptime(year_month, "%Y-%m")
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)

        row = self.conn.execute(
            """SELECT MAX(ts) as max_ts FROM messages
               WHERE channel_id = ? AND ts >= ? AND ts < ?""",
            (channel_id, str(start.timestamp()), str(end.timestamp())),
        ).fetchone()
        return row["max_ts"] if row else None

    # ─── Reactions ───

    def upsert_reactions(self, reactions: list[SlackReaction]) -> int:
        sql = """
            INSERT OR REPLACE INTO reactions
            (channel_id, message_ts, emoji, user_id)
            VALUES (?, ?, ?, ?)
        """
        rows = [(r.channel_id, r.message_ts, r.emoji, r.user_id) for r in reactions]
        self.conn.executemany(sql, rows)
        self.conn.commit()
        return len(rows)

    def get_reactions_for_message(
        self, channel_id: str, message_ts: str
    ) -> list[dict]:
        rows = self.conn.execute(
            """SELECT emoji, GROUP_CONCAT(u.display_name) as users, COUNT(*) as count
               FROM reactions r
               LEFT JOIN users u ON r.user_id = u.id
               WHERE r.channel_id = ? AND r.message_ts = ?
               GROUP BY emoji""",
            (channel_id, message_ts),
        ).fetchall()
        return [dict(r) for r in rows]

    # ─── Files ───

    def upsert_files(self, files: list[SlackFile]) -> int:
        sql = """
            INSERT OR REPLACE INTO files
            (id, name, title, mimetype, filetype, size,
             url_private, url_private_download, permalink,
             channel_id, message_ts, user_id, created, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        rows = [
            (
                f.id, f.name, f.title, f.mimetype, f.filetype, f.size,
                f.url_private, f.url_private_download, f.permalink,
                f.channel_id, f.message_ts, f.user_id, f.created, f.raw_json,
            )
            for f in files
        ]
        self.conn.executemany(sql, rows)
        self.conn.commit()
        return len(rows)

    def get_files_for_message(
        self, channel_id: str, message_ts: str
    ) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM files WHERE channel_id = ? AND message_ts = ?",
            (channel_id, message_ts),
        ).fetchall()
        return [dict(r) for r in rows]

    # ─── Sync State ───

    def get_sync_state(self, channel_id: str) -> Optional[str]:
        """채널의 마지막 동기화 ts 반환"""
        row = self.conn.execute(
            "SELECT last_synced_ts FROM sync_state WHERE channel_id = ?",
            (channel_id,),
        ).fetchone()
        return row["last_synced_ts"] if row else None

    def update_sync_state(
        self, channel_id: str, latest_ts: str, total_messages: Optional[int] = None
    ) -> None:
        now = _now_iso()
        if total_messages is not None:
            self.conn.execute(
                """INSERT OR REPLACE INTO sync_state
                   (channel_id, last_synced_ts, last_sync_at, total_messages, status)
                   VALUES (?, ?, ?, ?, 'idle')""",
                (channel_id, latest_ts, now, total_messages),
            )
        else:
            self.conn.execute(
                """INSERT INTO sync_state (channel_id, last_synced_ts, last_sync_at, status)
                   VALUES (?, ?, ?, 'idle')
                   ON CONFLICT(channel_id) DO UPDATE SET
                     last_synced_ts = excluded.last_synced_ts,
                     last_sync_at = excluded.last_sync_at,
                     status = 'idle'""",
                (channel_id, latest_ts, now),
            )
        self.conn.commit()

    def set_sync_status(self, channel_id: str, status: str) -> None:
        self.conn.execute(
            """INSERT INTO sync_state (channel_id, last_synced_ts, status)
               VALUES (?, '0', ?)
               ON CONFLICT(channel_id) DO UPDATE SET status = ?""",
            (channel_id, status, status),
        )
        self.conn.commit()

    def get_all_sync_states(self) -> list[dict]:
        rows = self.conn.execute(
            """SELECT s.*, c.name as channel_name
               FROM sync_state s
               LEFT JOIN channels c ON s.channel_id = c.id
               ORDER BY c.name"""
        ).fetchall()
        return [dict(r) for r in rows]

    # ─── Export State ───

    def get_export_state(
        self, channel_id: str, year_month: str
    ) -> Optional[str]:
        row = self.conn.execute(
            """SELECT last_exported_ts FROM export_state
               WHERE channel_id = ? AND year_month = ?""",
            (channel_id, year_month),
        ).fetchone()
        return row["last_exported_ts"] if row else None

    def update_export_state(
        self, channel_id: str, year_month: str, latest_ts: str
    ) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO export_state
               (channel_id, year_month, last_exported_ts, exported_at)
               VALUES (?, ?, ?, ?)""",
            (channel_id, year_month, latest_ts, _now_iso()),
        )
        self.conn.commit()

    # ─── Stats ───

    def get_channel_stats(self) -> list[dict]:
        rows = self.conn.execute(
            """SELECT c.id, c.name, c.is_archived,
                      COUNT(m.ts) as message_count,
                      MIN(m.ts) as earliest_ts,
                      MAX(m.ts) as latest_ts,
                      s.last_synced_ts, s.last_sync_at, s.status
               FROM channels c
               LEFT JOIN messages m ON c.id = m.channel_id
               LEFT JOIN sync_state s ON c.id = s.channel_id
               GROUP BY c.id
               ORDER BY c.name"""
        ).fetchall()
        return [dict(r) for r in rows]

    def get_total_counts(self) -> dict:
        users = self.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        channels = self.conn.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
        messages = self.conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        reactions = self.conn.execute("SELECT COUNT(*) FROM reactions").fetchone()[0]
        files = self.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        return {
            "users": users,
            "channels": channels,
            "messages": messages,
            "reactions": reactions,
            "files": files,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
