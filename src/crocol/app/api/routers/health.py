import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from config.roles import MODELS
from config.settings import (
    API_PREFIX,
    APP_VERSION,
    GLOBAL_QUESTIONS_PER_DAY,
    GLOBAL_TOKENS_PER_DAY,
    MAX_CONCURRENT_RUNS,
    QUESTION_MAX_CHARS,
    RATE_PER_DAY,
    RATE_PER_MINUTE,
    VISION_FORMATS,
    VISION_LABEL,
    VISION_MAX_BYTES,
    get_settings,
)
from crocol.app.api.deps import admit_other, container
from crocol.app.deps import AppContainer
from crocol.app.schemas import MetaResponse, ReadyResponse
from crocol.infrastructure.repository.spatials import SOURCE
from crocol.infrastructure.vectors.chroma_store import chroma_client

router = APIRouter(prefix=API_PREFIX, tags=["health"])
State = Annotated[AppContainer, Depends(container)]
CHECK_TIMEOUT_S = 5.0
CHROMA_TTL_S = 60.0
CHROMA_CACHE: dict[str, tuple[float, dict]] = {}


async def check_postgres(state: AppContainer) -> dict:

    if state.pool is None:
        return {"ok": False, "detail": "not configured"}
    async with state.pool.connection() as conn:
        await conn.execute("SELECT 1")
    return {"ok": True}


def count_chroma() -> int:

    name = get_settings().collection_name
    return chroma_client().get_collection(name).count()


async def check_chroma(state: AppContainer) -> dict:
    """Cached for a minute: every probe is a paid network round trip."""
    cached = CHROMA_CACHE.get("chroma")
    if cached and time.monotonic() - cached[0] < CHROMA_TTL_S:
        return cached[1]
    records = await asyncio.to_thread(count_chroma)
    result = {"ok": records > 0, "detail": f"{records} records"}
    CHROMA_CACHE["chroma"] = (time.monotonic(), result)
    return result


async def check_vision(state: AppContainer) -> dict:

    if state.vision is None:
        return {"ok": False, "detail": "not configured"}
    await asyncio.to_thread(getattr, state.vision, "session")
    return {"ok": True, "detail": VISION_LABEL}


async def probe(check: Callable[[AppContainer], Awaitable[dict]],
                state: AppContainer
                ) -> dict:

    try:
        return await asyncio.wait_for(check(state), CHECK_TIMEOUT_S)
    except Exception as exc:
        return {"ok": False, "detail": type(exc).__name__}


@router.get("/health")
async def health() -> dict:
    """Liveness: the process answers."""
    return {"status": "ok"}


@router.get("/ready", response_model=ReadyResponse,
            dependencies=[Depends(admit_other)])
async def ready(state: State, response: Response) -> dict:
    """Readiness of Postgres, Chroma and the vision model (503 if not)."""
    checks = {
        "postgres": await probe(check_postgres, state),
        "chroma": await probe(check_chroma, state),
        "vision": await probe(check_vision, state),
    }
    is_ready = all(check["ok"] for check in checks.values())
    if not is_ready:
        response.status_code = 503
    return {"ready": is_ready, "checks": checks}


@router.get("/meta", response_model=MetaResponse,
            dependencies=[Depends(admit_other)])
async def meta(state: State) -> dict:
    """What the frontend shows: models, limits and today's usage."""
    return {
        "app": "Crocol",
        "version": APP_VERSION,
        "models": {**MODELS, "crack_segmentation": VISION_LABEL},
        "limits": {
            "questions_per_minute": RATE_PER_MINUTE,
            "questions_per_day_per_ip": RATE_PER_DAY,
            "questions_per_day": GLOBAL_QUESTIONS_PER_DAY,
            "tokens_per_day": GLOBAL_TOKENS_PER_DAY,
            "concurrent_runs": MAX_CONCURRENT_RUNS,
            "question_max_chars": QUESTION_MAX_CHARS,
            "image_max_bytes": VISION_MAX_BYTES,
            "image_formats": sorted(VISION_FORMATS),
        },
        "usage_today": state.spend.snapshot(),
        "citation_labels": {"spatial": SOURCE, "vision": VISION_LABEL},
    }
