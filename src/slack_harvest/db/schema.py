"""SQLite 스키마 정의 및 DB 초기화."""

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

DDL = """\
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS schema_info (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS channels (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    former_name  TEXT DEFAULT '',
    topic        TEXT DEFAULT '',
    purpose      TEXT DEFAULT '',
    is_private   INTEGER DEFAULT 0,
    is_archived  INTEGER DEFAULT 0,
    member_count INTEGER DEFAULT 0,
    raw_json     TEXT DEFAULT '{}',
    fetched_at   TEXT,
    latest_ts    TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id           TEXT PRIMARY KEY,
    display_name TEXT NOT NULL DEFAULT '',
    real_name    TEXT DEFAULT '',
    email        TEXT DEFAULT '',
    title        TEXT DEFAULT '',
    avatar_url   TEXT DEFAULT '',
    is_bot       INTEGER DEFAULT 0,
    raw_json     TEXT DEFAULT '{}',
    fetched_at   TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    channel_id  TEXT NOT NULL,
    ts          TEXT NOT NULL,
    thread_ts   TEXT,
    user_id     TEXT,
    text        TEXT DEFAULT '',
    subtype     TEXT DEFAULT '',
    edited_ts   TEXT,
    reply_count INTEGER DEFAULT 0,
    reactions   TEXT DEFAULT '[]',
    raw_json    TEXT DEFAULT '{}',
    PRIMARY KEY (channel_id, ts)
);

CREATE TABLE IF NOT EXISTS files (
    id          TEXT PRIMARY KEY,
    channel_id  TEXT,
    message_ts  TEXT,
    user_id     TEXT,
    name        TEXT NOT NULL DEFAULT 'unknown',
    mimetype    TEXT DEFAULT '',
    url_private TEXT DEFAULT '',
    local_path  TEXT DEFAULT '',
    size        INTEGER DEFAULT 0,
    downloaded  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sync_state (
    channel_id     TEXT PRIMARY KEY,
    last_synced_ts TEXT,
    status         TEXT DEFAULT 'idle'
);

CREATE INDEX IF NOT EXISTS idx_messages_channel_ts
    ON messages(channel_id, ts);
CREATE INDEX IF NOT EXISTS idx_messages_thread
    ON messages(channel_id, thread_ts);
CREATE INDEX IF NOT EXISTS idx_files_channel_msg
    ON files(channel_id, message_ts);

CREATE TABLE IF NOT EXISTS workspace_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS thread_summaries (
    channel_id TEXT NOT NULL,
    thread_ts  TEXT NOT NULL,
    summary    TEXT NOT NULL,
    method     TEXT DEFAULT 'llm',
    created_at TEXT NOT NULL,
    PRIMARY KEY (channel_id, thread_ts)
);
"""


def init_db(db_path: Path) -> sqlite3.Connection:
    """DB 파일 생성 + 스키마 적용. 이미 존재하면 그대로 사용."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(DDL)
    conn.execute(
        "INSERT OR IGNORE INTO schema_info (version) VALUES (?)",
        (SCHEMA_VERSION,),
    )
    # 기존 DB에 누락된 컬럼 마이그레이션
    existing = {row[1] for row in conn.execute("PRAGMA table_info(channels)")}
    if "former_name" not in existing:
        conn.execute("ALTER TABLE channels ADD COLUMN former_name TEXT DEFAULT ''")
    conn.commit()
    return conn
