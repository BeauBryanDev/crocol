import numpy as np
import pytest

from crocol.infrastructure.simulation import SimulationInput, simulate
from crocol.infrastructure.simulation.grid import RadialGrid
from crocol.infrastructure.simulation.solver import WellSimulator

BASE = dict(rw=0.354, re=1000.0, h=50.0, Nr=12, Nz=5, kh=100.0,
            kv_kh=0.1, phi=0.2, cf=4e-6, pi=4000.0, pb=2000.0, mu=1.5,
            Bo=1.2, co=1e-5, rho=50.0, q=1000.0, T=30.0, Nt=10)


def build(**changes: object) -> WellSimulator:
    inp = SimulationInput(**{**BASE, **changes})
    return WellSimulator(RadialGrid(inp), inp)


@pytest.mark.parametrize("control,value", [("rate", 800.0),
                                           ("bhp", 3000.0)])
@pytest.mark.parametrize("theta", [1.0, 0.5])
@pytest.mark.parametrize("changes", [
    {},
    {"outer_bc": "pressure", "top_bc": "pressure"},
    {"perf_top": 10.0, "perf_bot": 30.0},
    {"Nz": 1},
])
def test_banded_solve_matches_dense_bordered_system(
        control: str, value: float, theta: float, changes: dict) -> None:
    sim = build(**changes)
    rng = np.random.default_rng(7)
    pot = 4000.0 - 50.0 * rng.random(sim.grid.N)

    x = sim.solve(pot, 0.5, theta, control, value)
    A, b = sim.system(pot, 0.5, theta, control, value)
    dense = np.linalg.solve(A.toarray(), b)

    assert np.allclose(x, dense, rtol=1e-10, atol=1e-8)


def test_last_matrix_is_bordered_and_banded() -> None:
    res = simulate({**BASE, "Nr": 6, "Nz": 3})
    n = res.sim.grid.N
    A = res.sim.A_last.toarray()
    assert A.shape == (n + 1, n + 1)
    rows, cols = np.nonzero(A[:n, :n])
    assert np.abs(rows - cols).max() <= res.sim.grid.Nz
