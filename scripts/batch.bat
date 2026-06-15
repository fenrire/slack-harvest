@echo off
:: slack-harvest 일일 배치: fetch --all -> summarize --llm(best-effort) -> export
:: 중앙 오케스트레이터(daily-batch)가 호출. 단독 실행도 가능.
:: 종료코드: fetch 또는 export 가 실패하면 非0 반환 (daily-batch 가 실패로 판정).
::           summarize 는 Gemini 키 의존 부가 작업이라 실패해도 계속 진행(캐시성).

setlocal
set PYTHONUTF8=1
cd /d "%~dp0.."

echo [%DATE% %TIME%] batch start

:: uv 경유 실행 (slack-harvest 는 venv 안에만 있고 PATH 에 없음)
uv run slack-harvest fetch --all -y || goto :fail
uv run slack-harvest summarize --llm
uv run slack-harvest export || goto :fail

echo [%DATE% %TIME%] batch done
endlocal
exit /b 0

:fail
set RC=%ERRORLEVEL%
echo [%DATE% %TIME%] batch FAILED (exit=%RC%)
endlocal
exit /b 1
