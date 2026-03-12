# agent-browser 연동 검토

> 작성일: 2026-03-12
> 참고 레포: https://github.com/vercel-labs/agent-browser (로컬: `~/Documents/agent-browser`)

---

## 현재 구조의 한계

현재 Bot Token (xoxb-) 기반 구조의 제약:

| 문제 | 원인 |
|------|------|
| 채널마다 `/invite @slack-harvest` 수동 초대 필요 | 봇은 초대받은 채널만 접근 가능 |
| DM / 그룹 메시지 수집 불가 | 봇 토큰(xoxb-)의 근본적 한계 |
| `url_private_download` 파일 다운로드 불가 | 인증된 세션 없이는 403 |
| Private 채널 접근 제한 | 명시적 초대 필요 |

---

## 개선 방향 (우선순위 순)

### Option A. User Token (xoxp-) 전환 ✅ 권장

**코드 변경 최소, 즉시 효과 최대**

- 내 계정 OAuth로 xoxp- 토큰 발급
- 기존 `WebClient` 코드 그대로 유지 (토큰만 교체)
- 접근 가능 범위: 내가 멤버인 **모든 채널 + DM + Private 채널** 자동 포함
- 봇 초대 불필요

필요 스코프 추가:
```
channels:history, channels:read        # 현재와 동일
groups:history, groups:read            # Private 채널
im:history, im:read                    # DM
mpim:history, mpim:read                # 그룹 DM
files:read                             # 파일 메타
```

발급 방법: https://api.slack.com/apps → OAuth & Permissions → User Token Scopes

---

### Option B. agent-browser로 파일 다운로드 보완

현재 `models.py`에 `url_private_download` URL은 저장되지만 실제 다운로드는 미구현.

agent-browser 브라우저 세션으로 처리:

```bash
# Slack 로그인 세션 저장 (최초 1회)
agent-browser --session slack open https://slack.com
# 로그인 완료 후 세션 자동 저장

# 이후 파일 다운로드
agent-browser --session slack navigate <url_private_download>
agent-browser --session slack download <url_private_download> --path ./files/
```

`harvester.py`의 파일 수집 이후 단계에 다운로드 로직 추가 가능.

---

### Option C. agent-browser 네트워크 인터셉트로 DM 수집

Bot Token으로는 절대 접근 불가한 DM을, Slack 웹앱 내부 API 응답을 가로채는 방식으로 수집.

```bash
agent-browser --session slack open https://app.slack.com
agent-browser network intercept "*/api/conversations.history*" --capture
agent-browser navigate "/messages/DM_CHANNEL_ID"
# → Slack 웹앱이 호출하는 conversations.history 응답 캡처
```

기존 데이터 모델(Message, Channel 등)과 동일한 구조로 수신 가능.

⚠️ 주의: Slack 웹 인터페이스 변경 시 깨질 수 있음. Option A로 해결 가능한 경우 A 우선.

---

## 구현 로드맵 (제안)

```
1단계: User Token 전환
   - xoxp- 토큰 발급
   - .env.example에 SLACK_USER_TOKEN 추가
   - harvester.py 토큰 분기 처리 (봇/유저 선택)
   - DM 채널 타입(im, mpim) sync 지원 추가

2단계: 파일 다운로드 구현
   - agent-browser 세션으로 url_private_download 다운로드
   - 로컬 파일 경로를 DB에 저장 (files 테이블 확장)

3단계: (선택) DM 전용 수집기
   - agent-browser 인터셉트 방식으로 DM 전용 harvester 구현
   - 기존 harvester.py와 동일한 DB 스키마에 저장
```

---

## 관련 파일

- `src/slack_harvest/harvester.py` — API 호출 + sync 로직
- `src/slack_harvest/models.py` — 데이터 클래스 (File 모델 확장 필요)
- `src/slack_harvest/db.py` — SQLite 스키마
- `~/Documents/agent-browser/` — agent-browser 로컬 설치
