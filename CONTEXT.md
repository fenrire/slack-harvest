# CONTEXT — slack-harvest 배치 정상화 후속

> 마지막 갱신: 2026-06-15

## 현재 상태
- DB 머지 완료(6/5): `위메이드 퍼블리싱` → `위메이드` 통합. 운영 DB `integrity_check ok` / messages 479,458 / channels 765
- workspace 폴더명 고정: `config.yaml: workspace=위메이드` (이름 변경 시 폴더 분리 재발 방지)
- export 기준을 channels.txt로 제한 (제외 채널 export 부활 방지)
- **6/15 수동 수집+export+QMD 반영 완료**:
  - keyring 의존성 누락 수정(커밋 e4fbf5e) → fetch(신규 241건/답글 1,710건/API 262회) → export(59채널 재생성, 첨부 24개)
  - PC 포맷(6/9) 유실분 복구: `channels.txt`(59채널, gitignore), `uv.lock`
  - QMD: slack 30,784파일, `qmd embed` 완료 → Vectors 519,530 / Pending 0, 시맨틱 검색 동작 확인
- 머지 백업/`_merged-...` 소스 폴더 **삭제 완료** (운영 DB 무결성 확인 후)

## 다음 할 것
- [ ] **다음 자동 배치(04:00) 무인 실행 확인** — keyring 수정 후 첫 자동 실행이 토큰 로드 성공하는지. 실패 시 batch.bat의 PYTHONUTF8 외 토큰 경로(WCM) 점검

## 미결·주의사항
- 배치 스케줄이 `schtasks`에서 확인 안 됨 — 실제 실행 방식(수동/다른 스케줄러) 미확정. batch.bat 주석은 "매일 04:00". keyring 버그로 PC 포맷(6/9)~6/15 줄곧 실패했을 것
- export는 날짜 증분이 아닌 **전체 재생성(멱등)**. 모든 MD mtime 갱신되지만, **qmd는 content-hash 기준**이라 재인덱싱/재임베딩 안 일어남(6/15 검증: slack `0 updated`)
- `export_all`은 기본 DB 전체 기준. cli에서 channels.txt 전달 시에만 필터됨 — `--channel` 개별 export는 무관
