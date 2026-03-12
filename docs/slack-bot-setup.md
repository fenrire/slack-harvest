# Slack Bot Token 만들기

## 1. Slack App 생성

1. https://api.slack.com/apps 접속
2. **"Create New App"** 클릭
3. **"From scratch"** 선택
4. App Name: `slack-harvest` (원하는 이름)
5. 워크스페이스 선택 → **Create App**

## 2. OAuth Scopes 추가

좌측 메뉴 **OAuth & Permissions** → 아래로 스크롤 → **Scopes** 섹션

**Bot Token Scopes**에 다음 6개 추가:

| Scope | 용도 |
|-------|------|
| `channels:history` | 공개 채널 메시지 읽기 |
| `channels:read` | 채널 목록 조회 |
| `users:read` | 사용자 정보 |
| `users:read.email` | 사용자 이메일 (users:read 자동 포함) |
| `reactions:read` | 리액션 정보 |
| `files:read` | 파일 메타데이터 |

> Private 채널도 필요하면 `groups:history`, `groups:read` 추가

## 3. 워크스페이스에 설치

같은 페이지 상단 **"Install to Workspace"** 클릭 → **Allow**

## 4. Bot Token 복사

설치 후 나타나는 **Bot User OAuth Token** (`xoxb-`로 시작) 복사

## 5. .env에 설정

```bash
cp .env.example .env
```

`.env` 파일 편집:
```
SLACK_BOT_TOKEN=xoxb-여기에-복사한-토큰
```

## 6. Bot을 채널에 초대

> **중요:** Bot은 초대된 채널만 접근할 수 있습니다.

각 채널에서:
- `/invite @slack-harvest` 입력하거나
- 채널 설정 → 통합 → 앱 추가

## 7. 테스트

```bash
harvest sync --full
```

## 참고: Scope 의존성

일부 scope는 다른 scope에 의존합니다. Slack이 "필수 추가 범위" 팝업을 표시하면 **"범위 추가"**를 눌러주세요.

- `users:read.email` → `users:read` 필요
- `groups:history` → `groups:read` 필요
