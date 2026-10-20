import asyncio
import math
import time
from collections import deque
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from config.exceptions import (
    BudgetExceededError,
    BusyError,
    RateLimitedError,
)

MINUTE_S = 60.0
DAY_S = 86400.0


class RateLimiter:
    """Sliding windows per key (client IP): per minute and per day."""

    def __init__(self, per_minute: int,
                per_day: int | None = None,
                clock: Callable[[], 
                float] = time.monotonic) -> None:

        self._per_minute = per_minute
        self._per_day = per_day
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def retry_after(self, hits: deque[float],
                    now: float) -> int | None:

        minute = [t for t in hits if now - t < MINUTE_S]
        
        if len(minute) >= self._per_minute:
            
            return math.ceil(MINUTE_S - (now - minute[0]))
        
        if self._per_day is not None and len(hits) >= self._per_day:
            return math.ceil(DAY_S - (now - hits[0]))
        
        return None

    def check(self, key: str) -> None:
        """Record one hit or raise RateLimitedError with a retry delay."""
        now = self._clock()
        hits = self._hits.setdefault(key, deque())
        
        while hits and now - hits[0] >= DAY_S:
            hits.popleft()

        wait = self.retry_after(hits, now)
        if wait is not None:
            raise RateLimitedError(retry_after=max(wait, 1))
        hits.append(now)

    def forget_idle(self) -> None:

        now = self._clock()
        
        for key in list(self._hits):
            
            hits = self._hits[key]
            if not hits or now - hits[-1] >= DAY_S:
                del self._hits[key]


def utc_day() -> str:

    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class SpendCounter:
    """Global questions and tokens per UTC day; questions are reserved."""

    def __init__(self, max_questions: int
                 , max_tokens: int,
                 today: Callable[[],
                                 str] = utc_day,
                 run_estimate: int = 0
                 ) -> None:

        self._max_questions = max_questions
        self._max_tokens = max_tokens
        self._run_estimate = run_estimate
        self._today = today
        self._day = today()
        self.questions = 0
        self.tokens = 0

    def roll(self) -> None:

        day = self._today()
        if day != self._day:
            self._day, self.questions, self.tokens = day, 0, 0

    def seed(self, questions: int, tokens: int) -> None:
        """Totals already spent today (from ops.query_log at startup)."""
        self.roll()
        self.questions, self.tokens = questions, tokens

    def reserve(self) -> None:

        self.roll()
        if (self.questions >= self._max_questions
                or self.tokens + self._run_estimate >= self._max_tokens):
            raise BudgetExceededError()
        self.questions += 1

    def release(self) -> None:
        """Give back a reserved question that never ran."""
        self.roll()
        self.questions = max(self.questions - 1, 0)

    def add_tokens(self, tokens: int) -> None:

        self.roll()
        self.tokens += max(int(tokens), 0)

    def snapshot(self) -> dict:

        self.roll()
        return {
            "questions_today": self.questions,
            "questions_per_day": self._max_questions,
            "tokens_today": self.tokens,
            "tokens_per_day": self._max_tokens,
        }


class RunSlots:
    """At most N agent runs at once; waiting longer than the limit fails."""

    def __init__(self, slots: int, wait_s: float) -> None:

        self._semaphore = asyncio.Semaphore(slots)
        self._wait_s = wait_s

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:

        try:
            await asyncio.wait_for(self._semaphore.acquire(), self._wait_s)
        except TimeoutError as exc:
            raise BusyError() from exc
        try:
            yield
        finally:
            self._semaphore.release()
