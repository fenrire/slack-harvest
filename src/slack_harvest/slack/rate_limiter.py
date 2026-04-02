"""Slack API Rate Limit 처리."""

import time
from dataclasses import dataclass, field


@dataclass
class RateLimiter:
    """Tier 3 기준 1.2초 간격. Retry-After 헤더 존중."""

    min_interval: float = 1.2
    _last_call: float = field(default=0.0, init=False, repr=False)

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.monotonic()

    def wait_retry_after(self, seconds: int) -> None:
        time.sleep(seconds)
        self._last_call = time.monotonic()
