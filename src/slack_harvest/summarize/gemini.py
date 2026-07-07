"""Vertex AI Gemini(ADC 인증)를 이용한 스레드 요약.

사내 정책상 Gemini API키 폐지(2026-07) → 본인 Google 계정 ADC(Vertex AI) 인증으로 전환.
사전 조건: `gcloud auth application-default login`(@wemade.com, 사내망 IP) + quota project 설정.
⚠ Context-Aware Access: Vertex는 사내망 IP에서만 인증 통과(비사내망은 호출 차단).
"""

from __future__ import annotations

import logging
import time


SYSTEM_PROMPT = """당신은 Slack 스레드를 한국어로 요약하는 어시스턴트입니다.
스레드의 핵심 주제를 20자 이내의 명사형 구절로 요약하세요.
예: "결제 API 연동 오류", "iOS 빌드 배포 논의", "DB 마이그레이션 계획"
요약만 출력하고 다른 설명은 쓰지 마세요."""


class GeminiSummarizer:
    def __init__(
        self,
        project: str,
        location: str = "global",
        model: str = "gemini-2.5-flash-lite",
        rpm: int = 500,
    ):
        from google import genai

        self._client = genai.Client(vertexai=True, project=project, location=location)
        self._model = model
        self._min_interval = 60.0 / rpm  # seconds between requests
        self._last_call = 0.0

    def summarize(self, text: str, replies: list[str] | None = None) -> str:
        """스레드를 요약합니다. 실패 시 빈 문자열 반환."""
        from google.genai import types

        content = text
        if replies:
            content += "\n" + "\n".join(replies[:10])  # 최대 10개 답글만

        self._rate_limit()
        try:
            resp = self._client.models.generate_content(
                model=self._model,
                contents=content[:2000],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=50,
                    temperature=0.2,
                ),
            )
            return (resp.text or "").strip()
        except Exception as e:
            logging.getLogger(__name__).warning("Vertex Gemini 실패: %s", e)
            return ""

    def _rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()
