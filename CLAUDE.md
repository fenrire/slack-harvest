# slack-harvest

슬랙 채널/스레드를 로컬에 아카이빙하는 CLI 도구.

## 아키텍처

```
Slack API → SQLite (Single Source of Truth) → MD export (QMD 검색용)
                                             → NexusEvent JSONL (work-nexus 연동)
                                             → 파일 다운로드 (첨부)
```

- **SQLite**: 메시지, 사용자, 채널, 파일 메타 저장. 증분 수집 상태 관리.
- **Markdown**: SQLite에서 생성하는 파생물. QMD 인덱싱 + 사람 열람용. 언제든 재생성 가능.
- **NexusEvent JSONL**: work-nexus/data/outbox/ 출력. NEXUS_OUTBOX_DIR 미설정 시 비활성.
- **단방향 흐름**: `fetch` → DB 저장 → `export` → MD + 파일 다운로드 (+ `--nexus` 시 JSONL)

## 요구사항

1. 특정 채널/스레드 단위로 수집 (CLI에서 지정)
2. MD 형식 저장 + 첨부 이미지/파일 로컬 다운로드
3. Mermaid 변환 가능한 콘텐츠 후처리 (코드 블록 감지, 스레드→시퀀스 다이어그램)
4. 로컬 문서 간 상대 경로 링크 동작 (@멘션→사용자 프로필, #채널→채널 인덱스, 첨부→로컬 파일)
5. 메시지 작성자 기본 정보 포함 (이름, 이메일, 직책)
6. SQLite + MD 하이브리드 저장
7. 배치 수집 시 멱등성 보장 (동일 메시지 중복 저장 없음, upsert 기반)

## 프로젝트 구조

```
src/
  slack_harvest/
    __init__.py
    cli.py              # Click CLI
    config.py           # 환경변수, 설정
    db/
      __init__.py
      schema.py         # SQLite 스키마
      repository.py     # DB CRUD
    slack/
      __init__.py
      client.py         # Slack API (httpx)
      models.py         # 데이터 모델 (dataclass)
      rate_limiter.py   # Rate limit 처리
    export/
      __init__.py
      markdown.py       # MD 변환
      linker.py         # 상대 경로 링크 생성
      mermaid.py        # Mermaid 변환
      downloader.py     # 파일 다운로드
      nexus.py          # NexusEvent JSONL (work-nexus 연동)
```

## 출력 디렉토리 구조

```
~/Documents/SlackArchive/
  {workspace}/                     # 워크스페이스별 분리 (auth.test 자동 감지)
    _db/
      slack-harvest.db
    _users/
      U01ABC123.md           # 사용자 프로필
    channels/
      general/
        _index.md            # 채널 메타정보
        2026-03-15.md        # 날짜별 대화
        threads/
          1711234567.890123.md
        files/
          image.png
```

## 기술 스택

- Python 3.10+
- httpx (Slack API 호출)
- click (CLI)
- rich (진행률 표시)
- python-dotenv (환경변수)
- SQLite (WAL 모드)

## 멱등성 설계

- 메시지: `(channel_id, ts)` 복합 PK → INSERT OR REPLACE
- 사용자: `id` PK → INSERT OR REPLACE
- 파일: `id` PK → INSERT OR REPLACE, `downloaded` 플래그로 다운로드 상태 추적
- 증분 수집: `channels.latest_ts` 기준으로 `oldest` 파라미터 설정
- 동일 배치 재실행 시 결과 동일 보장

## 크레덴셜

시크릿 로드: `Load-Secrets` 실행 (KeePassXC → WCM 동기화)
WCM 식별자: `config.yaml`의 `credentials` 섹션에 선언 (git 커밋됨, 시크릿 아님)

| 용도 | config.yaml 키 | KeePassXC 항목 | WCM Service / Key |
|------|----------------|----------------|-------------------|
| Slack User Token | `credentials.slack` | `slack/user-token` | `claude-code:slack` / `user-token` |
| Gemini API Key | `credentials.gemini` | `google/gemini-api-key` | `claude-code:google-ai-studio` / `gemini` |

## Slack API 토큰

- User Token (xoxp-) 사용
- 필요 스코프: `channels:history`, `channels:read`, `groups:history`, `groups:read`, `users:read`, `users:read.email`, `files:read`

## 컨벤션

- CLI 명령: `slack-harvest fetch`, `slack-harvest export`, `slack-harvest sync-users`, `slack-harvest list`
- 환경변수: `SLACK_USER_TOKEN`, `GEMINI_API_KEY`(선택), `HARVEST_OUTPUT_DIR`, `NEXUS_OUTBOX_DIR`(선택), `HARVEST_CHANNELS_FILE`(기본: `channels.txt`)
- 채널 설정: `channels.txt`에 수집 대상 채널을 명시적으로 관리. `fetch --all`은 이 파일 기반. `channels --save`로 기존 수집 채널을 파일에 저장
- 모든 텍스트 출력: 한국어
- 커밋 메시지: 한국어 가능
