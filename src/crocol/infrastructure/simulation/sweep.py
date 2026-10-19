from typing import Any

import numpy as np
from pydantic import ValidationError

from crocol.infrastructure.simulation.results import simulate
from crocol.infrastructure.simulation.schemas import SimulationInput
from crocol.infrastructure.simulation.sweep_cases import (
    make_row,
    prepare_base,
    rate_search_bounds,
)
from crocol.infrastructure.simulation.sweep_models import (
    SweepOptions,
    SweepResult,
)
from crocol.infrastructure.simulation.sweep_notes import sweep_notes

CURVE_POINTS = 150
REFINE_FACTORS = (0.75, 0.5, 0.35, 0.25, 0.15)
REFINE_POINTS = 7


class SweepRunner:
    """Runs one case per control target and keeps rows, curves and notes."""

    def __init__(self, base: dict, opts: SweepOptions) -> None:
        self.base = base
        self.opts = opts
        self.rows: list[dict] = []
        self.curves: dict[tuple, tuple] = {}
        self.notes: list[str] = []
        self.np_limit: float | None = None

    def add(self, control: str, value: float) -> None:
        data = dict(self.base)
        if control == "rate":
            data.update(well_mode="rate", q=float(value), pwf=None)
        else:
            data.update(well_mode="bhp", pwf=float(value), q=None)
        try:
            res = simulate(SimulationInput(**data))
        except ValidationError as exc:
            message = exc.errors()[0]["msg"]
            self.notes.append(f"{control} {value:g} was rejected: {message}")
            return
        row, curve, self.np_limit = make_row(control, value, res,
                                             self.opts.discount_rate)
        self.rows.append(row)
        self.curves[(control, row["target"])] = curve

    def valid_rates(self) -> list[dict]:
        rates = []
        for r in self.rows:
            if r["control"] == "rate" and r["valid"]:
                rates.append(r)
        return sorted(rates, key=target_of)


def target_of(row: dict) -> float:
    return row["target"]


def np_of(row: dict) -> float:
    return row["np_stb"]


def discounted_of(row: dict) -> float:
    return row["discounted_np_stb"]


def row_order(row: dict) -> tuple[bool, float]:
    return row["control"] != "rate", row["target"]


def knee_index(ranked: list[dict], tolerance: float) -> int:
    best = max(r["np_stb"] for r in ranked)
    for i, r in enumerate(ranked):
        if r["np_stb"] >= (1.0 - tolerance) * best:
            return i
    return len(ranked) - 1


def refine_targets(ranked: list[dict], base_inp: SimulationInput,
                   opts: SweepOptions) -> list[float]:
    i = knee_index(ranked, opts.tolerance)
    if i > 0:
        lo, hi = ranked[i - 1]["target"], ranked[i]["target"]
        if hi - lo < 1e-3 * hi:
            return []
        return list(np.linspace(lo, hi, REFINE_POINTS)[1:-1])

    floor_q = 0.0
    if base_inp.q_abandon is not None:
        floor_q = 1.2 * base_inp.q_abandon
    lowest = opts.rate_min or 0.0
    new = []
    for f in REFINE_FACTORS:
        q = ranked[0]["target"] * f
        if q > floor_q and q >= lowest:
            new.append(q)
    return new


def run_rates(runner: SweepRunner, base_inp: SimulationInput,
              opts: SweepOptions) -> tuple[float, float]:
    q_lo, q_hi = rate_search_bounds(base_inp, opts)
    for q in np.linspace(q_lo, q_hi, opts.n_rate):
        runner.add("rate", q)

    for _ in range(opts.refine_rounds):
        ranked = runner.valid_rates()
        if len(ranked) < 2:
            break
        new = refine_targets(ranked, base_inp, opts)
        if not new:
            break
        for q in new:
            runner.add("rate", q)
    return q_lo, q_hi


def pick(subset: list[dict], lowest_target: bool) -> dict | None:
    if not subset:
        return None
    top = max(r["np_stb"] for r in subset)
    tied = [r for r in subset if r["np_stb"] >= top * (1.0 - 1e-9)]
    if lowest_target:
        return min(tied, key=target_of)
    return max(tied, key=target_of)


def sample_curves(curves: dict) -> dict:
    out = {}
    for key, (t, cum) in curves.items():
        n = len(t)
        spaced = np.round(np.geomspace(1, n, min(n, CURVE_POINTS)))
        idx = np.union1d(np.unique(spaced.astype(int)) - 1, [0, n - 1])
        out[key] = (t[idx], cum[idx])
    return out


def sweep(params: SimulationInput | dict,
          options: SweepOptions | dict | None = None) -> SweepResult:
    opts = options
    if not isinstance(options, SweepOptions):
        opts = SweepOptions.model_validate(options or {})
    base_inp, base = prepare_base(params)
    runner = SweepRunner(base, opts)

    rate_range = None
    if "rate" in opts.controls:
        rate_range = run_rates(runner, base_inp, opts)
    if "bhp" in opts.controls:
        floor = base_inp.pwf_floor
        for frac in np.linspace(0.0, 0.9, opts.n_bhp):
            runner.add("bhp", floor + frac * (base_inp.pi - floor))

    rows = runner.rows
    feasible = [r for r in rows if r["valid"]]
    if not feasible:
        raise ValueError("No feasible case: every run fell below the "
                         "bubble point")
    rows.sort(key=row_order)

    np_best = max(r["np_stb"] for r in feasible)
    for r in rows:
        t, cum = runner.curves[(r["control"], r["target"])]
        if cum[-1] >= 0.9 * np_best:
            r["t90_days"] = float(np.interp(0.9 * np_best, cum, t))

    rate_ok = [r for r in feasible if r["control"] == "rate"]
    bhp_ok = [r for r in feasible if r["control"] == "bhp"]
    best_rate = pick(rate_ok, True)
    best_bhp = pick(bhp_ok, False)
    best_overall = max([b for b in (best_rate, best_bhp) if b], key=np_of)

    recommended = None
    best_discounted = None
    if rate_ok:
        threshold = (1.0 - opts.tolerance) * best_rate["np_stb"]
        near_best = [r for r in rate_ok if r["np_stb"] >= threshold]
        recommended = min(near_best, key=target_of)
        best_discounted = max(rate_ok, key=discounted_of)

    ooip = best_overall["np_stb"] / best_overall["rf"]
    bounds = {
        "np_depletion_limit_stb": runner.np_limit,
        "rf_depletion_limit": runner.np_limit / ooip,
    }
    if rate_range is not None:
        bounds["rate_search_range_stb_d"] = [round(rate_range[0], 2),
                                             round(rate_range[1], 2)]
    bounds["pwf_floor_psi"] = base_inp.pwf_floor

    inputs = {
        "horizon_days": base_inp.T,
        "pi_psi": base_inp.pi,
        "pb_psi": base_inp.pb,
        "pwf_floor_psi": base_inp.pwf_floor,
        "floor_source": base_inp.floor_source,
        "q_max_stb_d": base_inp.q_max,
        "q_abandon_stb_d": base_inp.q_abandon,
        "max_drawdown_psi": base_inp.max_drawdown,
        "skin": base_inp.skin,
        "discount_rate_annual": opts.discount_rate,
    }
    notes = runner.notes + sweep_notes(base_inp, opts, recommended,
                                       best_discounted, best_rate,
                                       len(rows) - len(feasible))

    return SweepResult(options=opts,
                       inputs=inputs,
                       bounds=bounds,
                       rows=rows,
                       best_overall=best_overall,
                       best_rate=best_rate,
                       best_bhp=best_bhp,
                       recommended_rate=recommended,
                       best_discounted_rate=best_discounted,
                       notes=notes,
                       curves=sample_curves(runner.curves))


def run_well_sweep(well_params: SimulationInput | dict,
                   tool_args: SweepOptions | dict | None = None
                   ) -> dict[str, Any]:
                   
    result = sweep(well_params, tool_args)

    return {"table_markdown": result.to_markdown(), **result.to_dict()}
