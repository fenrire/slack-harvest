"""LLM 분석 모듈 (스텁 - 향후 확장)

이 모듈은 두 가지 데이터 소스를 활용합니다:
1. SQLite DB: 구조적 쿼리 (누가, 언제, 어디서, 리액션 통계 등)
2. QMD 검색: 시맨틱 쿼리 (주제 검색, 결론 추출 등)

분석 요구사항이 달라질 때마다 이 모듈에 새로운 분석 메서드를 추가합니다.
"""

from __future__ import annotations

from pathlib import Path

from .db import SlackHarvestDB


class SlackAnalyzer:
    """Slack 데이터 분석기"""

    def __init__(self, db: SlackHarvestDB, export_dir: Path):
        self.db = db
        self.export_dir = export_dir

    def get_channel_summary_text(self, channel_name: str, year_month: str) -> str:
        """LLM에 전달할 수 있는 형태로 채널 메시지를 포매팅"""
        ch = self.db.get_channel_by_name(channel_name)
        if not ch:
            return f"채널 '{channel_name}'을 찾을 수 없습니다."

        messages = self.db.get_messages_for_period(ch["id"], year_month)
        if not messages:
            return f"#{channel_name}의 {year_month} 기간에 메시지가 없습니다."

        user_map = self.db.get_user_display_map()
        lines = [f"# #{channel_name} - {year_month} ({len(messages)}개 메시지)\n"]

        for msg in messages:
            user = user_map.get(msg.get("user_id", ""), "Unknown")
            text = msg.get("text", "")
            lines.append(f"[{msg['ts']}] {user}: {text}")

        return "\n".join(lines)

    def get_activity_stats(self, channel_name: str) -> dict:
        """채널 활동 통계"""
        ch = self.db.get_channel_by_name(channel_name)
        if not ch:
            return {}

        channel_id = ch["id"]
        conn = self.db.conn

        # 가장 활발한 사용자
        top_users = conn.execute(
            """SELECT u.display_name or u.real_name or u.name as name,
                      COUNT(*) as count
               FROM messages m
               JOIN users u ON m.user_id = u.id
               WHERE m.channel_id = ?
               GROUP BY m.user_id
               ORDER BY count DESC
               LIMIT 10""",
            (channel_id,),
        ).fetchall()

        # 가장 많이 사용된 리액션
        top_reactions = conn.execute(
            """SELECT emoji, COUNT(*) as count
               FROM reactions
               WHERE channel_id = ?
               GROUP BY emoji
               ORDER BY count DESC
               LIMIT 10""",
            (channel_id,),
        ).fetchall()

        # 월별 메시지 수
        monthly = conn.execute(
            """SELECT strftime('%Y-%m', ts, 'unixepoch') as month,
                      COUNT(*) as count
               FROM messages
               WHERE channel_id = ?
               GROUP BY month
               ORDER BY month""",
            (channel_id,),
        ).fetchall()

        return {
            "channel": channel_name,
            "top_users": [dict(r) for r in top_users],
            "top_reactions": [dict(r) for r in top_reactions],
            "monthly_activity": [dict(r) for r in monthly],
        }
