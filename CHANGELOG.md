# CHANGELOG

## 2026-03-12

### feat: User Token 지원 추가

**배경:** Bot Token(xoxb-)은 채널마다 `/invite`로 수동 초대해야 접근 가능. 대규모 워크스페이스에서 비현실적이며, DM·Private 채널은 원천적으로 불가.

- `SLACK_USER_TOKEN(xoxp-)` 환경 변수 지원 추가
- User Token 있으면 우선 사용, 없으면 Bot Token fallback (`active_token` property)
- `--include-private`: Private 채널 자동 포함 (봇 초대 불필요)
- `--include-dm`: DM(`im`) 및 그룹 DM(`mpim`) 동기화 지원
- DM 채널 name 자동 합성 (`DM-{user_id}`)

### feat: 초기 구현 (Slack 워크스페이스 아카이빙 도구)

**배경:** Slack 채널에 흩어진 정보를 주제별로 취합·분석·to-do 정리 등 다양한 LLM 분석에 활용하기 위해 로컬 아카이브 시스템 필요. 분석 요구사항이 계속 달라질 수 있으므로 유연한 2-레이어 구조 채택.

- SQLite(Layer 1): 전체 Slack 데이터를 구조적으로 저장 (raw_json 포함)
- Markdown/QMD(Layer 2): 월별 파일로 내보내 시맨틱 검색 인덱싱
- CLI 명령어: `harvest sync`, `harvest export`, `harvest status`, `harvest search`
- 증분 동기화: `sync_state` 테이블로 마지막 ts 기록, 신규 메시지만 수집
- 적응형 레이트 리밋: `AdaptiveRateLimiter` + SDK 내장 재시도

### docs: 아키텍처 결정 기록(ADR) 및 설정 가이드 추가

**배경:** 아키텍처 선택 이유와 Slack Bot 설정 방법을 팀 내 공유 및 향후 참조용으로 문서화.

- `docs/architecture-decisions.md`: 8개 ADR (2-레이어 구조, SQLite 선택, raw_json 보존 등)
- `docs/slack-bot-setup.md`: Slack App 생성 → Scope 추가 → Token 발급 단계별 가이드
- `docs/agent-browser-integration.md`: Bot Token 한계 및 agent-browser 연동 방향 검토
