import math

import numpy as np
from scipy.special import exp1

from crocol.infrastructure.simulation.grid import DARCY, VEL_FACTOR
from crocol.infrastructure.simulation.results import SimulationResult
from crocol.infrastructure.simulation.schemas import SimulationInput
from crocol.infrastructure.simulation.sweep_models import SweepOptions


def open_thickness(inp: SimulationInput) -> float:
    dz = inp.h / inp.Nz
    z = (np.arange(inp.Nz) + 0.5) * dz
    return float(((z >= inp.perf_top) & (z <= inp.perf_bot)).sum() * dz)


def rate_search_bounds(inp: SimulationInput,
                       opts: SweepOptions) -> tuple[float, float]:
    """Rate range from the pseudo-steady-state and line-source rates."""
    drawdown = inp.pi - inp.pwf_floor
    k = inp.kro * inp.kh
    flow = 2.0 * math.pi * DARCY * k * open_thickness(inp)
    ln_term = max(math.log(inp.re / inp.rw_eff) - 0.75 + inp.skin_eff, 0.1)
    q_pss = flow / (inp.mu * inp.Bo * ln_term) * drawdown

    eta = VEL_FACTOR * k / (inp.phi * inp.mu * (inp.co + inp.cf))
    x = inp.rw_eff ** 2 / (4.0 * eta * inp.T)
    q_ia = (drawdown * 2.0 * flow
            / (inp.Bo * inp.mu * (exp1(x) + 2.0 * inp.skin_eff)))

    q_hi = 1.5 * max(q_pss, q_ia)
    if opts.rate_max is not None:
        q_hi = opts.rate_max
    if inp.q_max is not None:
        q_hi = min(q_hi, inp.q_max)

    q_lo = opts.rate_min if opts.rate_min is not None else 0.05 * q_hi
    if inp.q_abandon is not None:
        q_lo = max(q_lo, 1.5 * inp.q_abandon)
    if q_lo >= q_hi:
        raise ValueError(
            f"Empty rate range: lowest {q_lo:.1f} STB/d is not below "
            f"highest {q_hi:.1f} STB/d, check q_max, q_abandon and "
            f"rate_min/rate_max")
            # returns  q:lo , q:hi
    return q_lo, q_hi


def prepare_base(params: SimulationInput | dict
                 ) -> tuple[SimulationInput, dict]:
    data = dict(params)
    if isinstance(params, SimulationInput):
        data = params.model_dump()
    data.update(well_mode="bhp", pwf=data["pi"], q=None)
    inp = SimulationInput(**data)
    return inp, inp.model_dump()


def binding_limits(summary: dict) -> str:
    limits = []
    if summary["days_pwf_floor"] > 0.0:
        limits.append(f"pwf_floor({summary['floor_source']})")
    if summary["days_q_cap"] > 0.0:
        limits.append("q_cap")
    return "+".join(limits) if limits else "none"


def make_row(control: str, value: float,
             res: SimulationResult,
             discount_rate: float
             ) -> tuple[dict, tuple, float]:
    sim, s, inp = res.sim, res.summary, res.inp
    t_mid = sim.t - 0.5 * sim.dt
    factor = (1.0 + discount_rate) ** (-t_mid / 365.0)
    np_limit = float(sim.C.sum() * (inp.pi - inp.pwf_floor))

    row = {
        "control": control,
        "target": float(value),
        "np_stb": s["np_stb"],
        "rf": s["recovery_factor"],
        "pct_of_limit": s["np_stb"] / np_limit,
        "plateau_days": s["plateau_days"],
        "days_pwf_floor": s["days_pwf_floor"],
        "days_q_cap": s["days_q_cap"],
        "t_end_days": s["t_end_days"],
        "ended_by": s["ended_by"],
        "q_30d_stb_d": float(np.interp(30.0, sim.t, sim.q)),
        "q_final_stb_d": s["q_final_stb_d"],
        "pwf_final_psi": s["pwf_final_psi"],
        "drawdown_max_psi": float(inp.pi - sim.pwf.min()),
        "discounted_np_stb": float(np.sum(sim.q * sim.dt * factor)),
        "t90_days": None,
        "limit": binding_limits(s),
        "valid": s["valid"],
    }
    curve = (np.concatenate(([0.0], sim.t)),
             np.concatenate(([0.0], sim.Np))
             )

    return row, curve, np_limit
