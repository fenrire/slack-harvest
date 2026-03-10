"""Markdown 내보내기 모듈 (QMD 인덱싱용)"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from .db import SlackHarvestDB

logger = logging.getLogger(__name__)


class MarkdownExporter:
    """DB의 Slack 데이터를 채널별/월별 Markdown 파일로 내보내기"""

    def __init__(self, db: SlackHarvestDB, export_dir: Path):
        self.db = db
        self.export_dir = export_dir
        self._user_map: dict[str, str] = {}

    def export_all(self, force: bool = False, channel_names: list[str] | None = None) -> dict:
        """전체 내보내기. 변경된 월만 재생성 (force=True면 전체)"""
        self._user_map = self.db.get_user_display_map()
        stats = {"channels": 0, "files": 0, "skipped": 0}

        channels = self.db.get_all_channels()
        if channel_names:
            name_set = set(channel_names)
            channels = [c for c in channels if c["name"] in name_set]

        self._export_workspace_index(channels)

        for channel in channels:
            exported = self._export_channel(channel, force=force)
            stats["channels"] += 1
            stats["files"] += exported["files"]
            stats["skipped"] += exported["skipped"]

        logger.info(
            "내보내기 완료: 채널 %d개, 파일 %d개 생성, %d개 스킵",
            stats["channels"], stats["files"], stats["skipped"],
        )
        return stats

    def _export_workspace_index(self, channels: list[dict]) -> None:
        """워크스페이스 개요 인덱스 파일 생성"""
        counts = self.db.get_total_counts()
        lines = [
            "---",
            "title: Slack 워크스페이스 개요",
            f"exported_at: {_now_iso()}",
            "---",
            "",
            "# Slack 워크스페이스 개요",
            "",
            f"- 사용자: {counts['users']}명",
            f"- 채널: {counts['channels']}개",
            f"- 메시지: {counts['messages']}개",
            f"- 리액션: {counts['reactions']}개",
            f"- 파일: {counts['files']}개",
            "",
            "## 채널 목록",
            "",
        ]

        for ch in channels:
            archived = " (보관됨)" if ch["is_archived"] else ""
            purpose = f" - {ch['purpose']}" if ch.get("purpose") else ""
            lines.append(f"- **#{ch['name']}**{archived}{purpose}")

        path = self.export_dir / "slack" / "_index.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines), encoding="utf-8")

    def _export_channel(self, channel: dict, force: bool = False) -> dict:
        """채널의 메시지를 월별 Markdown으로 내보내기"""
        result = {"files": 0, "skipped": 0}
        channel_id = channel["id"]
        channel_name = channel["name"]
        channel_dir = self.export_dir / "slack" / "channels" / channel_name

        # 채널 정보 파일
        self._export_channel_info(channel, channel_dir)

        periods = self.db.get_message_periods(channel_id)
        for year_month in periods:
            # 증분 체크
            if not force:
                last_exported = self.db.get_export_state(channel_id, year_month)
                latest_ts = self.db.get_latest_ts_for_period(channel_id, year_month)
                if last_exported and latest_ts and last_exported >= latest_ts:
                    result["skipped"] += 1
                    continue

            messages = self.db.get_messages_for_period(channel_id, year_month)
            if not messages:
                continue

            md = self._render_month(channel, year_month, messages)
            out_path = channel_dir / f"{year_month}.md"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(md, encoding="utf-8")

            # export state 업데이트
            latest_ts = self.db.get_latest_ts_for_period(channel_id, year_month)
            if latest_ts:
                self.db.update_export_state(channel_id, year_month, latest_ts)

            result["files"] += 1
            logger.debug("내보내기: #%s %s", channel_name, year_month)

        return result

    def _export_channel_info(self, channel: dict, channel_dir: Path) -> None:
        """채널 메타데이터 파일 생성"""
        lines = [
            "---",
            f"title: \"#{channel['name']}\"",
            f"channel_id: {channel['id']}",
            f"exported_at: {_now_iso()}",
            "---",
            "",
            f"# #{channel['name']}",
            "",
        ]
        if channel.get("topic"):
            lines.append(f"**토픽:** {channel['topic']}")
            lines.append("")
        if channel.get("purpose"):
            lines.append(f"**목적:** {channel['purpose']}")
            lines.append("")
        if channel.get("is_archived"):
            lines.append("*이 채널은 보관되었습니다.*")
            lines.append("")

        channel_dir.mkdir(parents=True, exist_ok=True)
        (channel_dir / "_channel_info.md").write_text(
            "\n".join(lines), encoding="utf-8"
        )

    def _render_month(
        self, channel: dict, year_month: str, messages: list[dict]
    ) -> str:
        """월별 메시지를 Markdown으로 렌더링"""
        channel_name = channel["name"]

        # 비-답글 메시지만 (답글은 스레드 블록 안에서 렌더링)
        top_level = [m for m in messages if not _is_thread_reply(m)]
        msg_count = len(messages)

        # 헤더
        lines = [
            "---",
            f'title: "#{channel_name} - {year_month}"',
            f"channel: {channel_name}",
            f"channel_id: {channel['id']}",
            f"period: {year_month}",
            f"message_count: {msg_count}",
            f"exported_at: {_now_iso()}",
            "---",
            "",
            f"# #{channel_name} - {year_month}",
            "",
        ]

        current_date = None
        for msg in top_level:
            msg_date = _ts_to_date(msg["ts"])
            if msg_date != current_date:
                if current_date is not None:
                    lines.append("---")
                    lines.append("")
                lines.append(f"## {msg_date}")
                lines.append("")
                current_date = msg_date

            self._render_message(lines, msg, channel["id"])
            lines.append("")

        return "\n".join(lines)

    def _render_message(
        self, lines: list[str], msg: dict, channel_id: str
    ) -> None:
        """단일 메시지 렌더링"""
        time_str = _ts_to_time(msg["ts"])
        user_name = self._resolve_user(msg)

        # 시스템 메시지 (join, leave, topic 등)
        if msg.get("subtype") in (
            "channel_join", "channel_leave", "channel_topic",
            "channel_purpose", "channel_name",
        ):
            lines.append(f"*{time_str} - {user_name}: {msg.get('text', '')}*")
            return

        lines.append(f"### {time_str} - {user_name}")

        # 메시지 본문
        text = msg.get("text") or ""
        # user ID 멘션 치환 (<@U123> → @이름)
        text = self._replace_user_mentions(text)
        if text:
            lines.append(text)

        # 리액션
        reactions = self.db.get_reactions_for_message(channel_id, msg["ts"])
        for r in reactions:
            users_str = r["users"] or ""
            lines.append(f"- :{r['emoji']}: ({r['count']}: {users_str})")

        # 파일 첨부
        files = self.db.get_files_for_message(channel_id, msg["ts"])
        for f in files:
            size_str = _format_size(f.get("size"))
            lines.append(
                f"- 첨부: `{f.get('name', 'file')}` ({f.get('mimetype', '?')}, {size_str})"
            )

        # 스레드
        if msg.get("reply_count", 0) > 0:
            thread_replies = self.db.get_thread_replies(channel_id, msg["ts"])
            if thread_replies:
                reply_count = len(thread_replies)
                # 스레드 제목: 본문 첫 줄에서 추출
                thread_title = (text[:50] + "...") if len(text) > 50 else text
                lines.append("")
                lines.append(f"#### Thread ({reply_count} replies)")
                lines.append("")

                # 부모 메시지
                lines.append(f"> **{time_str} - {user_name}** (thread start)")
                for t_line in text.split("\n"):
                    lines.append(f"> {t_line}")
                lines.append(">")

                # 답글
                for reply in thread_replies:
                    r_time = _ts_to_time(reply["ts"])
                    r_user = self._resolve_user(reply)
                    r_text = self._replace_user_mentions(reply.get("text") or "")
                    lines.append(f"> **{r_time} - {r_user}**")
                    for r_line in r_text.split("\n"):
                        lines.append(f"> {r_line}")
                    lines.append(">")

    def _resolve_user(self, msg: dict) -> str:
        """메시지에서 사용자 이름 결정"""
        # JOIN된 user 테이블 데이터 우선
        display = msg.get("display_name") or msg.get("real_name") or msg.get("user_name")
        if display:
            return display
        # fallback: user_map
        user_id = msg.get("user_id")
        if user_id and user_id in self._user_map:
            return self._user_map[user_id]
        # bot
        if msg.get("bot_id"):
            return f"Bot ({msg['bot_id']})"
        return "Unknown"

    def _replace_user_mentions(self, text: str) -> str:
        """<@U123ABC> 형식 멘션을 @이름으로 치환"""
        import re

        def replace_match(m):
            user_id = m.group(1)
            name = self._user_map.get(user_id, user_id)
            return f"@{name}"

        return re.sub(r"<@(U[A-Z0-9]+)>", replace_match, text)


# ─── Helpers ───


def _ts_to_date(ts: str) -> str:
    """Slack ts → YYYY-MM-DD"""
    dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
    return dt.strftime("%Y-%m-%d")


def _ts_to_time(ts: str) -> str:
    """Slack ts → HH:MM"""
    dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
    return dt.strftime("%H:%M")


def _is_thread_reply(msg: dict) -> bool:
    """스레드 답글인지 판별"""
    thread_ts = msg.get("thread_ts")
    return thread_ts is not None and thread_ts != msg["ts"]


def _format_size(size: int | None) -> str:
    """바이트 → 읽기 쉬운 크기"""
    if size is None:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
