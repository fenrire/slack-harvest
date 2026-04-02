"""SQLite → Markdown 변환 엔진."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from ..db.repository import Repository
from .linker import Linker


class MarkdownExporter:
    def __init__(self, repo: Repository, linker: Linker, output_dir: Path):
        self.repo = repo
        self.linker = linker
        self.output_dir = output_dir
        self._workspace_url = repo.get_meta("workspace_url") or ""

    def export_all(self) -> None:
        """전체 export: 채널별 MD + 사용자 프로필."""
        channels = self.repo.list_channels()
        for ch in channels:
            if self.repo.get_message_count(ch["id"]) > 0:
                self.export_channel(ch)
        self._export_users()

    def export_channel(self, ch: dict) -> None:
        ch_dir = self.output_dir / "channels" / ch["name"]
        ch_dir.mkdir(parents=True, exist_ok=True)

        # LLM 요약 캐시 로드 (N+1 쿼리 방지)
        self._summaries = self.repo.get_all_thread_summaries(ch["id"])

        # _index.md
        self._write_index(ch, ch_dir / "_index.md")

        # 스레드 파일명 매핑 먼저 구축 (날짜별 파일에서 스레드 링크 참조용)
        thread_parents = self.repo.get_thread_parents(ch["id"])
        self._thread_filenames: dict[str, str] = {}  # ts → filename
        if thread_parents:
            threads_dir = ch_dir / "threads"
            # 기존 스레드 파일 정리 (파일명 변경 시 중복 방지)
            if threads_dir.exists():
                for old_file in threads_dir.glob("*.md"):
                    old_file.unlink()
            threads_dir.mkdir(exist_ok=True)
            for parent in thread_parents:
                replies = self.repo.get_thread_messages(ch["id"], parent["ts"])
                summary = self._get_summary(parent)
                fname = _thread_filename(parent, replies, summary_override=summary)
                self._thread_filenames[parent["ts"]] = fname

        # 날짜별 MD
        dates = self.repo.get_dates_for_channel(ch["id"])
        for date in dates:
            msgs = self.repo.get_messages_by_channel(ch["id"], date=date)
            # 스레드 답글은 날짜별 파일에서 제외 (별도 파일)
            top_level = [m for m in msgs if not _is_reply(m)]
            if top_level:
                path = ch_dir / f"{date}.md"
                self._write_daily(ch, date, top_level, path)

        # 스레드 파일 생성
        if thread_parents:
            for parent in thread_parents:
                replies = self.repo.get_thread_messages(ch["id"], parent["ts"])
                fname = self._thread_filenames[parent["ts"]]
                path = threads_dir / fname
                self._write_thread(ch, parent, replies, path)

    # ── 내부 헬퍼 ─────────────────────────────────────────────

    def _get_summary(self, parent: dict) -> str:
        """LLM 요약 캐시 우선, 없으면 휴리스틱 폴백."""
        cached = self._summaries.get(parent["ts"])
        if cached:
            return cached
        return _truncate(parent.get("text", ""), 20)

    def _write_index(self, ch: dict, path: Path) -> None:
        lines = [
            f"# #{ch['name']}",
            "",
            f"- **Topic**: {ch.get('topic', '')}",
            f"- **Purpose**: {ch.get('purpose', '')}",
            f"- **Private**: {'예' if ch.get('is_private') else '아니오'}",
            f"- **Members**: {ch.get('member_count', 0)}",
            "",
            "## 날짜별 대화",
            "",
        ]
        dates = self.repo.get_dates_for_channel(ch["id"])
        for d in dates:
            lines.append(f"- [{d}]({d}.md)")
        path.write_text("\n".join(lines), encoding="utf-8")

    def _write_daily(
        self, ch: dict, date: str, msgs: list[dict], path: Path
    ) -> None:
        lines = [
            "---",
            f'channel: "{ch["name"]}"',
            f"date: {date}",
            f"messages: {len(msgs)}",
            "source: slack-harvest",
            "---",
            "",
            f"# #{ch['name']} - {date}",
            "",
        ]

        for msg in msgs:
            lines.extend(self._render_message(msg, ch, path))
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")

    def _write_thread(
        self, ch: dict, parent: dict, replies: list[dict], path: Path
    ) -> None:
        ts = datetime.fromtimestamp(float(parent["ts"]))
        summary = self._get_summary(parent)
        lines = [
            "---",
            f'channel: "{ch["name"]}"',
            f'thread_ts: "{parent["ts"]}"',
            f"date: {ts.strftime('%Y-%m-%d')}",
            f"replies: {len(replies)}",
            "source: slack-harvest",
            "---",
            "",
            f"# 스레드: #{ch['name']} — {summary}",
            f"> 시작: {ts.strftime('%Y-%m-%d %H:%M')}",
            "",
        ]

        current_date = ""
        for msg in replies:
            msg_date = datetime.fromtimestamp(float(msg["ts"])).strftime("%Y-%m-%d")
            if msg_date != current_date:
                current_date = msg_date
                lines.append(f"## {msg_date}")
                lines.append("")
            lines.extend(self._render_message(msg, ch, path))
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")

    def _render_message(
        self, msg: dict, ch: dict, current_file: Path
    ) -> list[str]:
        author = msg.get("display_name") or msg.get("real_name") or msg.get("user_id") or "?"
        user_id = msg.get("user_id", "")
        ts = datetime.fromtimestamp(float(msg["ts"]))
        time_str = ts.strftime("%H:%M")

        # 작성자 링크
        if user_id:
            author_md = self.linker._user_link(user_id, current_file)
        else:
            author_md = author

        # Slack permalink
        slack_link = ""
        if self._workspace_url:
            ts_id = msg["ts"].replace(".", "")
            permalink = f"{self._workspace_url}/archives/{msg['channel_id']}/p{ts_id}"
            thread_ts = msg.get("thread_ts")
            if thread_ts and thread_ts != msg["ts"]:
                permalink += f"?thread_ts={thread_ts}&cid={msg['channel_id']}"
            slack_link = f" ([원문]({permalink}))"

        lines = [f"### {time_str} - {author_md}{slack_link}"]

        # 본문 (링크 변환)
        text = self.linker.resolve_text(msg.get("text", ""), current_file)
        if text:
            lines.append("")
            # 마크다운 줄바꿈 보장: 각 줄 끝에 trailing 2 spaces 추가
            # (빈 줄은 단락 구분이므로 제외, 이미 trailing spaces가 있는 줄도 제외)
            md_lines = []
            for line in text.split("\n"):
                if line.strip() and not line.endswith("  "):
                    md_lines.append(line + "  ")
                else:
                    md_lines.append(line)
            lines.append("\n".join(md_lines))

        # 첨부 파일
        files = self._get_files_for_message(msg)
        for f in files:
            fname = f.get("name") or f.get("title") or "unknown"
            link = self.linker.file_link(fname, ch["name"], current_file)
            lines.append(f"\n{link}")

        # 리액션
        reactions = json.loads(msg.get("reactions", "[]"))
        if reactions:
            reaction_str = "  ".join(
                f":{r['name']}: ({r.get('count', len(r.get('users', [])))})"
                for r in reactions
            )
            lines.append(f"\n{reaction_str}")

        # 스레드 링크 (날짜별 파일에서만)
        reply_count = msg.get("reply_count", 0)
        if reply_count > 0 and "threads" not in str(current_file):
            thread_fname = getattr(self, "_thread_filenames", {}).get(msg["ts"], "")
            link = self.linker.thread_link(
                msg["ts"], reply_count, current_file, ch["name"], thread_fname=thread_fname
            )
            lines.append(f"\n{link}")

        return lines

    def _get_files_for_message(self, msg: dict) -> list[dict]:
        """raw_json에서 파일 목록 추출."""
        raw = json.loads(msg.get("raw_json", "{}"))
        return raw.get("files", [])

    def _export_users(self) -> None:
        users_dir = self.output_dir / "_users"
        users_dir.mkdir(parents=True, exist_ok=True)
        users = self.repo.get_all_users()
        for user in users:
            if user.get("is_bot"):
                continue
            path = users_dir / f"{user['id']}.md"
            lines = [
                f"# {user.get('display_name') or user.get('real_name') or user['id']}",
                "",
                f"- **이름**: {user.get('real_name', '')}",
                f"- **이메일**: {user.get('email', '')}",
                f"- **직책**: {user.get('title', '')}",
                f"- **Slack ID**: {user['id']}",
            ]
            path.write_text("\n".join(lines), encoding="utf-8")


def _is_reply(msg: dict) -> bool:
    """스레드 답글인지 (부모 메시지가 아닌)."""
    thread_ts = msg.get("thread_ts")
    return thread_ts is not None and thread_ts != msg.get("ts")


def _extract_topic(text: str, max_len: int = 20) -> str:
    """메시지에서 핵심 주제를 추출하여 max_len자로 요약.

    1) 슬랙 마크업/멘션 태그 제거
    2) **볼드** 텍스트가 있으면 첫 번째 볼드를 우선 사용
    3) 인사말/호칭 라인 건너뛰고 첫 실질 문장 사용
    """
    # 슬랙 태그 제거
    clean = re.sub(r"<[^>]+>", "", text).strip()

    # **볼드** 내용이 있으면 핵심일 가능성 높음
    bold = re.findall(r"\*\*(.+?)\*\*", clean)
    if not bold:
        bold = re.findall(r"\*(.+?)\*", clean)
    if bold:
        topic = bold[0].strip()
        if len(topic) > max_len:
            return topic[:max_len] + "…"
        return topic

    # 줄 단위로 분리
    lines = [ln.strip() for ln in clean.split("\n") if ln.strip()]

    # 줄 내 인사/호칭 접두어 제거 패턴
    greeting_prefix = re.compile(
        r"^("
        r"@\S+\s*"                      # @멘션
        r"|.*?(팀장|부장|실장|과장|대리|차장|님)\s*"  # 호칭
        r")*(안녕하세요|안녕하십니까)[.!,]?\s*",
        re.DOTALL,
    )
    pure_greeting = re.compile(
        r"^(안녕하세요|안녕하십니까|감사합니다|수고하셨습니다|고생하셨습니다|cc\s|CC\s)",
    )

    for line in lines:
        # @멘션 제거
        stripped = re.sub(r"@\S+", "", line).strip()
        # 인사 접두어 제거
        stripped = greeting_prefix.sub("", stripped).strip()
        # 순수 인사만 남은 경우 스킵
        if pure_greeting.match(stripped) or len(stripped) < 5:
            continue
        if len(stripped) > max_len:
            return stripped[:max_len] + "…"
        return stripped

    # 모두 인사말이면 전체에서 추출
    fallback = re.sub(r"@\S+", "", re.sub(r"\n", " ", clean)).strip()
    if len(fallback) > max_len:
        return fallback[:max_len] + "…"
    return fallback or "(내용 없음)"


def _truncate(text: str, max_len: int = 20) -> str:
    """하위 호환용 — _extract_topic으로 위임."""
    return _extract_topic(text, max_len)


def _thread_slug(text: str) -> str:
    """텍스트를 파일명용 slug로 변환 — 20자 요약."""
    summary = _truncate(text, 20)
    # HTML 엔티티 정리
    summary = summary.replace("&lt;", "").replace("&gt;", "").replace("&amp;", "&")
    slug = re.sub(r'[\\/:*?"<>|\n\r`\[\]]', '', summary)
    slug = slug.strip(". ")
    return slug or "thread"


def _thread_filename(
    parent: dict, replies: list[dict], summary_override: str | None = None
) -> str:
    """{최종덧글날짜}_{내용요약}_{thread_ts}.md"""
    # 최종 덧글 날짜 (replies 중 마지막)
    if replies:
        last_ts = max(float(r["ts"]) for r in replies)
    else:
        last_ts = float(parent["ts"])
    last_date = datetime.fromtimestamp(last_ts).strftime("%Y-%m-%d")
    if summary_override:
        slug = _make_slug(summary_override)
    else:
        slug = _thread_slug(parent.get("text", ""))
    return f"{last_date}_{slug}_{parent['ts']}.md"


def _make_slug(text: str) -> str:
    """이미 요약된 텍스트를 파일명용 slug로 변환."""
    text = text.replace("&lt;", "").replace("&gt;", "").replace("&amp;", "&")
    slug = re.sub(r'[\\/:*?"<>|\n\r`\[\]]', '', text)
    slug = slug.strip(". ")
    return slug or "thread"
