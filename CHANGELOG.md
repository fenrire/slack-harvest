# Changelog

## 2026-04-02

### LLM 기반 스레드 요약 캐시
- `thread_summaries` 테이블 추가: LLM 요약을 DB에 캐시하여 export 시 재사용
- `slack-harvest summarize` CLI 명령 추가: `--export`로 미요약 스레드 JSON 출력, `--import`로 요약 결과 저장
- ANTHROPIC_API_KEY 없이 Claude Code 세션에서 요약 생성 → JSON import 워크플로우
- export 시 캐시된 LLM 요약 우선 사용, 없으면 기존 휴리스틱(`_extract_topic`) 폴백
- 스레드 파일명/제목 모두 캐시된 요약 반영
- 스레드 파일명 매핑을 날짜별 MD 생성 전에 구축 (스레드 링크 정확도 개선)
- export 시 threads/ 디렉토리 기존 파일 정리 후 재생성 (요약 변경 시 중복 파일 방지)

### 스레드 MD 개선 + 누락 사용자 보충
- 스레드 파일명: `{최종덧글날짜}_{주제요약}_{thread_ts}.md` — 날짜 정렬 + 맥락 파악 + 고유성
- 주제 추출 로직: 인사말/호칭 자동 건너뛰기, **볼드** 텍스트 우선 추출, 실질 업무 내용 20자 요약
- 스레드 파일 내 날짜별 `## YYYY-MM-DD` 구분선 추가 (여러 날에 걸친 스레드 탐색 용이)
- 스레드 제목에 주제 요약 표시 + 시작 시각 인용
- fetch 후 누락 사용자 자동 보충: 메시지에 등장하지만 `users.list`에 없는 외부/게스트 사용자를 `users.info`로 개별 조회

### 수정 메시지 감지 (--refresh-days)
- `fetch --refresh-days N` 옵션 추가: 최근 N일 메시지를 재수집하여 수정된 메시지를 자동 감지·업데이트
- 증분 수집(`latest_ts`)만으로는 원본 ts가 변하지 않는 수정 메시지를 놓치는 문제 해결
- upsert 전에 `edited_ts` 비교로 실제 수정된 건수를 리포트
- 예: `slack-harvest fetch -c general -r 7` → 최근 7일 메시지 중 수정된 것 감지

### v1.0.0 — 완전 재설계
- 기존 Slack→Notion 업로더를 폐기하고, 로컬 아카이빙 CLI 도구로 전면 재설계 (Notion 코드 전부 삭제)
- **아키텍처**: Slack API → SQLite (SSOT) → MD export + NexusEvent JSONL + 파일 다운로드
- **SQLite**: WAL 모드, 6 테이블 (channels, users, messages, files, sync_state, schema_info). 멱등성 보장 (INSERT OR REPLACE)
- **Slack API 클라이언트**: httpx 기반, 커서 페이지네이션, Rate Limit 자동 대기 (Tier 3, Retry-After 존중)
- **MD Export**: 날짜별/채널별 파일 생성, YAML frontmatter, 사용자 프로필 MD, 스레드 별도 파일
- **링크 체계**: @멘션→_users/ 프로필, #채널→_index.md, 첨부→files/ 상대 경로 링크
- **파일 다운로드**: Bearer 인증으로 url_private 다운로드, downloaded 플래그로 멱등성 보장
- **NexusEvent JSONL**: work-nexus 연동용 변환. Jira 티켓, Confluence URL, @멘션, 스레드 reply_to 자동 감지
- **Mermaid 후처리**: 코드 블록 내 mermaid 키워드 감지, 스레드→시퀀스 다이어그램 변환
- **워크스페이스 분리**: auth.test로 자동 감지, ~/Documents/SlackArchive/{workspace}/ 경로
- **CLI**: Click 기반 — fetch, export, sync-users, list 명령

## 2026-03-12

### Slack 전환 (Pivot)
- 카카오워크 → Slack 으로 데이터 소스 전환 (카카오워크 API 제한으로 실용성 부족)
- 프로젝트명 `slack-harvest` 로 변경, Slack User Token(xoxp-) 기반 API 클라이언트 구현
- 노션 데이터베이스 업로더 유지 (채널/날짜별 페이지 자동 생성)

### 클립보드 붙여넣기 기능
- copy+paste 워크플로우를 위한 paste 명령 추가

## 2026-03-11

### 초기 구현
- 카카오워크 메시지 → 노션 정리 도구 초기 버전
