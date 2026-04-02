"""Slack 데이터 모델."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SlackUser:
    id: str
    display_name: str
    real_name: str = ""
    email: str = ""
    title: str = ""
    avatar_url: str = ""
    is_bot: bool = False


@dataclass
class SlackFile:
    id: str
    name: str
    mimetype: str = ""
    url_private: str = ""
    size: int = 0
    user_id: str = ""


@dataclass
class SlackMessage:
    ts: str
    channel_id: str
    user_id: str = ""
    text: str = ""
    thread_ts: str | None = None
    subtype: str = ""
    reply_count: int = 0
    reactions: list[dict] = field(default_factory=list)
    files: list[SlackFile] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    @property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(float(self.ts))

    @property
    def date_str(self) -> str:
        return self.timestamp.strftime("%Y-%m-%d")

    @property
    def is_thread_parent(self) -> bool:
        return self.reply_count > 0

    @property
    def is_thread_reply(self) -> bool:
        return self.thread_ts is not None and self.thread_ts != self.ts
