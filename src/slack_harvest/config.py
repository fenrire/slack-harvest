"""환경변수 및 설정 관리."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    slack_token: str = ""
    workspace: str = ""  # auth.test에서 자동 채움
    output_dir: Path = field(default_factory=lambda: Path.home() / "Documents" / "SlackArchive")
    nexus_outbox: Path | None = None
    gemini_api_key: str = ""

    @classmethod
    def from_env(cls) -> "Config":
        token = os.getenv("SLACK_TOKEN", "")
        output_dir = Path(os.getenv(
            "HARVEST_OUTPUT_DIR",
            str(Path.home() / "Documents" / "SlackArchive"),
        ))
        nexus_raw = os.getenv("NEXUS_OUTBOX_DIR")
        return cls(
            slack_token=token,
            output_dir=output_dir,
            nexus_outbox=Path(nexus_raw) if nexus_raw else None,
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        )

    @property
    def workspace_dir(self) -> Path:
        return self.output_dir / self.workspace

    @property
    def db_path(self) -> Path:
        return self.workspace_dir / "_db" / "slack-harvest.db"

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.slack_token:
            errors.append("SLACK_TOKEN이 설정되지 않았습니다.")
        return errors
