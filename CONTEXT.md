# CONTEXT — slack-harvest

> 마지막 갱신: 2026-07-07

## 현재 상태
- **LLM 요약 Vertex 이관 완료(7/7)**: `summarize --llm`이 google-genai + Vertex AI(ADC 인증) 사용. project/location/model은 `config.yaml`의 `vertex` 섹션. 사내망에서 실호출 검증 완료(`gemini-2.5-flash-lite` global 가용)
- **Mac 일배치 진입점 `scripts/batch.sh` 추가(7/7)**: `scheduled-tasks` launchd 러너가 호출. `batch.bat`의 Mac 미러(fetch→summarize best-effort→export, 종료코드 정직성)
- DB 머지 완료(6/5): `위메이드 퍼블리싱` → `위메이드` 통합. workspace 폴더명 고정(`config.yaml: workspace=위메이드`)
- **일배치는 `scheduled-tasks` 레포가 중앙 관리** (매일 자동 실행). Mac 전환으로 진입점이 `.bat`→`.sh`

## 다음 할 것
- [ ] **사라진 채널 정리 검토**: `#게임사업본부x기술개발본부-pm논의방`(`C09T95XTWQY`)가 영구 삭제인지 `conversations.info`로 확인 후, 영구면 channels.txt에서 제거(매 배치 경고 노이즈 제거). 코드 격리로 배치는 이미 안전하니 급하진 않음

## 미결·주의사항
- **Vertex는 사내망 IP에서만 인증 통과**(Context-Aware Access). Mac 일배치가 비사내망(집/테더링)에서 돌면 `summarize --llm`은 실패하지만 best-effort라 배치는 정상 종료(요약만 스킵). ADC 사전조건: `gcloud auth application-default login`(@wemade.com, 사내망) + quota project=`gemini-ent-483802`
- 현재 미요약 스레드 6868개는 전부 답글 5개 미만 → 기본 `--min-replies 5`에선 summarize 대상 0건(정상)
- export는 날짜 증분이 아닌 **전체 재생성(멱등)**. MD mtime 갱신되나 qmd는 content-hash 기준이라 재인덱싱 안 일어남(6/15 검증)
- 무인 배치 전제: Slack 토큰이 keyring(Mac=Keychain)에 있어야 함
