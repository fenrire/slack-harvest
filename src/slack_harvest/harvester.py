"""Slack API 수집 모듈"""

from __future__ import annotations

import logging
import time
from typing import Generator, Optional

from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler

from .db import SlackHarvestDB
from .models import (
    SlackChannel,
    SlackFile,
    SlackMessage,
    SlackReaction,
    SlackUser,
)

logger = logging.getLogger(__name__)


class AdaptiveRateLimiter:
    """Slack API 레이트 리밋을 사전에 방지하는 적응형 속도 조절기"""

    def __init__(self, initial_delay: float = 1.3):
        self.delay = initial_delay
        self.min_delay = 1.2
        self.max_delay = 30.0
        self._last_request_time = 0.0
        self._consecutive_ok = 0

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request_time = time.monotonic()

    def on_rate_limited(self) -> None:
        self.delay = min(self.delay * 2, self.max_delay)
        self._consecutive_ok = 0
        logger.warning("Rate limited! 딜레이를 %.1f초로 증가", self.delay)

    def on_success(self) -> None:
        self._consecutive_ok += 1
        if self._consecutive_ok > 20:
            self.delay = max(self.delay * 0.9, self.min_delay)


class SlackHarvester:
    """Slack 워크스페이스 데이터를 로컬 DB에 수집"""

    def __init__(self, token: str, db: SlackHarvestDB):
        self.client = WebClient(token=token)
        self.client.retry_handlers.append(RateLimitErrorRetryHandler(max_retry_count=5))
        self.db = db
        self._limiter = AdaptiveRateLimiter()
        self._api_calls = 0

    def _api_call(self, method: str, **kwargs) -> dict:
        """API 호출 래퍼 (레이트 리밋 + 에러 처리)"""
        self._limiter.wait()
        try:
            response = getattr(self.client, method)(**kwargs)
            self._limiter.on_success()
            self._api_calls += 1
            return response.data
        except SlackApiError as e:
            if e.response.status_code == 429:
                self._limiter.on_rate_limited()
                retry_after = int(e.response.headers.get("Retry-After", 30))
                logger.warning("429 응답, %d초 대기 후 재시도", retry_after)
                time.sleep(retry_after)
                return self._api_call(method, **kwargs)
            raise

    def _paginate(self, method: str, result_key: str, **kwargs) -> Generator[list[dict], None, None]:
        """커서 기반 페이지네이션 제네릭 헬퍼"""
        kwargs.setdefault("limit", 200)
        cursor = None

        while True:
            if cursor:
                kwargs["cursor"] = cursor

            data = self._api_call(method, **kwargs)
            items = data.get(result_key, [])
            if items:
                yield items

            cursor = data.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

    # ─── Sync ───

    def sync_all(
        self,
        full: bool = False,
        channel_names: Optional[list[str]] = None,
        include_archived: bool = False,
        include_private: bool = False,
        include_dm: bool = False,
    ) -> dict:
        """전체 동기화 실행"""
        stats = {"users": 0, "channels": 0, "messages": 0, "threads": 0}

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
        ) as progress:
            # 1. Users
            task = progress.add_task("사용자 동기화", total=None)
            stats["users"] = self.sync_users()
            progress.update(task, completed=100, total=100)

            # 2. Channels
            task = progress.add_task("채널 목록 동기화", total=None)
            channels = self.sync_channels(
                include_archived=include_archived,
                include_private=include_private,
                include_dm=include_dm,
            )
            stats["channels"] = len(channels)
            progress.update(task, completed=100, total=100)

            # 3. Filter channels
            if channel_names:
                channel_names_set = set(channel_names)
                channels = [c for c in channels if c["name"] in channel_names_set]

            # 4. Messages per channel
            ch_task = progress.add_task(
                "채널 메시지 동기화", total=len(channels)
            )
            for ch in channels:
                msg_count, thread_count = self.sync_channel_messages(
                    ch["id"], ch["name"], full=full, progress=progress
                )
                stats["messages"] += msg_count
                stats["threads"] += thread_count
                progress.update(ch_task, advance=1)

        logger.info(
            "동기화 완료: 사용자 %d, 채널 %d, 메시지 %d, 스레드 %d (API 호출 %d회)",
            stats["users"], stats["channels"], stats["messages"],
            stats["threads"], self._api_calls,
        )
        return stats

    def sync_users(self) -> int:
        """모든 사용자 동기화"""
        all_users: list[SlackUser] = []
        for page in self._paginate("users_list", "members"):
            for data in page:
                all_users.append(SlackUser.from_api(data))

        count = self.db.upsert_users(all_users)
        logger.info("사용자 %d명 동기화 완료", count)
        return count

    def sync_channels(
        self,
        include_archived: bool = False,
        include_private: bool = False,
        include_dm: bool = False,
    ) -> list[dict]:
        """모든 채널 동기화, 채널 목록 반환"""
        types = ["public_channel"]
        if include_private:
            types.append("private_channel")
        if include_dm:
            types.extend(["im", "mpim"])  # DM 및 그룹 DM (User Token 필요)

        all_channels: list[SlackChannel] = []
        for page in self._paginate(
            "conversations_list",
            "channels",
            types=",".join(types),
            exclude_archived=not include_archived,
        ):
            for data in page:
                all_channels.append(SlackChannel.from_api(data))

        self.db.upsert_channels(all_channels)
        logger.info("채널 %d개 동기화 완료", len(all_channels))

        return self.db.get_all_channels()

    def sync_channel_messages(
        self,
        channel_id: str,
        channel_name: str,
        full: bool = False,
        progress: Optional[Progress] = None,
    ) -> tuple[int, int]:
        """채널 메시지 동기화. (메시지 수, 스레드 수) 반환"""
        self.db.set_sync_status(channel_id, "syncing")

        try:
            # 증분 동기화: 마지막 ts 이후만
            oldest = None
            if not full:
                oldest = self.db.get_sync_state(channel_id)

            msg_task = None
            if progress:
                msg_task = progress.add_task(
                    f"  #{channel_name}", total=None
                )

            latest_ts_seen = oldest or "0"
            total_messages = 0

            kwargs = {"channel": channel_id}
            if oldest:
                kwargs["oldest"] = oldest
                kwargs["inclusive"] = False

            for page in self._paginate(
                "conversations_history", "messages", **kwargs
            ):
                batch: list[SlackMessage] = []
                all_reactions: list[SlackReaction] = []
                all_files: list[SlackFile] = []

                for data in page:
                    msg = SlackMessage.from_api(data, channel_id)
                    batch.append(msg)

                    if msg.ts > latest_ts_seen:
                        latest_ts_seen = msg.ts

                    # 리액션 추출
                    for reaction_data in msg.reactions:
                        all_reactions.extend(
                            SlackReaction.from_message_api(
                                channel_id, msg.ts, reaction_data
                            )
                        )

                    # 파일 추출
                    for file_data in msg.files:
                        all_files.append(
                            SlackFile.from_api(file_data, channel_id, msg.ts)
                        )

                self.db.upsert_messages(batch)
                if all_reactions:
                    self.db.upsert_reactions(all_reactions)
                if all_files:
                    self.db.upsert_files(all_files)
                total_messages += len(batch)

                if msg_task is not None:
                    progress.update(
                        msg_task,
                        description=f"  #{channel_name} ({total_messages} msgs)",
                    )

            # 스레드 답글 수집
            thread_parents = self.db.get_thread_parents(channel_id, since_ts=oldest)
            thread_count = 0

            for parent_ts in thread_parents:
                replies = self._fetch_thread_replies(channel_id, parent_ts)
                if replies:
                    self.db.upsert_messages(replies)
                    thread_count += 1

            # 총 메시지 수 업데이트
            total_in_db = self.db.conn.execute(
                "SELECT COUNT(*) FROM messages WHERE channel_id = ?",
                (channel_id,),
            ).fetchone()[0]

            self.db.update_sync_state(channel_id, latest_ts_seen, total_in_db)

            if msg_task is not None:
                progress.update(msg_task, visible=False)

            logger.info(
                "채널 #%s: 메시지 %d개, 스레드 %d개 동기화",
                channel_name, total_messages, thread_count,
            )
            return total_messages, thread_count

        except Exception:
            self.db.set_sync_status(channel_id, "error")
            raise

    def _fetch_thread_replies(
        self, channel_id: str, thread_ts: str
    ) -> list[SlackMessage]:
        """스레드 답글 수집 (부모 메시지 제외)"""
        replies: list[SlackMessage] = []

        for page in self._paginate(
            "conversations_replies",
            "messages",
            channel=channel_id,
            ts=thread_ts,
        ):
            for data in page:
                # 부모 메시지는 스킵 (이미 history에서 수집됨)
                if data["ts"] == thread_ts:
                    continue
                replies.append(SlackMessage.from_api(data, channel_id))

        return replies
