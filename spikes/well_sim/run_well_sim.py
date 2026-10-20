#%% imports
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

from pydantic import ValidationError

from crocol.infrastructure.simulation import (
    SimulationInput,
    simulate,
    validation_checks,
)
import plots
from terminal import read_parameters


#%% run
try:
    inp = SimulationInput(**read_parameters())
except ValidationError as exc:
    for err in exc.errors():
        print(f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}")
    raise SystemExit(1)

res = simulate(inp)

print("\nSummary")
for key, value in res.summary.items():
    print(f"  {key}: {value}")
print("Events:", res.events)
for warning in res.warnings:
    print("WARNING:", warning)
print("Checks:", validation_checks(res.sim))


#%% plots
plots.plot_grid(res)
plots.plot_matrix(res)
plots.plot_fields(res)
plots.plot_profiles(res)
plots.plot_production(res)
