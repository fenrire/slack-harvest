"""슬랙 마크업 → 로컬 상대 경로 마크다운 링크 변환."""

from __future__ import annotations

import html
import re
from os.path import relpath
from pathlib import Path


class Linker:
    """메시지 텍스트 내 슬랙 참조를 로컬 상대 경로로 변환."""

    def __init__(
        self,
        users: dict[str, dict],
        channels: dict[str, dict],
        base_dir: Path,
    ):
        self.users = users
        self.channels = channels
        self.base_dir = base_dir

    def resolve_text(self, text: str, current_file: Path) -> str:
        """메시지 텍스트 내 모든 슬랙 참조를 마크다운 링크로 변환."""
        # @멘션 → 사용자 프로필 링크
        text = re.sub(
            r"<@(\w+)>",
            lambda m: self._user_link(m.group(1), current_file),
            text,
        )
        # #채널 → 채널 인덱스 링크
        text = re.sub(
            r"<#(\w+)\|?([^>]*)>",
            lambda m: self._channel_link(m.group(1), m.group(2), current_file),
            text,
        )
        # 슬랙 URL 링크 <url|label>
        text = re.sub(
            r"<(https?://[^|>]+)\|?([^>]*)>",
            lambda m: self._url_link(m.group(1), m.group(2)),
            text,
        )
        # <!subteam^ID|@name> → @name, <!subteam^ID> → @그룹
        text = re.sub(r"<!subteam\^[^|>]+\|@?([^>]+)>", r"@\1", text)
        text = re.sub(r"<!subteam\^[^>]+>", "@그룹", text)
        # <!here>, <!channel>, <!everyone> → @here 등
        text = re.sub(r"<!here(\|[^>]*)?>", "@here", text)
        text = re.sub(r"<!channel(\|[^>]*)?>", "@channel", text)
        text = re.sub(r"<!everyone(\|[^>]*)?>", "@everyone", text)
        # HTML 엔티티 디코딩 (&gt; → >, &lt; → <, &amp; → &)
        text = html.unescape(text)
        # 슬랙 마크업 → 표준 마크다운
        text = _convert_slack_markup(text)
        return text

    def _user_link(self, user_id: str, current_file: Path) -> str:
        user = self.users.get(user_id)
        name = (user.get("display_name") or user.get("real_name") or user_id) if user else user_id
        target = self.base_dir / "_users" / f"{user_id}.md"
        rel = _relative(current_file, target)
        return f"[@{name}]({rel})"

    def _channel_link(
        self, channel_id: str, fallback_name: str, current_file: Path
    ) -> str:
        ch = self.channels.get(channel_id)
        name = ch["name"] if ch else (fallback_name or channel_id)
        target = self.base_dir / "channels" / name / "_index.md"
        rel = _relative(current_file, target)
        return f"[#{name}]({rel})"

    def _url_link(self, url: str, label: str) -> str:
        return f"[{label or url}]({url})"

    def file_link(
        self, file_name: str, channel_name: str, current_file: Path
    ) -> str:
        target = self.base_dir / "channels" / channel_name / "files" / file_name
        rel = _relative(current_file, target)
        # 이미지인지 판별
        if _is_image(file_name):
            return f"![{file_name}]({rel})"
        return f"[{file_name}]({rel})"

    def thread_link(self, thread_ts: str, reply_count: int, current_file: Path, channel_name: str, thread_fname: str = "") -> str:
        fname = thread_fname or f"{thread_ts}.md"
        target = self.base_dir / "channels" / channel_name / "threads" / fname
        rel = _relative(current_file, target)
        return f"[스레드 ({reply_count}개 답글)]({rel})"


def _relative(from_file: Path, to_file: Path) -> str:
    """from_file 기준 to_file의 상대 경로 (forward slash)."""
    return relpath(str(to_file), str(from_file.parent)).replace("\\", "/")


def _is_image(name: str) -> bool:
    return name.lower().rsplit(".", 1)[-1] in {"png", "jpg", "jpeg", "gif", "webp", "svg"}


def _convert_slack_markup(text: str) -> str:
    """슬랙 마크업을 표준 마크다운으로 변환."""
    # ```code``` → fenced code block (슬랙 인라인 코드 블록 → 마크다운 코드 블록)
    # 여러 줄에 걸친 것도, 한 줄 안에서 열고 닫는 것도 처리
    text = re.sub(
        r"```([^`]+?)```",
        lambda m: f"\n```\n{m.group(1).strip()}\n```\n",
        text,
        flags=re.DOTALL,
    )
    # *bold* → **bold** (단, 이미 **로 감싸진 건 건너뜀)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"**\1**", text)
    # _italic_ → *italic*
    text = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"*\1*", text)
    # ~strikethrough~ → ~~strikethrough~~
    text = re.sub(r"~([^~\n]+)~", r"~~\1~~", text)
    # 알파벳/로마숫자 리스트 마커를 마크다운 리스트로 변환
    # "    a. text" → "    - a. text"  (들여쓰기 보존 + unordered list 마커 추가)
    text = re.sub(
        r"^(\s+)([a-z]|i{1,3}|iv|vi{0,3})\. ",
        r"\1- \2. ",
        text,
        flags=re.MULTILINE,
    )
    return text
