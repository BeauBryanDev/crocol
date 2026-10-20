from typing import Annotated

from fastapi import APIRouter, Depends

from config.settings import (
    API_PREFIX,
    WELLSIM_LABEL,
    WELLSIM_MAX_N_BHP,
    WELLSIM_MAX_N_RATE,
    WELLSIM_MAX_NR,
    WELLSIM_MAX_NT,
    WELLSIM_MAX_NZ,
    WELLSIM_RUNS_PER_MINUTE,
    WELLSIM_SWEEPS_PER_DAY,
)
from crocol.app.api.deps import (
    admit_other,
    container,
    run_admission,
    sweep_admission,
)
from crocol.app.deps import AppContainer
from crocol.app.schemas import (
    ErrorResponse,
    WellDefaultsResponse,
    WellParams,
    WellRunResponse,
    WellSweepOptions,
    WellSweepResponse,
)

router = APIRouter(prefix=f"{API_PREFIX}/wellsim", tags=["wellsim"])
ERRORS = {code: {"model": ErrorResponse} for code in (422, 429, 503)}
State = Annotated[AppContainer, Depends(container)]
LIMITS = {
    "max_nr": WELLSIM_MAX_NR,
    "max_nz": WELLSIM_MAX_NZ,
    "max_nt": WELLSIM_MAX_NT,
    "max_n_rate": WELLSIM_MAX_N_RATE,
    "max_n_bhp": WELLSIM_MAX_N_BHP,
    "runs_per_minute": WELLSIM_RUNS_PER_MINUTE,
    "sweeps_per_day": WELLSIM_SWEEPS_PER_DAY,
}


@router.get("/defaults", response_model=WellDefaultsResponse,
            dependencies=[Depends(admit_other)])
async def defaults() -> dict:
    """Default well, sweep options and public limits for the web form."""
    return {
        "well": WellParams(),
        "options": WellSweepOptions(),
        "limits": LIMITS,
        "source": WELLSIM_LABEL,
    }


@router.post("/run", response_model=WellRunResponse, responses=ERRORS)
async def run(params: Annotated[dict, Depends(run_admission)],
              state: State) -> dict:
    """One simulation: pressure and rate series plus the final r-z field."""
    result = await state.simulation.run(params)
    return {**result, "source": WELLSIM_LABEL}


@router.post("/sweep", response_model=WellSweepResponse, responses=ERRORS)
async def sweep(admitted: Annotated[tuple[dict, dict],
                                    Depends(sweep_admission)],
                state: State) -> dict:
    """Rate and BHP sweep: recovery per case and the recommended rate."""
    params, options = admitted
    result = await state.simulation.sweep(params, options)
    return {**result, "source": WELLSIM_LABEL}
