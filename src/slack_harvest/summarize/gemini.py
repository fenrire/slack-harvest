"""Gemini API를 이용한 스레드 요약."""

from __future__ import annotations

import time
import httpx


GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"

SYSTEM_PROMPT = """당신은 Slack 스레드를 한국어로 요약하는 어시스턴트입니다.
스레드의 핵심 주제를 20자 이내의 명사형 구절로 요약하세요.
예: "결제 API 연동 오류", "iOS 빌드 배포 논의", "DB 마이그레이션 계획"
요약만 출력하고 다른 설명은 쓰지 마세요."""


class GeminiSummarizer:
    def __init__(self, api_key: str, rpm: int = 500):
        self.api_key = api_key
        self._min_interval = 60.0 / rpm  # seconds between requests
        self._last_call = 0.0

    def summarize(self, text: str, replies: list[str] | None = None) -> str:
        """스레드를 요약합니다. 실패 시 빈 문자열 반환."""
        content = text
        if replies:
            content += "\n" + "\n".join(replies[:10])  # 최대 10개 답글만

        self._rate_limit()
        try:
            resp = httpx.post(
                GEMINI_API_URL,
                params={"key": self.api_key},
                json={
                    "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                    "contents": [{"parts": [{"text": content[:2000]}]}],
                    "generationConfig": {"maxOutputTokens": 50, "temperature": 0.2},
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Gemini API 실패: %s", e)
            return ""

    def _rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()
