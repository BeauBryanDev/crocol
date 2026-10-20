import dataclasses

import pytest
from test_api_routes import client_for, make_state

from config.settings import WELLSIM_LABEL
from crocol.app.api.guards import RateLimiter
from crocol.app.deps import AppContainer
from crocol.application.tools.well_simulation import SimulationRunner
from crocol.infrastructure.simulation.adapter import NumericWellSimulator

pytestmark = pytest.mark.anyio
SMALL = {"Nr": 12, "Nz": 4, "Nt": 40}
SMALL_SWEEP = {"n_rate": 4, "n_bhp": 3, "refine_rounds": 0}


def sim_state(tmp_path, runs_per_minute: int = 10,
              sweeps_per_day: int = 20) -> AppContainer:
    return dataclasses.replace(
        make_state(tmp_path),
        simulation=SimulationRunner(NumericWellSimulator()),
        run_limiter=RateLimiter(runs_per_minute),
        sweep_limiter=RateLimiter(sweeps_per_day, sweeps_per_day))


async def test_defaults_give_the_form_its_starting_well(tmp_path) -> None:
    async with client_for(sim_state(tmp_path)) as client:
        response = await client.get("/api/wellsim/defaults")
    body = response.json()
    assert response.status_code == 200
    assert body["well"]["pi"] == 4000.0 and body["well"]["q"] == 1000.0
    assert "theta" not in body["well"]
    assert body["limits"]["max_nr"] == 50
    assert body["limits"]["sweeps_per_day"] == 20
    assert body["source"] == WELLSIM_LABEL


async def test_run_returns_series_and_field(tmp_path) -> None:
    async with client_for(sim_state(tmp_path)) as client:
        response = await client.post("/api/wellsim/run", json=SMALL)
    body = response.json()
    assert response.status_code == 200
    assert body["summary"]["valid"]
    assert len(body["series"]["q_stb_d"]) == len(body["series"]["t_days"])
    assert len(body["fields"]["pressure_drop_final_psi"]) == SMALL["Nr"]
    assert body["inputs"]["theta"] == 1.0
    assert body["source"] == WELLSIM_LABEL


async def test_sweep_returns_table_curves_and_recommendation(
        tmp_path) -> None:
    payload = {"well": SMALL, "options": SMALL_SWEEP}
    async with client_for(sim_state(tmp_path)) as client:
        response = await client.post("/api/wellsim/sweep", json=payload)
    body = response.json()
    assert response.status_code == 200
    assert body["recommended_rate"]["control"] == "rate"
    assert len(body["curves"]) == len(body["rows"])
    assert body["table_markdown"].startswith("| control")


@pytest.mark.parametrize("payload,field", [
    ({"Nr": 51}, "Nr"),
    ({"Nt": 366}, "Nt"),
    ({"theta": 0.5}, "theta"),
    ({"outer_bc": "pressure"}, "outer_bc"),
])
async def test_caps_and_hidden_fields_are_rejected(
        tmp_path, payload: dict, field: str) -> None:
    async with client_for(sim_state(tmp_path)) as client:
        response = await client.post("/api/wellsim/run", json=payload)
    assert response.status_code == 422
    assert field in response.json()["error"]


async def test_sweep_option_caps_are_rejected(tmp_path) -> None:
    payload = {"well": SMALL, "options": {"n_rate": 13}}
    async with client_for(sim_state(tmp_path)) as client:
        response = await client.post("/api/wellsim/sweep", json=payload)
    assert response.status_code == 422
    assert "n_rate" in response.json()["error"]


async def test_physics_error_is_readable_and_costs_no_run(tmp_path) -> None:
    state = sim_state(tmp_path, runs_per_minute=1)
    async with client_for(state) as client:
        bad = await client.post("/api/wellsim/run",
                                json={**SMALL, "pb": 4500.0})
        good = await client.post("/api/wellsim/run", json=SMALL)
    assert bad.status_code == 422
    assert "pb must be below pi" in bad.json()["error"]
    assert good.status_code == 200


async def test_run_rate_limit(tmp_path) -> None:
    state = sim_state(tmp_path, runs_per_minute=1)
    async with client_for(state) as client:
        await client.post("/api/wellsim/run", json=SMALL)
        response = await client.post("/api/wellsim/run", json=SMALL)
    assert response.status_code == 429
    assert "simulations" in response.json()["error"]
    assert int(response.headers["retry-after"]) > 0


async def test_sweep_daily_limit(tmp_path) -> None:
    state = sim_state(tmp_path, sweeps_per_day=1)
    payload = {"well": SMALL, "options": SMALL_SWEEP}
    async with client_for(state) as client:
        await client.post("/api/wellsim/sweep", json=payload)
        response = await client.post("/api/wellsim/sweep", json=payload)
    assert response.status_code == 429
    assert "daily sweep limit" in response.json()["error"]


async def test_simulation_does_not_touch_the_chat_budget(tmp_path) -> None:
    state = sim_state(tmp_path)
    async with client_for(state) as client:
        await client.post("/api/wellsim/run", json=SMALL)
    assert state.spend.snapshot()["questions_today"] == 0


async def test_missing_simulator_is_503(tmp_path) -> None:
    async with client_for(make_state(tmp_path)) as client:
        response = await client.post("/api/wellsim/run", json=SMALL)
    assert response.status_code == 503


async def test_chat_with_a_well_is_a_normal_paid_question(tmp_path) -> None:
    state = sim_state(tmp_path)
    body = {"question": "Interpreta este pozo", "well": SMALL}
    async with client_for(state) as client:
        response = await client.post("/api/chat", json=body)
    assert response.status_code == 200
    assert state.ask.wells[0]["Nr"] == SMALL["Nr"]
    assert state.ask.wells[0]["pi"] == 4000.0
    assert state.spend.snapshot()["questions_today"] == 1


async def test_chat_stream_passes_the_well(tmp_path) -> None:
    state = sim_state(tmp_path)
    body = {"question": "Interpreta este pozo", "well": SMALL}
    async with client_for(state) as client:
        response = await client.post("/api/chat/stream", json=body)
    assert response.status_code == 200
    assert len(state.ask.wells) == 1
    assert state.ask.wells[0]["Nz"] == SMALL["Nz"]


async def test_chat_with_a_bad_well_costs_no_question(tmp_path) -> None:
    state = sim_state(tmp_path)
    body = {"question": "Interpreta este pozo",
            "well": {**SMALL, "pb": 4500.0}}
    async with client_for(state) as client:
        response = await client.post("/api/chat", json=body)
    assert response.status_code == 422
    assert "pb must be below pi" in response.json()["error"]
    assert state.ask.calls == []
    assert state.spend.snapshot()["questions_today"] == 0


async def test_chat_without_a_well_is_unchanged(tmp_path) -> None:
    state = sim_state(tmp_path)
    async with client_for(state) as client:
        await client.post("/api/chat", json={"question": "que es la Luna"})
    assert state.ask.wells == [None]
