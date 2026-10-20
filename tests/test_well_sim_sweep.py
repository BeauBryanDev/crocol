import json

import pytest
from pydantic import ValidationError

from crocol.infrastructure.simulation import (
    SweepOptions,
    run_well_sweep,
    sweep,
    sweep_tool_spec,
)

BASE = dict(rw=2.5, re=960.0, h=86.0, Nr=30, Nz=12, kh=125.0, kv_kh=0.125, phi=0.25,
            cf=5e-6, pi=2640.0, pb=1300.0, mu=1.86, Bo=1.125, co=1.5e-5, rho=45.0,
            kro=0.85, T=100.0, Nt=60)


def rate_rows(result):
    return [r for r in result.rows if r["control"] == "rate"]


def test_recovery_grows_with_rate_then_flattens():
    res = sweep(BASE, {"controls": ["rate"], "n_rate": 6, "refine_rounds": 1})
    rows = rate_rows(res)
    assert rows[0]["np_stb"] == pytest.approx(rows[0]["target"] * 100.0, rel=1e-6)
    assert rows[0]["limit"] == "none"
    assert all(b["np_stb"] >= a["np_stb"] * (1 - 1e-4) for a, b in zip(rows, rows[1:]))
    assert max(r["np_stb"] for r in rows) <= res.bounds["np_depletion_limit_stb"] * 1.0001
    best, rec = res.best_rate, res.recommended_rate
    assert rec["np_stb"] >= 0.99 * best["np_stb"]
    assert rec["target"] <= best["target"]
    discounted = res.best_discounted_rate
    assert discounted["discounted_np_stb"] == max(r["discounted_np_stb"] for r in rows)
    assert discounted["target"] >= rec["target"]


def test_lower_bhp_recovers_more_and_floor_is_best():
    res = sweep(BASE, {"controls": ["bhp"], "n_bhp": 5})
    np_values = [r["np_stb"] for r in res.rows]
    assert all(a > b for a, b in zip(np_values, np_values[1:]))
    assert res.best_bhp["target"] == pytest.approx(res.inputs["pwf_floor_psi"])
    assert res.best_rate is None and res.recommended_rate is None


def test_facility_limit_caps_every_rate_and_is_reported():
    res = sweep({**BASE, "q_max": 1500.0}, {"controls": ["rate"], "n_rate": 5, "refine_rounds": 0})
    assert max(r["target"] for r in rate_rows(res)) <= 1500.0 + 1e-9
    assert res.best_rate["target"] == pytest.approx(1500.0, rel=1e-3)
    assert any("facility-limited" in n for n in res.notes)


def test_long_horizon_with_economic_limit_is_depletion_limited():
    res = sweep({**BASE, "T": 1500.0, "Nt": 100, "q_abandon": 50.0},
                {"controls": ["rate"], "n_rate": 6, "refine_rounds": 1})
    top = sorted(rate_rows(res), key=lambda r: r["target"])[-3:]
    assert all(r["ended_by"] == "abandonment" for r in top)
    assert (max(r["np_stb"] for r in top) - min(r["np_stb"] for r in top)) / top[-1]["np_stb"] < 0.03


def test_bubble_point_violations_are_excluded_from_the_ranking():
    res = sweep({**BASE, "pb": 1800.0, "enforce_pb": False},
                {"controls": ["rate"], "n_rate": 6, "refine_rounds": 0})
    assert any(not r["valid"] for r in res.rows)
    assert res.best_rate["valid"] and res.recommended_rate["valid"]


def test_skin_is_not_a_sweep_option():
    with pytest.raises(ValidationError):
        SweepOptions(skin=2.0)
    assert "skin" not in sweep_tool_spec()["input_schema"]["properties"]


@pytest.mark.parametrize("options", [dict(n_rate=2), dict(rate_min=500.0, rate_max=400.0),
                                     dict(controls=["rate", "rate"])])
def test_invalid_options_are_rejected(options):
    with pytest.raises(ValidationError):
        SweepOptions(**options)


def test_tool_wrapper_output_is_json_with_a_table():
    out = run_well_sweep(BASE, {"n_rate": 4, "n_bhp": 3, "refine_rounds": 0})
    payload = json.loads(json.dumps(out))
    assert payload["table_markdown"].startswith("| control")
    assert len(payload["rows"][0]) == len(payload["columns"])
    assert payload["recommended_rate"] is not None
    assert sweep_tool_spec()["name"] == "run_well_sweep"
