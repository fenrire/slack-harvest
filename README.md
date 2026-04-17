# slack-harvest

Slack 채널/스레드를 SQLite + Markdown으로 로컬에 아카이빙하는 CLI 도구.

> 아키텍처 상세: [docs/architecture.md](docs/architecture.md)

## 설치

```bash
pip install -e .
```

Python 3.10+ 필요.

## 크레덴셜 설정

### Slack User Token 발급

1. [Slack API](https://api.slack.com/apps) → 앱 생성
2. **OAuth & Permissions** → User Token Scopes 추가:
   - `channels:history`, `channels:read`
   - `groups:history`, `groups:read`
   - `users:read`, `users:read.email`
   - `files:read`
3. 워크스페이스에 앱 설치 → **User OAuth Token** (`xoxp-...`) 복사

### 환경변수 설정

```bash
cp .env.example .env
```

`.env`에서 필요한 항목 주석 해제 후 값 입력:

```env
SLACK_USER_TOKEN=xoxp-...
```

> Windows에서 KeePassXC + WCM을 쓰는 경우 `config.yaml` 참고. 환경변수 없이 자동 주입됩니다.

## 빠른 시작

```bash
# 특정 채널 수집
slack-harvest fetch -c general

# 수집 대상 채널 목록 확인
slack-harvest list

# Markdown으로 내보내기
slack-harvest export -c general

# 사용자 정보 동기화
slack-harvest sync-users
```

## 채널 일괄 수집 (`fetch --all`)

수집 대상 채널을 `channels.txt`에 관리합니다:

```
# channels.txt
general
dev-backend
# alert-ops  ← 주석으로 비활성화
```

```bash
# channels.txt 기반 일괄 수집 (확인 프롬프트)
slack-harvest fetch --all

# 확인 생략 (배치 스크립트용)
slack-harvest fetch --all -y

# 기존 DB에서 채널 목록 추출
slack-harvest channels --save
```

## 출력 구조

```
~/Documents/SlackArchive/
  {workspace}/
    _db/slack-harvest.db
    _users/U01ABC.md
    channels/
      general/
        _index.md
        2026-03-15.md
        threads/1711234567.890.md
        files/image.png
```

## 선택 기능

| 환경변수 | 기능 |
|----------|------|
| `GOOGLE_GEMINI_API_KEY` | 스레드 자동 요약 (`--llm`) |
| `NEXUS_OUTBOX_DIR` | work-nexus 연동 JSONL 출력 |
| `HARVEST_LOG_FILE` | 배치 작업 중앙 로그 |
| `HARVEST_OUTPUT_DIR` | 출력 디렉토리 변경 (기본: `~/Documents/SlackArchive`) |
