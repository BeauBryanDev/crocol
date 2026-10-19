import numpy as np
from scipy.optimize import brentq

from crocol.infrastructure.simulation.schemas import SimulationInput

DARCY = 0.001127
FT3_PER_BBL = 5.615
VEL_FACTOR = DARCY * FT3_PER_BBL


def build_time_steps(inp: SimulationInput) -> tuple[np.ndarray, str]:
    """Build time steps for the simulation."""
    T, N = inp.T, inp.Nt
    if inp.dt_mode == "uniform" or N == 1 or inp.dt0 >= T / N:
        return np.full(N, T / N), "uniform"

    dt0 = inp.dt0

    def sum_error(g: float) -> float:
        return dt0 * (g ** N - 1.0) / (g - 1.0) - T

    g = brentq(sum_error, 1.0 + 1e-9, (T / dt0) ** (1.0 / (N - 1)))
    return dt0 * g ** np.arange(N), "geometric"


class RadialGrid:
    """Logarithmic r-z grid; cell n = i * Nz + k (i radial, k vertical)."""

    def __init__(self, inp: SimulationInput) -> None:
        """Initialize the radial grid."""
        self.inp = inp
        self.Nr = inp.Nr
        self.Nz = inp.Nz
        self.N = self.Nr * self.Nz
        self.ct = inp.co + inp.cf
        self.gamma = inp.rho / 144.0
        self.z_ref = 0.5 * inp.h
        self.rw = inp.rw_eff
        self.skin = inp.skin_eff

        steps = np.arange(self.Nr + 1) / self.Nr
        self.r_face = self.rw * (inp.re / self.rw) ** steps
        self.r_cell = np.sqrt(self.r_face[:-1] * self.r_face[1:])
        self.dr = np.diff(self.r_face)
        self.dz = inp.h / self.Nz
        self.z_face = np.linspace(0.0, inp.h, self.Nz + 1)
        self.z_cell = 0.5 * (self.z_face[:-1] + self.z_face[1:])

        self.build_geometry()
        self.build_well_and_boundaries()

    def idx(self, i: int, k: int) -> int:
        """Return the index of the cell."""
        return i * self.Nz + k

    def mobility_terms(self) -> tuple[float, float, float]:
        """Return the mobility terms."""
        inp = self.inp
        kr = inp.kro * inp.kh
        kz = kr * inp.kv_kh
        mob = 1.0 / (inp.mu * inp.Bo)
        return kr, kz, mob

    def build_geometry(self) -> None:
        """Build the geometry of the grid."""
        inp = self.inp
        kr, kz, mob = self.mobility_terms()

        outer = self.r_face[1:] ** 2
        inner = self.r_face[:-1] ** 2
        self.ring_area = np.pi * (outer - inner)
        self.bulk_vol = self.ring_area[:, None] * self.dz * np.ones(
            (1, self.Nz))
        self.pore_vol = inp.phi * self.bulk_vol

        ln_ratio = np.log(self.r_cell[1:] / self.r_cell[:-1])
        tr_col = DARCY * 2.0 * np.pi * kr * self.dz * mob / ln_ratio
        self.Tr = np.repeat(tr_col[:, None], self.Nz, axis=1)

        tz_row = DARCY * kz * self.ring_area * mob / self.dz
        self.Tz = np.repeat(tz_row[:, None], self.Nz - 1, axis=1)

        self.storage = self.pore_vol * self.ct / (inp.Bo * FT3_PER_BBL)

    def build_well_and_boundaries(self) -> None:
        """Build the well and boundaries of the grid
         by Dirichlet boundary conditions and Neumann boundary conditions."""
        inp = self.inp
        kr, kz, mob = self.mobility_terms()

        self.open = ((self.z_cell >= inp.perf_top)
                     & (self.z_cell <= inp.perf_bot))
        if not self.open.any():
            raise ValueError("No layer is open to flow, widen the "
                             "perforated interval or raise Nz")
        denom = np.log(self.r_cell[0] / self.rw) + self.skin
        well_index = DARCY * 2.0 * np.pi * kr * self.dz * mob / denom
        self.WI = np.where(self.open, well_index, 0.0)

        ln_outer = np.log(inp.re / self.r_cell[-1])
        self.Te = np.full(
            self.Nz, DARCY * 2.0 * np.pi * kr * self.dz * mob / ln_outer)
        self.Tv = DARCY * kz * self.ring_area * mob / (0.5 * self.dz)
