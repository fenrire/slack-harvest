# CONTEXT — slack-harvest 워크스페이스 머지 후속

> 마지막 갱신: 2026-06-15

## 현재 상태
- DB 머지 완료: `위메이드 퍼블리싱` → `위메이드` 통합 (합집합 머지, messages 471,910 / channels 758 / integrity_check ok)
- export 기준을 channels.txt로 제한하는 수정 완료 (제외 채널 export 부활 방지)
- 소스 폴더는 `~/Documents/_merged-위메이드퍼블리싱-20260605/`로 이동(SlackArchive 밖, QMD 인덱싱 제외), 내부 `_db`→`_db.merged`
- 머지 백업 보존: `위메이드/_db/slack-harvest.db.bak-20260605` (598MB)
- QMD slack 컬렉션 갱신 완료: 60,609 → 28,157 문서 (중복 134채널·구 permalink 31,569개 제거)
- workspace 폴더명 고정 완료: `config.yaml: workspace=위메이드` (이름 변경 시 폴더 분리 재발 방지)
- **6/15 수동 수집+export 완료**: keyring 의존성 누락 수정 후 fetch(신규 241건/스레드답글 1,710건/API 262회)→export(채널 59개 재생성, 첨부 24개 다운로드) 정상 동작 확인. PC 포맷(6/9) 유실분 복구: `channels.txt`(59채널), `uv.lock`

## 다음 할 것
- [ ] QMD 신규 export 반영 + `qmd embed`(시맨틱 검색, 기존 백로그 2.9만 건 포함)
- [ ] 백업(`*.bak-20260605`)과 `~/Documents/_merged-...` 폴더 삭제 (수동 수집+export로 파이프라인 정상 확인됨 — 삭제 가능 상태)

## 미결·주의사항
- **배치(04:00)는 keyring 버그로 PC 포맷(6/9) 이후 줄곧 실패했을 것** — 토큰 로드 불가. 6/15 수정으로 해소. 다음 자동 배치 실제 동작 확인 필요
- 배치 스케줄이 `schtasks`에서 확인 안 됨 — 실제 실행 방식(수동/다른 스케줄러) 미확정. batch.bat 주석은 "매일 04:00"
- `export_all`은 기본 DB 전체 기준. cli에서 channels.txt 전달 시에만 필터됨 — `--channel` 개별 export는 무관
- export는 날짜 증분이 아닌 전체 재생성(멱등). 모든 MD mtime 갱신 → QMD 전체 재인덱싱 유발 가능(내용 동일, 시간만 소요)
- `_merged-...` 폴더에 과거 export(구 `wm-publ-dept` permalink) 잔존 — QMD 인덱싱 대상에서 제외할 것
