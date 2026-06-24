# CONTEXT — slack-harvest

> 마지막 갱신: 2026-06-24

## 현재 상태
- DB 머지 완료(6/5): `위메이드 퍼블리싱` → `위메이드` 통합. 운영 DB `integrity_check ok`
- workspace 폴더명 고정: `config.yaml: workspace=위메이드`
- export 기준을 channels.txt로 제한 (제외 채널 export 부활 방지)
- **일배치는 `scheduled-tasks` 레포(구 daily-batch)가 중앙 관리** — 6/16부터 매일 자동 실행. slack/gmail/confluence job 등록됨
- **6/24 배치 연속 실패 수정**: slack 배치가 6/22~6/24 3일 연속 `exit=1` 실패 → 원인은 `#게임사업본부x기술개발본부-pm논의방`(`C09T95XTWQY`) 삭제(`channel_not_found`)가 fetch 전체를 죽인 것. fetch 루프를 채널 단위로 격리(한 채널 실패는 건너뛰고 계속). 재실행 exit 0 검증 완료

## 다음 할 것
- [ ] **사라진 채널 정리 검토**: `#게임사업본부x기술개발본부-pm논의방`(`C09T95XTWQY`)가 영구 삭제인지 일시 문제인지 `conversations.info`로 확인 후, 영구면 channels.txt에서 제거(매 배치 경고 노이즈 제거). 코드 격리로 배치는 이미 안전하니 급하진 않음

## 미결·주의사항
- export는 날짜 증분이 아닌 **전체 재생성(멱등)**. 모든 MD mtime 갱신되지만 **qmd는 content-hash 기준**이라 재인덱싱/재임베딩 안 일어남(6/15 검증)
- `export_all`은 기본 DB 전체 기준. cli에서 channels.txt 전달 시에만 필터됨 — `--channel` 개별 export는 무관
- 무인 배치 전제: 토큰이 WCM에 있어야 함 → 포맷 후 `Load-Secrets` 선행. (`keyring`은 의존성에 포함됨, 6/15 수정)
