@echo off
:: slack-harvest 일일 배치: fetch --all → summarize --llm → export
:: 작업 스케줄러에서 실행됨 (매일 04:00)

setlocal
set PYTHONUTF8=1
cd /d "C:\Users\Jungholee_pc\Documents\Projects\slack-harvest"

echo [%DATE% %TIME%] 배치 시작
slack-harvest fetch --all -y
slack-harvest summarize --llm
slack-harvest export

echo [%DATE% %TIME%] 배치 완료
endlocal
