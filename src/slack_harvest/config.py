"""설정 관리 모듈"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass
class Config:
    slack_bot_token: Optional[str]
    slack_user_token: Optional[str] = None
    db_path: Path = Path("data/slack_harvest.db")
    export_dir: Path = Path("export")
    rate_limit_delay: float = 1.3
    batch_size: int = 200
    max_retries: int = 5
    channels_include: list[str] = field(default_factory=list)
    channels_exclude: list[str] = field(default_factory=list)
    include_archived: bool = False
    include_private: bool = False

    @property
    def active_token(self) -> str:
        """User Token 우선, 없으면 Bot Token fallback"""
        token = self.slack_user_token or self.slack_bot_token
        if not token:
            raise ValueError("SLACK_USER_TOKEN 또는 SLACK_BOT_TOKEN이 필요합니다")
        return token

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> Config:
        if env_file is None:
            env_file = Path(".env")
        load_dotenv(env_file)

        bot_token = os.environ.get("SLACK_BOT_TOKEN")
        user_token = os.environ.get("SLACK_USER_TOKEN")

        if not bot_token and not user_token:
            raise ValueError("SLACK_BOT_TOKEN 또는 SLACK_USER_TOKEN 환경 변수가 필요합니다")

        def _split_csv(key: str) -> list[str]:
            val = os.environ.get(key, "").strip()
            return [v.strip() for v in val.split(",") if v.strip()] if val else []

        return cls(
            slack_bot_token=bot_token,
            slack_user_token=user_token,
            db_path=Path(os.environ.get("HARVEST_DB_PATH", "data/slack_harvest.db")),
            export_dir=Path(os.environ.get("HARVEST_EXPORT_DIR", "export")),
            channels_include=_split_csv("HARVEST_CHANNELS_INCLUDE"),
            channels_exclude=_split_csv("HARVEST_CHANNELS_EXCLUDE"),
        )
