# Changelog

## 2026-04-06

### Windows 파일명 제어문자 버그 수정
- `_thread_slug()` / `_make_slug()`: Slack 메시지에 포함된 제어문자(`\x00-\x1f`, `\x7f`)를 파일명 생성 전에 제거
- Windows에서 `\x08`(backspace) 등 제어문자가 파일명에 포함되면 `OSError: [Errno 22] Invalid argument` 발생하던 문제 해결

### 대규모 배치 수집 (52개 채널, --since 2026-03-01)
- ly-*, nc-*, fb-* 계열 52개 채널 3월 이후 메시지 일괄 수집 완료
- SQLite WAL 모드 활용: fetch 실행 중 export 병렬 실행 가능 확인

### Haiku 기반 스레드 요약 9,443개 생성
- `reply_count >= 5` 필터링 (9,648개) → 49배치(배치당 200개)로 분할
- Claude Haiku subagent 49개 병렬 실행으로 9,443개 요약 생성·import
- 요약 품질: 15-25자 한국어, 인사말/멘션 제거, 파일명 안전 형식

## 2026-04-02

### LLM 기반 스레드 요약 캐시
- `thread_summaries` 테이블 추가: LLM 요약을 DB에 캐시하여 export 시 재사용
- `slack-harvest summarize` CLI 명령 추가: `--export`로 미요약 스레드 JSON 출력, `--import`로 요약 결과 저장
- ANTHROPIC_API_KEY 없이 Claude Code 세션에서 요약 생성 → JSON import 워크플로우
- export 시 캐시된 LLM 요약 우선 사용, 없으면 기존 휴리스틱(`_extract_topic`) 폴백
- 스레드 파일명/제목 모두 캐시된 요약 반영
- 스레드 파일명 매핑을 날짜별 MD 생성 전에 구축 (스레드 링크 정확도 개선)
- export 시 threads/ 디렉토리 기존 파일 정리 후 재생성 (요약 변경 시 중복 파일 방지)

### Slack→마크다운 변환 개선
- Slack 인라인 코드 블록(`` ```text``` ``)을 fenced code block으로 변환 (이후 내용이 코드 블록에 갇히는 문제 해결)
- 메시지 본문 줄바꿈 보장: 각 줄 끝에 trailing 2 spaces 추가 (마크다운 렌더러가 줄바꿈을 무시하는 문제 해결)
- 알파벳/로마숫자 리스트(`a.`, `i.` 등) → `- a.` 형태로 변환하여 마크다운 들여쓰기 구조 보존
- HTML 엔티티 디코딩: `&gt;` → `>`, `&lt;` → `<`, `&amp;` → `&` (Slack API가 인코딩한 것을 복원)
- `<!subteam^ID>` → `@그룹`, `<!here>` → `@here` 등 특수 멘션 변환

### Slack 원문 링크 (permalink)
- 각 메시지에 `[원문]` 링크 추가: 클릭하면 Slack 앱/웹에서 해당 메시지로 바로 이동
- 스레드 답글은 `?thread_ts=&cid=` 파라미터로 정확한 스레드 위치 연결
- `workspace_meta` 테이블 추가: `auth.test`의 workspace URL을 DB에 저장하여 오프라인 export 시 활용

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
