import asyncio
import os
import json
import subprocess
import sys
import threading
from typing import Any

import pytest

from config.exceptions import (
    SimulationInputError,
    SimulationTimeoutError,
    SimulatorBusyError,
)
from config.settings import WELLSIM_LABEL
from crocol.application.tools.well_simulation import (
    SimulationRunner,
    search_well_sweep,
    sweep_chunk,
)
from crocol.infrastructure.simulation.adapter import NumericWellSimulator

WELL = dict(rw=0.354, re=1000.0, h=50.0, Nr=20, Nz=5, kh=100.0, kv_kh=0.1,
            phi=0.2, cf=4e-6, pi=4000.0, pb=2000.0, mu=1.5, Bo=1.2,
            co=1e-5, rho=50.0, q=1000.0, T=365.0, Nt=60)
SMALL_SWEEP = {"n_rate": 4, "n_bhp": 3, "refine_rounds": 0}
SIM = NumericWellSimulator()


class SlowSimulator:
    """Blocks inside run until released, like a long simulation."""

    def __init__(self) -> None:
        self.release = threading.Event()
        self.finished = threading.Event()

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        self.release.wait(5.0)
        self.finished.set()
        return {"ok": True}

    def sweep(self, params: dict[str, Any],
              options: dict[str, Any]) -> dict[str, Any]:
        return self.run(params)


def test_run_payload_is_json_with_series_and_fields() -> None:
    out = json.loads(json.dumps(SIM.run(WELL)))
    assert out["summary"]["valid"]
    assert len(out["series"]["t_days"]) <= 200
    assert len(out["fields"]["r_cell_ft"]) == WELL["Nr"]
    assert out["inputs"]["theta"] == 1.0


@pytest.mark.parametrize("changes,message", [
    ({"Nr": 51}, "Nr must be at most 50"),
    ({"Nz": 21}, "Nz must be at most 20"),
    ({"Nt": "366"}, "Nt must be at most 365"),
    ({"theta": 0.5}, "theta is not a web form parameter"),
    ({"checkpoints": [10.0]}, "checkpoints is not a web form parameter"),
    ({"outer_bc": "pressure"}, "outer_bc is not a web form parameter"),
    ({"pe": 3000.0}, "pe is not a web form parameter"),
    ({"pb": 4500.0}, "pb must be below pi"),
    ({"bogus": 1}, "bogus"),
])
def test_web_input_enforces_caps_and_fixed_settings(
        changes: dict, message: str) -> None:
    with pytest.raises(SimulationInputError, match=message):
        SIM.run({**WELL, **changes})


def test_sweep_needs_no_target_and_returns_curves() -> None:
    params = {k: v for k, v in WELL.items() if k != "q"}
    out = json.loads(json.dumps(SIM.sweep(params, SMALL_SWEEP)))
    assert out["recommended_rate"] is not None
    assert len(out["curves"]) == len(out["rows"])
    assert out["well"]["Nr"] == WELL["Nr"]
    assert "theta" in out["well"]


@pytest.mark.parametrize("options,message", [
    ({"n_rate": 13}, "n_rate must be at most 12"),
    ({"n_bhp": 11}, "n_bhp must be at most 10"),
    ({"skin": 2.0}, "skin"),
])
def test_sweep_options_are_capped(options: dict, message: str) -> None:
    with pytest.raises(SimulationInputError, match=message):
        SIM.sweep(WELL, options)


def test_evidence_passage_is_cited_and_names_the_recommendation() -> None:
    result = SIM.sweep(WELL, SMALL_SWEEP)
    chunk = sweep_chunk(WELL, result)
    target = f"{result['recommended_rate']['target']:,.1f}"
    assert chunk.citation == WELLSIM_LABEL
    assert chunk.chunk_id == sweep_chunk(dict(WELL), result).chunk_id
    assert "Tasa recomendada: tasa " + target in chunk.text
    assert "| control" in chunk.text


@pytest.mark.anyio
async def test_runner_sweep_returns_result_and_chunk() -> None:
    runner = SimulationRunner(SIM)
    found = await search_well_sweep(runner, WELL)
    assert found.result["rows"]
    assert found.chunk.chunk_type == "simulation"


@pytest.mark.anyio
async def test_second_simulation_is_refused_while_one_runs() -> None:
    slow = SlowSimulator()
    runner = SimulationRunner(slow, wait_s=0.05)
    first = asyncio.ensure_future(runner.run(WELL))
    await asyncio.sleep(0.05)
    with pytest.raises(SimulatorBusyError):
        await runner.run(WELL)
    slow.release.set()
    assert await first == {"ok": True}


@pytest.mark.anyio
async def test_timeout_keeps_the_slot_until_the_thread_ends() -> None:
    slow = SlowSimulator()
    runner = SimulationRunner(slow, wait_s=0.05, run_timeout_s=0.05)
    with pytest.raises(SimulationTimeoutError):
        await runner.run(WELL)
    assert runner.slot.locked()

    slow.release.set()
    await asyncio.to_thread(slow.finished.wait, 5.0)
    await asyncio.sleep(0.05)
    assert not runner.slot.locked()


def test_api_process_imports_numpy_single_threaded() -> None:
    probe = (
        "import os, sys\n"
        "seen = {}\n"
        "class Probe:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name == 'numpy' and 'numpy' not in seen:\n"
        "            seen['numpy'] = os.environ.get('OPENBLAS_NUM_THREADS')\n"
        "        return None\n"
        "sys.meta_path.insert(0, Probe())\n"
        "import crocol.app.main\n"
        "print(seen.get('numpy'))\n"
    )
    env = {k: v for k, v in os.environ.items()
           if k != "OPENBLAS_NUM_THREADS"}
    out = subprocess.run([sys.executable, "-c", probe], env=env,
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-500:]
    assert out.stdout.strip().splitlines()[-1] == "1"
