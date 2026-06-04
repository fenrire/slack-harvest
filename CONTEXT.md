# CONTEXT — slack-harvest 첫 수집 윈도우 + DB 머지
> 마지막 갱신: 2026-06-04

## 현재 상태
- `--initial-days` 옵션 구현 완료 (기본 90일). `latest_ts=NULL`인 첫 수집 채널에 자동 적용
- `issue-cloud5` 채널 추가 수집+export 완료
- `위메이드` / `위메이드 퍼블리싱` 두 폴더 분석 완료 — workspace 이름 변경으로 인한 분리. 머지 대기 중

## 다음 할 것
- [ ] DB 머지: `위메이드 퍼블리싱` → `위메이드`로 통합
  - 29개 고유 채널 (messages, files, channels) 이관
  - 810개 고유 thread_summaries 이관
  - 56개 겹치는 채널은 위메이드가 상위집합 — 별도 처리 불필요
  - export 파일(channels/ 폴더)도 이관 필요
  - 머지 후 `위메이드 퍼블리싱` 폴더 삭제 (또는 백업)
- [ ] 변경사항 커밋 (`--initial-days`, `channels.txt` issue-cloud5 추가)

## 미결·주의사항
- `위메이드/slack-harvest.db` (루트에 0바이트 빈 파일) 존재 — 삭제 필요
- `위메이드 퍼블리싱`의 workspace_url은 `wm-publ-dept.slack.com`, `위메이드`는 `wemade.slack.com` — 워크스페이스 이름 변경 시점에 auth.test 반환값이 바뀌어 폴더 분리 발생. 향후 재발 방지를 위해 workspace 고정 로직 검토 필요
- 배치 스케줄이 `schtasks`에서 확인 안 됨 — 스크린샷에 보이는 실행은 다른 방식(수동 실행 또는 다른 스케줄러)일 수 있음
- 퍼블리싱 DB(923MB)의 29개 고유 채널 중 `alert-ly-gl-game`만 127K 메시지 — 대부분 alert 채널이므로 channels.txt에서 주석처리된 상태인지 확인 필요
