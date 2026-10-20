#%% imports
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

from pydantic import ValidationError

from crocol.infrastructure.simulation import SweepOptions, sweep
import plots
from terminal import read_parameters, read_sweep_options


#%% run
try:
    params = read_parameters(for_sweep=True)
    options = SweepOptions(**read_sweep_options())
    result = sweep(params, options)
except ValidationError as exc:
    for err in exc.errors():
        print(f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}")
    raise SystemExit(1)

print()
print(result.to_markdown())
print("\nBounds:", result.bounds)
print("Recommended rate:", result.recommended_rate["target"] if result.recommended_rate else None)
print("Best BHP:", result.best_bhp["target"] if result.best_bhp else None)
for note in result.notes:
    print("-", note)


#%% plots
plots.plot_sweep(result)
