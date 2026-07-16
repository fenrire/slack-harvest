# CONTEXT — slack-harvest

> 마지막 갱신: 2026-07-14

## 현재 상태
- **channels.txt 유실 재발 방지 완료(7/14)**: ① `fetch --all` 채널 목록 비면 exit≠0(+ops.log 실패 라인) ② channels.txt를 `SlackArchive/<workspace>/channels.txt`로 이동(DB와 함께 이전, git 미커밋) ③ fetch 콘솔에 메시지/스레드 수 노출 + batch가 HARVEST_LOG_FILE 자동 설정. 3건 검증 완료. weekly-report(`ce0bba66db33`)가 이미 데이터 복원·백필함(7/14 08:37까지)
- **LLM 요약 Vertex 이관 완료(7/7)**: `summarize --llm`이 google-genai + Vertex AI(ADC). project/location/model은 config.yaml `vertex` 섹션
- **Mac 일배치 진입점 `scripts/batch.sh`(7/7)**: `scheduled-tasks` launchd 러너가 호출. batch.bat의 Mac 미러
- DB 머지 완료(6/5): `위메이드 퍼블리싱`→`위메이드`. workspace 폴더명 고정(config.yaml)

## 다음 할 것
- [ ] **channels.txt 큐레이션 검토**: 7/13 복원본(59채널)은 DB sync_state(6/30 활성) 기반이라 **이전 수동 제외(큐레이션)와 다를 수 있음**. weekly-report도 검토 요청함. 이전에 의도적으로 뺀 채널이 되살아났는지 대조 필요 (위치: `~/Documents/SlackArchive/위메이드/channels.txt`)
- [ ] **사라진 채널 정리 검토**: `#게임사업본부x기술개발본부-pm논의방`(`C09T95XTWQY`) 영구 삭제 여부 `conversations.info`로 확인 후 영구면 channels.txt에서 제거(배치 경고 노이즈 제거). 코드 격리로 배치는 안전하니 급하진 않음

## 미결·주의사항
- **channels.txt 위치 = 아카이브 옆**(`SlackArchive/<workspace>/channels.txt`). repo cwd 아님. 장비 이전 시 SlackArchive 폴더째 복사하면 DB와 함께 따라옴. `HARVEST_CHANNELS_FILE`로 오버라이드 가능
- **Vertex는 사내망 IP에서만 인증 통과**(Context-Aware Access). Mac 일배치가 비사내망에서 돌면 summarize만 스킵(best-effort), 배치는 정상 종료. ADC 사전조건: `gcloud auth application-default login`(@wemade.com, 사내망) + quota project=`gemini-ent-483802`
- 현재 미요약 스레드 6868개는 전부 답글 5개 미만 → 기본 `--min-replies 5`에선 summarize 대상 0건(정상)
- export는 전체 재생성(멱등). qmd는 content-hash 기준이라 재인덱싱 안 일어남
