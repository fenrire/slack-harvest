"""Slack API 클라이언트 — httpx 기반, 페이지네이션 + Rate Limit."""

from __future__ import annotations

import logging
import re

import httpx

from .rate_limiter import RateLimiter

log = logging.getLogger(__name__)


class SlackClient:
    BASE_URL = "https://slack.com/api"

    def __init__(self, token: str):
        self.token = token
        self.limiter = RateLimiter()
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        self._api_calls = 0

    @property
    def api_calls(self) -> int:
        return self._api_calls

    def _get(self, method: str, params: dict | None = None) -> dict:
        """API GET 호출. Rate limit 자동 대기 + 429 자동 재시도."""
        self.limiter.wait()
        self._api_calls += 1
        resp = self._client.get(
            f"{self.BASE_URL}/{method}", params=params or {}
        )
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 30))
            log.warning("Rate limited. %d초 대기...", retry_after)
            self.limiter.wait_retry_after(retry_after)
            return self._get(method, params)
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(
                f"Slack API 오류 ({method}): {data.get('error', 'unknown')}"
            )
        return data

    def _paginate(self, method: str, key: str, params: dict | None = None) -> list[dict]:
        """커서 기반 페이지네이션 제네릭 헬퍼."""
        params = dict(params or {})
        params.setdefault("limit", 200)
        results: list[dict] = []
        cursor: str | None = None
        while True:
            if cursor:
                params["cursor"] = cursor
            data = self._get(method, params)
            results.extend(data.get(key, []))
            cursor = data.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        return results

    # ── 인증 ──────────────────────────────────────────────────

    def auth_test(self) -> dict:
        """토큰 검증 + 워크스페이스/사용자 정보."""
        return self._get("auth.test")

    # ── 채널 ──────────────────────────────────────────────────

    def list_channels(self, include_private: bool = True) -> list[dict]:
        types = "public_channel,private_channel" if include_private else "public_channel"
        return self._paginate(
            "conversations.list", "channels",
            {"types": types, "exclude_archived": "true"},
        )

    # ── 사용자 ────────────────────────────────────────────────

    def list_users(self) -> list[dict]:
        return self._paginate("users.list", "members")

    def get_user_info(self, user_id: str) -> dict | None:
        """users.info로 개별 사용자 조회. 탈퇴/비활성이면 None."""
        try:
            data = self._get("users.info", {"user": user_id})
            return data.get("user")
        except RuntimeError:
            log.warning("사용자 %s 조회 실패 (탈퇴/비활성 가능)", user_id)
            return None

    # ── 메시지 ────────────────────────────────────────────────

    def fetch_channel_history(
        self, channel_id: str, oldest: str | None = None
    ) -> list[dict]:
        """채널 히스토리. oldest 이후 메시지만 (증분 수집)."""
        params: dict = {"channel": channel_id}
        if oldest:
            params["oldest"] = oldest
        return self._paginate("conversations.history", "messages", params)

    def fetch_thread_replies(
        self, channel_id: str, thread_ts: str
    ) -> list[dict]:
        """스레드 전체 답글."""
        return self._paginate(
            "conversations.replies", "messages",
            {"channel": channel_id, "ts": thread_ts},
        )

    # ── URL 파싱 ──────────────────────────────────────────────

    @staticmethod
    def parse_thread_url(url: str) -> tuple[str, str] | None:
        """슬랙 스레드 URL → (channel_id, thread_ts).

        예: https://team.slack.com/archives/C01ABC/p1711234567890123
        """
        m = re.search(r"/archives/(\w+)/p(\d{10})(\d{6})", url)
        if m:
            return (m.group(1), f"{m.group(2)}.{m.group(3)}")
        return None
