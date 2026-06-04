# CONTEXT — slack-harvest 워크스페이스 머지 후속

> 마지막 갱신: 2026-06-05

## 현재 상태
- DB 머지 완료: `위메이드 퍼블리싱` → `위메이드` 통합 (합집합 머지, messages 471,910 / channels 758 / integrity_check ok)
- export 기준을 channels.txt로 제한하는 수정 완료 (제외 채널 export 부활 방지)
- 소스 폴더는 `_merged-위메이드퍼블리싱-20260605/`로 리네임, 내부 `_db`→`_db.merged`로 워크스페이스 자동 인식에서 제외
- 머지 백업 보존: `위메이드/_db/slack-harvest.db.bak-20260605` (627MB)

## 다음 할 것
- [ ] QMD slack 컬렉션 인덱스 갱신 (폴더 리네임 반영 + `_merged` 제외 확인) — 진행 중
- [ ] 다음 04:00 배치 정상 동작 확인 후 백업(`*.bak-20260605`)과 `_merged-...` 폴더 삭제
- [ ] (검토) workspace 고정 로직 — auth.test team명에 의존하면 이름 변경 시 또 폴더 분리됨. config로 workspace 고정 옵션 검토

## 미결·주의사항
- `export_all`은 기본 DB 전체 기준. cli에서 channels.txt 전달 시에만 필터됨 — `--channel` 개별 export는 무관
- 배치 스케줄이 `schtasks`에서 확인 안 됨 — 실제 실행 방식(수동/다른 스케줄러) 미확정. batch.bat 주석은 "매일 04:00"
- `_merged-...` 폴더에 과거 export(구 `wm-publ-dept` permalink) 잔존 — QMD 인덱싱 대상에서 제외할 것
