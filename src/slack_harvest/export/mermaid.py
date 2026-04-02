"""Mermaid 후처리 — 코드 블록 감지 + 스레드 시퀀스 다이어그램 변환."""

from __future__ import annotations

import re

# Mermaid 키워드 (코드 블록 내 감지용)
MERMAID_KEYWORDS = {
    "graph", "flowchart", "sequenceDiagram", "classDiagram",
    "stateDiagram", "erDiagram", "gantt", "pie", "gitgraph",
    "mindmap", "timeline", "journey",
}


class MermaidProcessor:
    def process_code_block(self, lang: str, code: str) -> tuple[str, str]:
        """코드 블록이 Mermaid인지 감지. Mermaid면 lang을 'mermaid'로 교체."""
        if lang.lower() == "mermaid":
            return "mermaid", code
        # lang이 없는 코드 블록에서 mermaid 키워드 감지
        if not lang:
            first_line = code.strip().split("\n")[0].strip()
            first_word = first_line.split()[0] if first_line else ""
            if first_word in MERMAID_KEYWORDS:
                return "mermaid", code
        return lang, code

    def thread_to_sequence(self, messages: list[dict]) -> str:
        """스레드 메시지 → Mermaid 시퀀스 다이어그램.

        조건: 참여자 2명 이상, 메시지 3개 이상.
        """
        participants: dict[str, str] = {}  # user_id → safe_name
        for msg in messages:
            uid = msg.get("user_id", "")
            name = msg.get("display_name") or msg.get("real_name") or uid
            if uid and uid not in participants:
                participants[uid] = _safe_name(name)

        if len(participants) < 2 or len(messages) < 3:
            return ""

        lines = ["", "```mermaid", "sequenceDiagram"]
        for safe in participants.values():
            lines.append(f"    participant {safe}")

        prev_uid = None
        for msg in messages:
            uid = msg.get("user_id", "")
            safe = participants.get(uid, "Unknown")
            summary = _truncate(msg.get("text", ""), 40)

            if prev_uid and prev_uid != uid:
                prev_safe = participants.get(prev_uid, "Unknown")
                lines.append(f"    {prev_safe}->>{safe}: {summary}")
            elif prev_uid == uid and prev_uid:
                lines.append(f"    Note right of {safe}: {summary}")
            prev_uid = uid

        lines.append("```")
        lines.append("")
        return "\n".join(lines)


def _safe_name(name: str) -> str:
    """Mermaid participant 이름으로 사용 가능하게 정리."""
    safe = re.sub(r"[^\w가-힣]", "_", name).strip("_")
    return safe or "Unknown"


def _truncate(text: str, max_len: int) -> str:
    text = text.replace("\n", " ").strip()
    return (text[:max_len] + "...") if len(text) > max_len else text
