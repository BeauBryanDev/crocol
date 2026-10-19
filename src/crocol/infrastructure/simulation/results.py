from dataclasses import dataclass
from typing import Any

import numpy as np

from crocol.infrastructure.simulation.grid import FT3_PER_BBL, RadialGrid
from crocol.infrastructure.simulation.schemas import SimulationInput
from crocol.infrastructure.simulation.solver import WellSimulator

MODES = ("target", "pwf_floor", "q_cap")

ASSUMPTIONS = (
    "Single-phase undersaturated oil with constant PVT, compressibility "
    "and viscosity",
    "No gas or water flow, recovery is depletion-only (about ct times "
    "drawdown)",
    "Pressures are referred to mid-depth, pwf is a bottomhole target and "
    "lift is not modeled",
    "Negative skin is modeled with the effective wellbore radius "
    "rw*exp(-S)",
)


def validation_checks(sim: WellSimulator) -> dict[str, float | None]:
    """Validation checks for the simulation."""
    out = { # Output dictionary
        "ei_max_rel_error": None,
        "pss_slope_numerical": None,
        "pss_slope_analytical": None,
    }
    if not sim.ei_applies():
        return out # Return the output

    gr = sim.grid # Grid object
    t_a = max(gr.r_face[min(3, gr.Nr)] ** 2 / sim.eta, # Time at which the pressure is stabilized
              10.0 * sim.dt[0],
              100.0 * gr.rw ** 2 / (4.0 * sim.eta))
    t_b = 0.5 * sim.t_ia # Time at which the pressure is stabilized
    m = (sim.t >= t_a) & (sim.t <= t_b) # Mask for the time range
    if m.any():
        dp_num = sim.inp.pi - sim.pwf[m] # Numerical pressure drop
        dp_an = sim.inp.pi - sim.analytic_ei(sim.t[m]) # Analytic pressure drop
        out["ei_max_rel_error"] = float(
            np.max(np.abs(dp_num - dp_an) / dp_an))

    late = len(sim.t) > 1 and sim.t[-1] >= 2.0 * sim.t_ia # Late time
    if sim.closed and late:
        slope = (sim.pwf[-1] - sim.pwf[-2]) / (sim.t[-1] - sim.t[-2]) # Slope of the pressure drop
        out["pss_slope_numerical"] = float(slope)
        out["pss_slope_analytical"] = float(-sim.inp.q / sim.C.sum()) # Analytic slope of the pressure drop
        # Return the maximum relative error, the numerical slope, and the analytic slope
    return out


def sample_indices(n: int, max_points: int) -> np.ndarray:
    """Log-spaced indices that always keep the last step."""
    if n <= max_points:
        return np.arange(n) # Return the indices
    spaced = np.round(np.geomspace(1, n, max_points)).astype(int)
    return np.union1d(np.unique(spaced) - 1, [n - 1]) # Return the indices


@dataclass
class SimulationResult:
    inp: SimulationInput # Simulation input
    sim: WellSimulator # Simulation object
    summary: dict # Summary dictionary
    events: list # Events list
    warnings: list # Warnings list

    def series(self, idx: np.ndarray) -> dict[str, list]:
        sim = self.sim # Simulation object
        return {
            "t_days": sim.t[idx].tolist(),
            "pwf_psi": sim.pwf[idx].tolist(), # well operating pressure
            "q_stb_d": sim.q[idx].tolist(), # Well rate
            "np_stb": sim.Np[idx].tolist(), # Cumulative production
            "p_avg_psi": sim.p_avg[idx].tolist(), # Average pressure
            "mode": [sim.modes[i] for i in idx], # Modes
        }

    def to_dict(self, max_points: int = 200,
                include_fields: bool = False) -> dict[str, Any]:
        sim, gr = self.sim, self.sim.grid # Simulation object and grid object
        idx = sample_indices(len(sim.t), max_points) # Indices
        out = {
            "summary": self.summary, # Summary dictionary
            "events": self.events, # Events list
            "warnings": self.warnings,
            "assumptions": list(ASSUMPTIONS), # Assumptions list
            "inputs": self.inp.model_dump(), # Inputs dictionary
            "series": self.series(idx), # Series dictionary
        }
        if include_fields:
            last = sim.pot_hist[-1].reshape(gr.Nr, gr.Nz) # Last pressure
            out["fields"] = {
                "r_cell_ft": gr.r_cell.tolist(), # Radial cell distances
                "z_cell_ft": gr.z_cell.tolist(), # Vertical cell distances
                "pressure_drop_final_psi": (self.inp.pi - last).tolist(), # Final pressure drop
            }
        return out # Return the output


def first_limit_day(sim: WellSimulator) -> float | None:
    """First limit day."""
    for i, mode in enumerate(sim.modes): # Modes
        if mode != "target":
            return float(sim.t[i - 1]) if i > 0 else 0.0 # Return the first limit day
    return None # Return the first limit day


def mode_events(sim: WellSimulator) -> list[dict]:
    """Mode events."""
    events = [] # Events list
    previous = None # Previous mode
    for s, mode in enumerate(sim.modes): # Modes
        if mode != previous:
            t_days = float(sim.t[s - 1]) if s > 0 else 0.0 # Time days
            events.append({"t_days": t_days, "mode": mode}) # Events list
            previous = mode # Previous mode
    return events # Return the events list


def run_warnings(sim: WellSimulator, valid: bool,
                 p_min_cell: float) -> list[str]:
    """Run warnings."""
    inp = sim.inp # Simulation input
    floor = inp.pwf_floor # BHP floor
    warnings = [] # Warnings list
    if inp.well_mode == "bhp" and inp.pwf < floor: # BHP mode and BHP is less than BHP floor
        warnings.append(
            f"Target pwf {inp.pwf:g} psi is below the operating floor "
            f"{floor:.1f} psi ({inp.floor_source}), the floor was used") # Warnings list
    if (inp.well_mode == "rate" and inp.q_max is not None
            and inp.q > inp.q_max): # Rate mode and rate is greater than maximum rate
        warnings.append(
            f"Target rate {inp.q:g} STB/d exceeds q_max {inp.q_max:g} "
            f"STB/d, the cap was used") # Warnings list
    fell_back = inp.dt_mode == "geometric" and sim.dt_mode_used == "uniform"
    if fell_back and inp.Nt > 1:
        warnings.append("dt0 >= T/N, uniform time steps were used")
    if not valid:
        warnings.append(
            f"Pressure fell to {p_min_cell:.1f} psi, below the bubble point "
            f"{inp.pb:g} psi, the single-phase result is not valid") # Warnings list{inp.pb:g} psi, the single-phase result is not valid
    return warnings


def summarize(sim: WellSimulator) -> tuple[dict, list, list]:
    """Summarize the simulation."""
    inp, gr = sim.inp, sim.grid # Simulation input and grid object

    ooip = float(gr.pore_vol.sum() / FT3_PER_BBL / inp.Bo) # Original oil in place
    head = gr.gamma * (sim.z_flat[None, :] - gr.z_ref) # Head
    p_min_cell = float((sim.pot_hist + head).min()) # Minimum pressure
    valid = bool(p_min_cell >= inp.pb - 0.01) # Valid

    modes = np.array(sim.modes) # Modes
    days = {m: float(sim.dt[modes == m].sum()) for m in MODES} # Days
    plateau = days["target"] if inp.well_mode == "rate" else None # Plateau days

    summary = { # Summary dictionary
        "np_stb": float(sim.Np[-1]),
        "recovery_factor": float(sim.Np[-1] / ooip), # Recovery factor
        "ooip_stb": ooip, # Original oil in place
        "q_avg_stb_d": float(sim.Np[-1] / sim.t[-1]), # Average well rate
        "q_final_stb_d": float(sim.q[-1]), # Final well rate
        "pwf_final_psi": float(sim.pwf[-1]), # Final BHP
        "p_avg_final_psi": float(sim.p_avg[-1]), # Final average pressure
        "p_min_cell_psi": p_min_cell, # Minimum pressure
        "t_end_days": float(sim.t[-1]), # End time
        "ended_by": sim.ended_by, # Ended by
        "pwf_floor_psi": float(inp.pwf_floor), # BHP floor
        "floor_source": inp.floor_source, # Floor source
        "days_target": days["target"], # Target days
        "days_pwf_floor": days["pwf_floor"], # BHP floor days
        "days_q_cap": days["q_cap"], # Rate capped days
        "plateau_days": plateau, # Plateau days
        "t_first_limit_days": first_limit_day(sim), # First limit day
        "material_balance_rel_error": None, # Material balance relative error
        "valid": valid, # Valid
    } # Summary dictionary

    t0 = np.concatenate(([0.0], sim.t)) # Time
    np0 = np.concatenate(([0.0], sim.Np)) # Cumulative production
    for c in inp.checkpoints: # Checkpoints
        summary[f"np_{c:g}d_stb"] = float(np.interp(c, t0, np0)) # Cumulative production at checkpoint

    if sim.closed:
        expansion = float((sim.C * (inp.pi - sim.pot_hist[-1])).sum()) # Expansion
        error = (sim.Np[-1] - expansion) / max(abs(expansion), 1e-30) # Material balance relative error
        summary["material_balance_rel_error"] = float(error) # Material balance relative error

    return summary, mode_events(sim), run_warnings(sim, valid, p_min_cell) # Return the summary, events, and warnings


def simulate(params: SimulationInput | dict) -> SimulationResult:
    """Simulate the simulation."""
    inp = params # Simulation input
    if not isinstance(params, SimulationInput):
        inp = SimulationInput.model_validate(params) # Simulation input
    sim = WellSimulator(RadialGrid(inp), inp) # Simulation object
    sim.run() # Run the simulation
    summary, events, warnings = summarize(sim) # Summary, events, and warnings
    return SimulationResult(inp=inp, # Simulation input
                            sim=sim, # Simulation object
                            summary=summary, # Summary dictionary
                            events=events, # Events list
                            warnings=warnings) # Warnings list
