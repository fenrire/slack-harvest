"""환경변수 및 설정 관리."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _load_yaml_config() -> dict:
    """프로젝트 루트의 config.yaml을 로드. 없으면 빈 딕트."""
    path = Path(os.getenv("HARVEST_CONFIG_FILE", "config.yaml"))
    if path.exists():
        try:
            import yaml
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            pass
    return {}


_YAML = _load_yaml_config()


def _from_cm(keyring_service: str, key: str, env_var: str) -> str:
    """Windows CM(keyring) 우선, 없으면 env var fallback."""
    if keyring_service and key:
        try:
            import keyring
            val = keyring.get_password(keyring_service, key)
            if val:
                return val
        except Exception:
            pass
    return os.getenv(env_var, "")


@dataclass
class Config:
    slack_token: str = ""
    workspace: str = ""  # auth.test에서 자동 채움
    output_dir: Path = field(default_factory=lambda: Path.home() / "Documents" / "SlackArchive")
    nexus_outbox: Path | None = None
    gemini_api_key: str = ""
    log_file: Path | None = None
    channels_file: Path = field(default_factory=lambda: Path("channels.txt"))

    @classmethod
    def from_env(cls) -> "Config":
        creds = _YAML.get("credentials", {})
        slack_cred = creds.get("slack", {})
        gemini_cred = creds.get("gemini", {})

        token = _from_cm(
            slack_cred.get("keyring_service", ""),
            slack_cred.get("key", ""),
            "SLACK_TOKEN",
        )
        output_dir = Path(os.getenv(
            "HARVEST_OUTPUT_DIR",
            str(Path.home() / "Documents" / "SlackArchive"),
        ))
        nexus_raw = os.getenv("NEXUS_OUTBOX_DIR")
        log_raw = os.getenv("HARVEST_LOG_FILE")
        channels_raw = os.getenv("HARVEST_CHANNELS_FILE", "channels.txt")
        return cls(
            slack_token=token,
            output_dir=output_dir,
            nexus_outbox=Path(nexus_raw) if nexus_raw else None,
            gemini_api_key=_from_cm(
                gemini_cred.get("keyring_service", ""),
                gemini_cred.get("key", ""),
                "GEMINI_API_KEY",
            ),
            log_file=Path(log_raw).expanduser() if log_raw else None,
            channels_file=Path(channels_raw),
        )

    def load_channels(self) -> list[str]:
        """channels.txt에서 수집 대상 채널 목록을 읽는다. 빈 줄과 #주석 무시."""
        if not self.channels_file.exists():
            return []
        lines = self.channels_file.read_text(encoding="utf-8").splitlines()
        return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]

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
