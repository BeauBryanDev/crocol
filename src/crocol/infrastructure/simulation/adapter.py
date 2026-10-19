from typing import Any

from pydantic import ValidationError

from config.exceptions import SimulationInputError
from config.settings import (
    WELLSIM_CURVE_DIGITS,
    WELLSIM_MAX_N_BHP,
    WELLSIM_MAX_N_RATE,
    WELLSIM_MAX_NR,
    WELLSIM_MAX_NT,
    WELLSIM_MAX_NZ,
    WELLSIM_MAX_POINTS,
    WELLSIM_THETA,
)
from crocol.infrastructure.simulation.results import simulate
from crocol.infrastructure.simulation.schemas import SimulationInput
from crocol.infrastructure.simulation.sweep import sweep
from crocol.infrastructure.simulation.sweep_models import SweepOptions

WEB_FIXED = {
    "theta": WELLSIM_THETA,
    "outer_bc": "closed",
    "top_bc": "noflow",
    "bottom_bc": "noflow",
    "checkpoints": [],
}
WEB_EXCLUDED = ("pe", "p_top", "p_bot", *WEB_FIXED)
GRID_CAPS = {
    "Nr": WELLSIM_MAX_NR,
    "Nz": WELLSIM_MAX_NZ,
    "Nt": WELLSIM_MAX_NT,
}
SWEEP_CAPS = {
    "n_rate": WELLSIM_MAX_N_RATE,
    "n_bhp": WELLSIM_MAX_N_BHP,
}


def first_error(exc: ValidationError) -> str:
    err = exc.errors()[0]
    where = ".".join(str(part) for part in err["loc"])
    message = err["msg"].removeprefix("Value error, ")
    return f"{where}: {message}" if where else message


def check_caps(values: dict[str, Any], caps: dict[str, int]) -> None:
    """Applied after validation, so coerced strings are capped too."""
    for key, cap in caps.items():
        if values[key] > cap:
            raise SimulationInputError(f"{key} must be at most {cap}")


def web_input(params: dict[str, Any],
              for_sweep: bool = False) -> SimulationInput:
    """Validated input with the public caps and the fixed web settings."""
    for key in WEB_EXCLUDED:
        if key in params:
            raise SimulationInputError(f"{key} is not a web form parameter")
    data = {**params, **WEB_FIXED}
    if for_sweep:
        data.update(well_mode="bhp", q=None, pwf=params.get("pi"))
    try:
        inp = SimulationInput(**data)
    except ValidationError as exc:
        raise SimulationInputError(first_error(exc)) from exc
    check_caps(inp.model_dump(), GRID_CAPS)
    return inp


def web_options(options: dict[str, Any]) -> SweepOptions:
    try:
        opts = SweepOptions(**options)
    except ValidationError as exc:
        raise SimulationInputError(first_error(exc)) from exc
    check_caps(opts.model_dump(), SWEEP_CAPS)
    return opts


def curve_list(curves: dict) -> list[dict[str, Any]]:
    out = []
    for (control, target), (t, cum) in sorted(curves.items()):
        out.append({
            "control": control,
            "target": round(float(target), 2),
            "t_days": [round(float(v), WELLSIM_CURVE_DIGITS) for v in t],
            "np_stb": [round(float(v), 1) for v in cum],
        })
    return out


class NumericWellSimulator:
    """WellSimulation port over the radial r-z single-phase simulator."""

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        result = simulate(web_input(params))
        return result.to_dict(max_points=WELLSIM_MAX_POINTS,
                              include_fields=True)

    def sweep(self, params: dict[str, Any],
              options: dict[str, Any]) -> dict[str, Any]:
        inp = web_input(params, for_sweep=True)
        opts = web_options(options)
        try:
            result = sweep(inp, opts)
        except ValueError as exc:
            raise SimulationInputError(str(exc)) from exc
        payload = {"table_markdown": result.to_markdown(),
                   **result.to_dict()}
        payload["curves"] = curve_list(result.curves)
        payload["well"] = inp.model_dump(exclude={"well_mode", "q", "pwf"})
        
        return payload

