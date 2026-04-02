"""첨부 파일 다운로드 — Bearer 인증 헤더로 url_private 다운로드."""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
from rich.progress import Progress, BarColumn, TextColumn

from ..db.repository import Repository

log = logging.getLogger(__name__)


class FileDownloader:
    def __init__(self, token: str, repo: Repository, output_dir: Path):
        self.repo = repo
        self.output_dir = output_dir
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {token}"},
            timeout=60.0,
            follow_redirects=True,
        )

    def download_pending(self) -> int:
        """미다운로드 파일 전부 내려받기."""
        pending = self.repo.get_pending_files()
        if not pending:
            return 0

        count = 0
        with Progress(
            TextColumn("[bold]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
        ) as progress:
            task = progress.add_task("파일 다운로드", total=len(pending))
            for f in pending:
                try:
                    self._download_one(f)
                    count += 1
                except Exception as e:
                    log.warning("파일 다운로드 실패 (%s): %s", f.get("name"), e)
                progress.advance(task)
        return count

    def _download_one(self, f: dict) -> None:
        if not f.get("url_private"):
            return

        # 채널명으로 디렉토리 결정
        ch = self.repo.get_channel_by_id(f["channel_id"])
        ch_name = ch["name"] if ch else f["channel_id"]
        local_dir = self.output_dir / "channels" / ch_name / "files"
        local_dir.mkdir(parents=True, exist_ok=True)

        # 파일명 충돌 방지
        local_path = local_dir / _safe_filename(f["name"])
        if local_path.exists():
            # 이미 존재하면 스킵
            self.repo.mark_file_downloaded(f["id"], str(local_path))
            return

        resp = self._client.get(f["url_private"])
        resp.raise_for_status()
        local_path.write_bytes(resp.content)
        self.repo.mark_file_downloaded(f["id"], str(local_path))


def _safe_filename(name: str) -> str:
    """Windows/Mac 호환 파일명으로 정리."""
    # 특수문자 제거, 255자 제한
    for ch in '<>:"/\\|?*':
        name = name.replace(ch, "_")
    return name[:200] if len(name) > 200 else name
