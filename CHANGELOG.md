# Changelog

## 2026-04-17

### config.yaml 도입: WCM 크레덴셜 식별자 관리
- `config.yaml` 추가 (git 커밋됨): WCM Service/key 식별자를 코드 밖에서 선언
- `config.py`: `.env` 환경변수 대신 `config.yaml`에서 keyring_service/key 읽음
- `.env`에서 `SLACK_CM_SERVICE` 등 CM 식별자 변수 제거 → config.yaml로 이관
- `pyproject.toml`에 `pyyaml>=6.0` 의존성 추가
- `.gitignore`에 `*.kdbx`, `.env.*` 추가 (시크릿 관리 가이드 섹션 7 준수)
- `CLAUDE.md`에 크레덴셜 표 추가 (가이드 섹션 3 준수)
- 팀원이 클론 후 WCM 구조를 별도 설정 없이 바로 파악 가능

## 2026-04-16

### 채널 이름 변경 추적 (`former_name`)
- `channels` 테이블에 `former_name TEXT DEFAULT ''` 컬럼 추가 (기존 DB 자동 마이그레이션)
- `upsert_channel`: 채널 이름 변경 감지 시 기존 이름을 `former_name`으로 보존
- `get_channel_by_name`: `name` 또는 `former_name` 양쪽 검색 → `channels.txt` 변경 없이 수집 이어짐
- fetch 시 구 이름으로 찾힌 경우 이름 변경 경고 출력
- `ly-gl-tech` → `ly-gl-main` 이름 변경 건 DB 수동 반영 + `channels.txt` 업데이트

## 2026-04-14 (세션 2)

### 채널 정리
- `aks-release`, `ai-champion-lounge`, `ai-champion-main`, `alert-*` (22개) channels.txt 주석 처리 확인 및 export 파일 삭제

### QMD MCP 서버 연동 수정
- Claude Code 플러그인 환경에서 QMD MCP 서버가 인덱스를 찾지 못하는 문제 원인 파악 (`enableProductionMode()` 미호출로 `getDefaultDbPath()` 실패)
- `marketplace.json`에 `INDEX_PATH` 환경변수 추가로 해결
- 업스트림 버그 PR 제출: https://github.com/tobi/qmd/pull/53

### QMD 컬렉션 context 설정
- wiki, confluence, slack, vault, gitbook 5개 컬렉션에 context 설명 추가 (검색 품질 향상)

### CLAUDE.md 지식 검색 순위 업데이트
- 1순위: `wiki` → `wiki` + `vault` (큐레이션된 경험 추가)

### 크레덴셜 식별자 설정파일 이관
- `config.py`에 하드코딩된 keyring service/username 식별자를 `.env`로 이관
- `SLACK_CM_SERVICE`, `SLACK_CM_USERNAME`, `GEMINI_CM_SERVICE`, `GEMINI_CM_USERNAME` 환경변수로 관리
- 전역 CLAUDE.md 크레덴셜 정책("식별자도 코드에 하드코딩하지 않는다") 준수

## 2026-04-14

### 크레덴셜 KeePassXC 이관 + WCM 배치 지원

- `.env`의 `SLACK_TOKEN`, `GEMINI_API_KEY` 평문 값 제거, CM 참조 주석으로 교체
- 시크릿은 KeePassXC vault(`slack/user-token`, `google/gemini-api-key`)로 이관
- PowerShell `Load-Secrets`에서 KeePassXC 읽기 후 Windows CM에도 자동 sync — 배치 무인 실행 가능
- `config.py`: `_from_cm()` 헬퍼 추가, Windows CM(keyring) 우선 → env var fallback 순서로 크레덴셜 로드

## 2026-04-08

### 수집 채널 설정파일 관리 (`channels.txt`)
- `channels.txt` 도입: 수집 대상 채널을 명시적으로 파일에서 관리. `fetch --all`이 워크스페이스 전체 채널을 수집하던 버그 수정
- `fetch --all` 실행 전 대상 채널 목록을 출력하고 확인 프롬프트 표시 (`-y`로 스킵 가능, 배치 스크립트용)
- `channels --save`: 기존 수집 이력 채널을 `channels.txt`에 저장하는 마이그레이션 커맨드
- `HARVEST_CHANNELS_FILE` 환경변수로 파일 경로 변경 가능 (기본: `./channels.txt`)
- ops.log 포맷 수정: `[fetch]` → `[slack-harvest/fetch]` (프로젝트 접두사 추가)

### 일일 배치 자동화 (Windows 작업 스케줄러)
- `slack-harvest fetch --all` 플래그 추가: DB에 등록된 모든 채널을 한 번에 수집
- `scripts/batch.bat`: fetch --all → summarize --llm → export 순서로 실행하는 배치 스크립트
- Windows 작업 스케줄러 `MyTasks\slack-harvest-batch` 매일 04:00 등록

### 배치 작업 로그 파일 (`HARVEST_LOG_FILE`)
- `HARVEST_LOG_FILE` 환경변수로 로그 파일 경로 지정 시 각 커맨드 완료 후 한 줄 append
- fetch: 채널 수 / 메시지 수 / 스레드 수 / API 호출 횟수 기록
- summarize --llm: 저장 건수 / 실패 건수 / 파라미터 기록
- export: Markdown 완료 / 다운로드 파일 수 기록
- 미설정 시 로그 비활성 (기존 동작 유지)

## 2026-04-07

### Gemini API 직접 요약 (`summarize --llm`)
- `GEMINI_API_KEY` 환경변수 지원 추가
- `slack-harvest summarize --llm` 옵션: Gemini 2.5 Flash로 직접 요약 (서브에이전트 우회 불필요)
- `--min-replies N` 옵션: 답글 N개 이상만 대상 (기본 5)
- rate limit 14 RPM 자동 조절, 실패 시 경고 후 계속 진행
- 무료 티어 기준 일 1,500건 처리 가능

### 스레드 자동 아카이브 분류 (export 단계)
- `threads/` 폴더를 `threads/` (active) + `threads/archive/` (stale)로 분리
- 마지막 활동 기준 14일 초과 스레드는 `threads/archive/`에 생성 (`ARCHIVE_DAYS = 14`)
- DB 변경 없이 export 로직만 수정 → 재생성 시 항상 최신 상태 반영
- 날짜별 파일의 스레드 링크도 archive/ 경로로 자동 연결
- 스레드 frontmatter에 `archived: true/false` 필드 추가

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
