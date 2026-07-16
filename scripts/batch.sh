#!/usr/bin/env bash
# slack-harvest 일일 배치: fetch --all -> summarize --llm(best-effort) -> export
# 중앙 오케스트레이터(scheduled-tasks)가 호출. 단독 실행도 가능. batch.bat 의 Mac 미러.
# 종료코드: fetch 또는 export 가 실패하면 非0 반환 (중앙 러너가 실패로 판정).
#           summarize 는 Vertex/ADC 의존 부가 작업이라 실패해도 계속 진행(캐시성).
# 시크릿: Slack 토큰은 keyring(Mac=Keychain 백엔드)에서 자가 조달, LLM 요약은 ADC.

export PYTHONUTF8=1
# 수집 통계(메시지 N건)를 항상 중앙 ops.log에 남긴다 — 0건 수집이 눈에 띄도록.
export HARVEST_LOG_FILE="${HARVEST_LOG_FILE:-$HOME/Documents/ops.log}"
cd "$(dirname "$0")/.." || exit 1

ts() { date '+%Y-%m-%d %H:%M:%S'; }

echo "[$(ts)] batch start"

# uv 경유 실행 (slack-harvest 는 venv 안에만 있고 PATH 에 없음)
uv run slack-harvest fetch --all -y || { echo "[$(ts)] batch FAILED (fetch)"; exit 1; }
uv run slack-harvest summarize --llm   # best-effort: 실패해도 계속
uv run slack-harvest export || { echo "[$(ts)] batch FAILED (export)"; exit 1; }

echo "[$(ts)] batch done"
exit 0
