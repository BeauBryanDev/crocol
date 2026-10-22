import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from config.exceptions import SimulationTimeoutError, SimulatorBusyError
from config.logging import elapsed_ms
from config.settings import (
    WELLSIM_LABEL,
    WELLSIM_RUN_TIMEOUT_S,
    WELLSIM_SWEEP_TIMEOUT_S,
    WELLSIM_WAIT_S,
)
from crocol.application.ports.simulation import WellSimulation
from crocol.application.tools.well_simulation_text import render_sweep
from crocol.domains.models.chunks import Chunk

LOGGER = logging.getLogger("crocol.wellsim")
TITLE = "Crocol – simulación numérica de pozo (flujo monofásico, r–z)"


@dataclass(frozen=True)
class SweepFound:
    result: dict[str, Any]
    chunk: Chunk


class SimulationRunner:
    """One simulation at a time per process, shared by the API and agent."""

    def __init__(self, sim: WellSimulation,
                 wait_s: float = WELLSIM_WAIT_S,
                 run_timeout_s: float = WELLSIM_RUN_TIMEOUT_S,
                 sweep_timeout_s: float = WELLSIM_SWEEP_TIMEOUT_S) -> None:
        self.sim = sim
        self.wait_s = wait_s
        self.run_timeout_s = run_timeout_s
        self.sweep_timeout_s = sweep_timeout_s
        self.slot = asyncio.Semaphore(1)

    def release(self, _: asyncio.Future) -> None:
        self.slot.release()

    async def guarded(self, call: Callable[..., dict], *args: Any,
                      timeout: float) -> dict[str, Any]:
        """The slot frees only when the worker thread really finishes."""
        name = getattr(call, "__name__", "call")
        started = time.perf_counter()
        try:
            await asyncio.wait_for(self.slot.acquire(), self.wait_s)
        except TimeoutError as exc:
            LOGGER.warning("wellsim %s busy after %d ms", name,
                           elapsed_ms(started))
            raise SimulatorBusyError() from exc

        waited = elapsed_ms(started)
        task = asyncio.ensure_future(asyncio.to_thread(call, *args))
        task.add_done_callback(self.release)
        try:
            result = await asyncio.wait_for(asyncio.shield(task), timeout)
        except TimeoutError as exc:
            LOGGER.warning("wellsim %s timed out after %ss", name, timeout)
            raise SimulationTimeoutError() from exc

        LOGGER.info("wellsim %s wait_ms=%d run_ms=%d", name, waited,
                    elapsed_ms(started) - waited)
        return result

    async def run(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self.guarded(self.sim.run, params,
                                  timeout=self.run_timeout_s)

    async def sweep(self, params: dict[str, Any],
                    options: dict[str, Any] | None = None
                    ) -> dict[str, Any]:
        return await self.guarded(self.sim.sweep, params, options or {},
                                  timeout=self.sweep_timeout_s)


def sweep_chunk(params: dict[str, Any], result: dict[str, Any]) -> Chunk:
    """Evidence passage with the sweep the user's well parameters produced."""
    key = json.dumps(params, sort_keys=True, default=str).encode()
    digest = hashlib.sha1(key).hexdigest()[:12]
    return Chunk(
        chunk_id=f"wellsim-{digest}",
        doc_id=f"wellsim-{digest}",
        text=render_sweep(result),
        citation=WELLSIM_LABEL,
        title=TITLE,
        collection="Crocol_Simulation",
        doc_type="simulation_result",
        chunk_type="simulation",
        heading_path="wellsim/sweep",
    )


async def search_well_sweep(runner: SimulationRunner,
                            params: dict[str, Any]) -> SweepFound:
    result = await runner.sweep(params)
    return SweepFound(result=result, chunk=sweep_chunk(params, result))
