import asyncio
import os
import time
from pathlib import Path

import pytest

from config.exceptions import (
    BudgetExceededError,
    BusyError,
    ImageTooLargeError,
    InvalidImageError,
    RateLimitedError,
    UnsupportedImageFormatError,
)
from crocol.app.api.guards import RateLimiter, RunSlots, SpendCounter
from crocol.infrastructure.vision.image_store import LocalImageStore

TRACE = "1b4e28ba-2fa1-11d2-883f-0016d3cca427"


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_one_per_minute_then_retry_after() -> None:
    clock = Clock()
    limiter = RateLimiter(per_minute=1, per_day=12, clock=clock)
    limiter.check("ip")
    with pytest.raises(RateLimitedError) as error:
        limiter.check("ip")
    assert 1 <= error.value.retry_after <= 60
    clock.now += 61
    limiter.check("ip")


def test_twelve_per_day_then_blocked_until_the_window_moves() -> None:
    clock = Clock()
    limiter = RateLimiter(per_minute=1, per_day=12, clock=clock)
    for _ in range(12):
        limiter.check("ip")
        clock.now += 61
    with pytest.raises(RateLimitedError) as error:
        limiter.check("ip")
    assert error.value.retry_after > 60
    limiter.check("other-ip")
    clock.now += 86400
    limiter.check("ip")


def fixed_day(day: list[str]):
    def today() -> str:
        return day[0]
    return today


def test_spend_counter_caps_questions_and_tokens_and_rolls_daily() -> None:
    day = ["2026-10-17"]
    counter = SpendCounter(max_questions=2, max_tokens=1000,
                           today=fixed_day(day))
    counter.reserve()
    counter.reserve()
    with pytest.raises(BudgetExceededError):
        counter.reserve()
    day[0] = "2026-10-18"
    counter.reserve()
    counter.add_tokens(1000)
    with pytest.raises(BudgetExceededError):
        counter.reserve()


def test_seed_restores_todays_totals() -> None:
    counter = SpendCounter(max_questions=30, max_tokens=800_000)
    counter.seed(questions=30, tokens=0)
    with pytest.raises(BudgetExceededError):
        counter.reserve()


@pytest.mark.anyio
async def test_third_run_waits_then_is_busy() -> None:
    slots = RunSlots(slots=2, wait_s=0.05)
    async with slots.slot():
        async with slots.slot():
            with pytest.raises(BusyError):
                async with slots.slot():
                    pass
    async with slots.slot():
        await asyncio.sleep(0)


@pytest.mark.parametrize(
    ("error", "status"),
    [(InvalidImageError, 400), (UnsupportedImageFormatError, 415),
     (ImageTooLargeError, 413)],
)
def test_image_errors_carry_status_and_stay_value_errors(error: type,
                                                        status: int) -> None:
    instance = error()
    assert instance.status_code == status
    assert isinstance(instance, ValueError)
    assert instance.public_message


def test_image_store_names_by_uuid_and_purges_after_retention(
        tmp_path: Path) -> None:
    store = LocalImageStore(directory=tmp_path, retention_hours=72)
    saved = store.save(TRACE, b"jpeg")
    assert saved.name == f"{TRACE}.jpg"
    with pytest.raises(ValueError):
        store.path_for("../../etc/passwd")

    old = time.time() - 73 * 3600
    os.utime(saved, (old, old))
    fresh = store.save("2c4e28ba-2fa1-11d2-883f-0016d3cca427", b"jpeg")
    assert store.purge() == 1
    assert not saved.exists() and fresh.exists()
