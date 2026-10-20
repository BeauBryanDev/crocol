import json

import numpy as np
import pytest
from pydantic import ValidationError

from crocol.infrastructure.simulation import (
    SimulationInput,
    simulate,
    validation_checks,
)

BASE = dict(rw=2.5, re=960.0, h=86.0, Nr=30, Nz=12, kh=125.0, kv_kh=0.125, phi=0.25,
            cf=5e-6, pi=2640.0, pb=1300.0, mu=1.86, Bo=1.125, co=1.5e-5, rho=45.0,
            kro=0.85, T=100.0, Nt=100, q=1000.0)


def run(**changes):
    return simulate({**BASE, **changes})


def test_material_balance_closed():
    res = run()
    assert abs(res.summary["material_balance_rel_error"]) < 1e-9
    assert res.summary["valid"]


@pytest.mark.parametrize("theta", [1.0, 0.5])
def test_matches_line_source_and_pseudo_steady(theta):
    checks = validation_checks(run(theta=theta).sim)
    assert checks["ei_max_rel_error"] < 0.01
    assert checks["pss_slope_numerical"] == pytest.approx(checks["pss_slope_analytical"], rel=1e-3)


def test_hydrostatic_equilibrium_gives_no_flow():
    res = run(well_mode="bhp", pwf=2640.0, q=None)
    assert abs(res.summary["np_stb"]) < 1e-6


def test_bubble_point_floor_binds_and_keeps_result_valid():
    res = run(q=8000.0, pb=1800.0)
    s = res.summary
    assert s["floor_source"] == "bubble_point"
    assert s["days_pwf_floor"] > 0.0
    assert s["pwf_final_psi"] == pytest.approx(s["pwf_floor_psi"], abs=1e-6)
    assert s["p_min_cell_psi"] >= 1800.0
    assert s["valid"]


def test_max_drawdown_floor_binds():
    res = run(q=1500.0, max_drawdown=500.0)
    s = res.summary
    assert s["floor_source"] == "max_drawdown"
    assert s["pwf_final_psi"] == pytest.approx(2140.0, abs=1e-6)
    assert [e["mode"] for e in res.events] == ["target", "pwf_floor"]


def test_rate_cap_in_bhp_mode():
    res = run(well_mode="bhp", pwf=1500.0, q=None, q_max=500.0)
    assert res.sim.q.max() <= 500.0 + 1e-6
    assert "q_cap" in res.sim.modes


def test_economic_limit_abandons_the_well():
    res = run(well_mode="bhp", pwf=1500.0, q=None, q_abandon=50.0, T=1000.0, Nt=200)
    s = res.summary
    assert s["ended_by"] == "abandonment"
    assert s["q_final_stb_d"] < 50.0
    assert s["t_end_days"] < 1000.0


def test_pb_not_enforced_flags_invalid():
    res = run(q=8000.0, pb=1800.0, enforce_pb=False)
    assert not res.summary["valid"]
    assert any("bubble point" in w for w in res.warnings)


def test_negative_skin_uses_effective_radius_and_matches_line_source():
    drawdown = {s: run(skin=s).summary["pwf_final_psi"] for s in (0.0, -3.0)}
    assert drawdown[-3.0] > drawdown[0.0]
    checks = validation_checks(run(skin=-3.0).sim)
    assert checks["ei_max_rel_error"] < 0.03


def test_checkpoints_and_json_output():
    res = run(checkpoints=[10.0, 50.0])
    assert res.summary["np_10d_stb"] == pytest.approx(10000.0, rel=1e-6)
    assert res.summary["np_50d_stb"] == pytest.approx(50000.0, rel=1e-6)
    payload = json.dumps(res.to_dict(max_points=50, include_fields=True))
    assert len(json.loads(payload)["series"]["t_days"]) <= 50


@pytest.mark.parametrize("changes", [
    dict(pb=3000.0),
    dict(q=None),
    dict(perf_top=60.0, perf_bot=40.0),
    dict(unknown_key=1),
    dict(pwf_min=2700.0),
    dict(checkpoints=[500.0]),
])
def test_invalid_inputs_are_rejected(changes):
    with pytest.raises(ValidationError):
        SimulationInput(**{**BASE, **changes})
