from dataclasses import dataclass, field

from psycopg_pool import AsyncConnectionPool

import bootstrap
from config.settings import (
    GLOBAL_QUESTIONS_PER_DAY,
    GLOBAL_TOKENS_PER_DAY,
    MAX_CONCURRENT_RUNS,
    OTHER_RATE_PER_MINUTE,
    RATE_PER_DAY,
    RATE_PER_MINUTE,
    RUN_WAIT_S,
    WELLSIM_RUNS_PER_MINUTE,
    WELLSIM_SWEEPS_PER_DAY,
)
from crocol.app.api.guards import RateLimiter, RunSlots, SpendCounter
from crocol.application.tools.well_simulation import SimulationRunner
from crocol.application.usecases.ask_questions import AskQuestion
from crocol.application.usecases.get_entity import GetEntity
from crocol.application.usecases.get_trace import GetTrace
from crocol.infrastructure.repository.spatials import PgSpatialStore
from crocol.infrastructure.repository.traces import PgTraceStore
from crocol.infrastructure.vision.image_store import LocalImageStore
from crocol.infrastructure.vision.onnx_segmenter import OnnxCrackAnalyzer


def wellsim_run_limiter() -> RateLimiter:

    return RateLimiter(WELLSIM_RUNS_PER_MINUTE)


def wellsim_sweep_limiter() -> RateLimiter:
    """The daily cap is the only sweep limit, so it also bounds a minute."""
    return RateLimiter(WELLSIM_SWEEPS_PER_DAY, WELLSIM_SWEEPS_PER_DAY)


@dataclass
class AppContainer:
    """Everything the routers need, built once at startup."""

    pool: AsyncConnectionPool | None
    ask: AskQuestion
    get_trace: GetTrace
    spatial: PgSpatialStore | None
    vision: OnnxCrackAnalyzer | None
    images: LocalImageStore
    question_limiter: RateLimiter
    other_limiter: RateLimiter
    spend: SpendCounter
    slots: RunSlots
    get_entity: GetEntity | None = None
    simulation: SimulationRunner | None = None
    run_limiter: RateLimiter = field(default_factory=wellsim_run_limiter)
    sweep_limiter: RateLimiter = field(
        default_factory=wellsim_sweep_limiter)


def build_container(pool: AsyncConnectionPool | None) -> AppContainer:

    deps = bootstrap.build_deps(pool)
    return AppContainer(
        pool=pool,
        ask=bootstrap.build_ask(pool, deps),
        get_trace=bootstrap.build_get_trace(pool),
        spatial=deps.spatial,
        vision=deps.vision,
        images=LocalImageStore(),
        question_limiter=RateLimiter(RATE_PER_MINUTE, RATE_PER_DAY),
        other_limiter=RateLimiter(OTHER_RATE_PER_MINUTE),
        spend=SpendCounter(GLOBAL_QUESTIONS_PER_DAY, GLOBAL_TOKENS_PER_DAY),
        slots=RunSlots(MAX_CONCURRENT_RUNS, RUN_WAIT_S),
        get_entity=GetEntity(deps.graph) if deps.graph else None,
        simulation=deps.simulation,
    )


async def seed_spend(container: AppContainer) -> None:
    """Restore today's totals so a restart does not reset the cap."""
    if container.pool is None:
        return
    try:
        questions, tokens = await PgTraceStore(container.pool).today_totals()
    except Exception:
        return
    container.spend.seed(questions, tokens)
