"""Slack 데이터 모델"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SlackUser:
    id: str
    name: str
    real_name: Optional[str] = None
    display_name: Optional[str] = None
    email: Optional[str] = None
    is_bot: bool = False
    is_admin: bool = False
    team_id: Optional[str] = None
    avatar_url: Optional[str] = None
    status_text: Optional[str] = None
    status_emoji: Optional[str] = None
    timezone: Optional[str] = None
    deleted: bool = False
    raw_json: Optional[str] = None

    @classmethod
    def from_api(cls, data: dict) -> SlackUser:
        profile = data.get("profile", {})
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            real_name=data.get("real_name") or profile.get("real_name"),
            display_name=profile.get("display_name"),
            email=profile.get("email"),
            is_bot=data.get("is_bot", False),
            is_admin=data.get("is_admin", False),
            team_id=data.get("team_id"),
            avatar_url=profile.get("image_72"),
            status_text=profile.get("status_text"),
            status_emoji=profile.get("status_emoji"),
            timezone=data.get("tz"),
            deleted=data.get("deleted", False),
            raw_json=json.dumps(data, ensure_ascii=False),
        )

    @property
    def label(self) -> str:
        """표시용 이름 반환"""
        return self.display_name or self.real_name or self.name


@dataclass
class SlackChannel:
    id: str
    name: str
    name_normalized: Optional[str] = None
    topic: Optional[str] = None
    purpose: Optional[str] = None
    is_archived: bool = False
    is_private: bool = False
    is_general: bool = False
    creator_id: Optional[str] = None
    created: Optional[int] = None
    num_members: Optional[int] = None
    raw_json: Optional[str] = None

    @classmethod
    def from_api(cls, data: dict) -> SlackChannel:
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            name_normalized=data.get("name_normalized"),
            topic=data.get("topic", {}).get("value"),
            purpose=data.get("purpose", {}).get("value"),
            is_archived=data.get("is_archived", False),
            is_private=data.get("is_private", False),
            is_general=data.get("is_general", False),
            creator_id=data.get("creator"),
            created=data.get("created"),
            num_members=data.get("num_members"),
            raw_json=json.dumps(data, ensure_ascii=False),
        )


@dataclass
class SlackMessage:
    channel_id: str
    ts: str
    user_id: Optional[str] = None
    text: Optional[str] = None
    thread_ts: Optional[str] = None
    reply_count: int = 0
    reply_users_count: int = 0
    subtype: Optional[str] = None
    bot_id: Optional[str] = None
    edited_ts: Optional[str] = None
    is_starred: bool = False
    has_files: bool = False
    reactions: list[dict] = field(default_factory=list)
    files: list[dict] = field(default_factory=list)
    raw_json: Optional[str] = None

    @classmethod
    def from_api(cls, data: dict, channel_id: str) -> SlackMessage:
        return cls(
            channel_id=channel_id,
            ts=data["ts"],
            user_id=data.get("user"),
            text=data.get("text"),
            thread_ts=data.get("thread_ts"),
            reply_count=data.get("reply_count", 0),
            reply_users_count=data.get("reply_users_count", 0),
            subtype=data.get("subtype"),
            bot_id=data.get("bot_id"),
            edited_ts=data.get("edited", {}).get("ts") if data.get("edited") else None,
            is_starred=data.get("is_starred", False),
            has_files=bool(data.get("files")),
            reactions=data.get("reactions", []),
            files=data.get("files", []),
            raw_json=json.dumps(data, ensure_ascii=False),
        )

    @property
    def is_thread_parent(self) -> bool:
        return self.thread_ts == self.ts and self.reply_count > 0

    @property
    def is_thread_reply(self) -> bool:
        return self.thread_ts is not None and self.thread_ts != self.ts


@dataclass
class SlackReaction:
    channel_id: str
    message_ts: str
    emoji: str
    user_id: str

    @classmethod
    def from_message_api(
        cls, channel_id: str, message_ts: str, reaction_data: dict
    ) -> list[SlackReaction]:
        """메시지의 reactions 배열에서 개별 리액션 리스트 생성"""
        results = []
        for user_id in reaction_data.get("users", []):
            results.append(
                cls(
                    channel_id=channel_id,
                    message_ts=message_ts,
                    emoji=reaction_data["name"],
                    user_id=user_id,
                )
            )
        return results


@dataclass
class SlackFile:
    id: str
    name: Optional[str] = None
    title: Optional[str] = None
    mimetype: Optional[str] = None
    filetype: Optional[str] = None
    size: Optional[int] = None
    url_private: Optional[str] = None
    url_private_download: Optional[str] = None
    permalink: Optional[str] = None
    channel_id: Optional[str] = None
    message_ts: Optional[str] = None
    user_id: Optional[str] = None
    created: Optional[int] = None
    raw_json: Optional[str] = None

    @classmethod
    def from_api(
        cls, data: dict, channel_id: str = None, message_ts: str = None
    ) -> SlackFile:
        return cls(
            id=data["id"],
            name=data.get("name"),
            title=data.get("title"),
            mimetype=data.get("mimetype"),
            filetype=data.get("filetype"),
            size=data.get("size"),
            url_private=data.get("url_private"),
            url_private_download=data.get("url_private_download"),
            permalink=data.get("permalink"),
            channel_id=channel_id,
            message_ts=message_ts,
            user_id=data.get("user"),
            created=data.get("created"),
            raw_json=json.dumps(data, ensure_ascii=False),
        )
