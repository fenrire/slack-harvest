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
- **일배치 일원화 결정(6/15)**: 별도 레포 `daily-batch`(manifest 중앙 오케스트레이터) 신설. slack-harvest `batch.bat`을 `uv run` 경유 + 종료코드 전파로 보강해 편입 준비 완료

## 다음 할 것
- [ ] **daily-batch 스케줄 등록(register-task.ps1) — 보류 중**. 사용자 결정 "진입점 점검 후 등록". slack은 점검·수정 완료. gmail(시스템 python 의존)/confluence(종료코드 미전파)는 각 프로젝트 CLAUDE.md에 점검 TODO 위임함 → 그 점검 완료 후 등록
- [ ] 등록과 **동시에** 기존 `\ConfluenceHarvest\DailySync`(07:00) 제거 — daily-batch가 흡수. 지금 제거하면 confluence 자동 sync 공백 발생하므로 등록과 세트로

## 미결·주의사항
- **현재 어떤 일배치도 자동 안 됨**: daily-batch 미등록, slack/gmail 수동, confluence는 DailySync(07:00)만 도는데 최근 실행 0xC000013A 비정상 종료. 등록 전까지 수집은 수동(`uv run slack-harvest fetch --all -y`)
- export는 날짜 증분이 아닌 **전체 재생성(멱등)**. 모든 MD mtime 갱신되지만, **qmd는 content-hash 기준**이라 재인덱싱/재임베딩 안 일어남(6/15 검증: slack `0 updated`)
- `export_all`은 기본 DB 전체 기준. cli에서 channels.txt 전달 시에만 필터됨 — `--channel` 개별 export는 무관
