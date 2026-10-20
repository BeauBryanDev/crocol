import numpy as np
from scipy import sparse
from scipy.linalg import solveh_banded
from scipy.special import exp1

from crocol.infrastructure.simulation.grid import (
    DARCY,
    VEL_FACTOR,
    RadialGrid,
    build_time_steps,
)
from crocol.infrastructure.simulation.schemas import SimulationInput

IMPLICIT_START_STEPS = 4


def connection_entries(pairs: list[tuple[np.ndarray,
                                         np.ndarray,
                                         np.ndarray]],
                                         n_cells: int
                                         ) -> tuple[np.ndarray,
                                                    np.ndarray,
                                                    np.ndarray,
                                                    np.ndarray]:
    """Calculate the connection entries for the system of equations."""
    diag = np.zeros(n_cells)
    rows, cols, vals = [], [], []
    for a, b, t in pairs:
        np.add.at(diag, a, t)
        np.add.at(diag, b, t)
        rows.extend([a, b])
        cols.extend([b, a])
        vals.extend([-t, -t])
        
    return (np.concatenate(rows), np.concatenate(cols),
            np.concatenate(vals), diag)


class WellSimulator:
    """Unknowns: potential p - gamma*(z - z_ref) per cell, plus the well pwf.

    The cell block is SPD and banded (offsets 0, 1, Nz); the well borders it.
    """

    def __init__(self, grid: RadialGrid, inp: SimulationInput) -> None:
        """Initialize the well simulator."""
        self.grid = grid
        self.inp = inp
        self.dt, self.dt_mode_used = build_time_steps(inp)
        self.t = np.cumsum(self.dt)
        self.eta = VEL_FACTOR * inp.kro * inp.kh / (
            inp.phi * inp.mu * grid.ct)
        self.t_ia = 0.1 * np.pi * inp.re ** 2 / self.eta
        self.closed = (inp.outer_bc == "closed" and inp.top_bc == "noflow"
                       and inp.bottom_bc == "noflow")
        self.z_flat = np.tile(grid.z_cell, grid.Nr)
        self.assemble_static()
        self.assemble_well()
        self.assemble_band()


    def assemble_static(self) -> None:
        """Assemble the static part of the system of equations."""
        gr, inp = self.grid, self.inp
        cells = np.arange(gr.N).reshape(gr.Nr, gr.Nz)
        pairs = [
            (cells[:-1, :].ravel(), cells[1:, :].ravel(), gr.Tr.ravel()),
            (cells[:, :-1].ravel(), cells[:, 1:].ravel(), gr.Tz.ravel()),
        ]
        rows, cols, vals, diag = connection_entries(pairs, gr.N)

        gain = np.zeros(gr.N)
        boundaries = []
        if inp.outer_bc == "pressure":
            boundaries.append((cells[-1, :], gr.Te, inp.pe))
        if inp.top_bc == "pressure":
            boundaries.append((cells[:, 0], gr.Tv, inp.p_top))
        if inp.bottom_bc == "pressure":
            boundaries.append((cells[:, -1], gr.Tv, inp.p_bot))
        """Add the boundaries to the system of equations."""
        for where, trans, pressure in boundaries:
            np.add.at(diag, where, trans)
            np.add.at(gain, where, trans * pressure)

        off = sparse.coo_matrix((vals, (rows, cols)), shape=(gr.N, gr.N))
        self.K = (off + sparse.diags(diag)).tocsr()
        self.gain = gain
        self.C = gr.storage.reshape(gr.N)

    def assemble_well(self) -> None:
        """Assemble the well part of the system of equations."""
        gr = self.grid
        well_cells = np.array([gr.idx(0, k) for k in range(gr.Nz)])
        zeros = np.zeros(gr.Nz, dtype=int)
        self.WI_full = np.zeros(gr.N)
        self.WI_full[well_cells] = gr.WI
        self.well_col = sparse.csc_matrix(
            (-gr.WI, (well_cells, zeros)), shape=(gr.N, 1))
        self.rate_row = sparse.csr_matrix(
            (gr.WI, (zeros, well_cells)), shape=(1, gr.N))
        self.empty_row = sparse.csr_matrix((1, gr.N))

    def assemble_band(self) -> None:
        """Assemble the band part of the system of equations."""
        nz = self.grid.Nz
        self.band_K = np.zeros((nz + 1, self.grid.N))
        for d in range(nz + 1):
            self.band_K[nz - d, d:] = self.K.diagonal(d)

    def rhs(self, pot_old: np.ndarray, dt: float,
            theta: float) -> np.ndarray:
        """Calculate the right-hand side of the system of equations."""
        return (self.C / dt * pot_old - (1.0 - theta) * (self.K @ pot_old)
                + self.gain)

    def system(self, pot_old: np.ndarray, dt: float, theta: float,
               control: str, value: float
               ) -> tuple[sparse.csc_matrix, np.ndarray]:
        """Build the system of equations."""
        N = self.grid.N
        block = sparse.diags(self.C / dt + self.WI_full) + theta * self.K

        if control == "rate":
            row, corner = self.rate_row, -self.grid.WI.sum()
        else:
            row, corner = self.empty_row, 1.0
        A = sparse.bmat([[block, self.well_col], [row, [[corner]]]],
                        format="csc")

        b = np.empty(N + 1)
        b[:N] = self.rhs(pot_old, dt, theta)
        b[N] = value
        return A, b

    def well_rate(self, x: np.ndarray) -> float:
        """Calculate the well rate."""
        nz = self.grid.Nz
        return float((self.grid.WI * (x[:nz] - x[-1])).sum())

    def solve(self, pot: np.ndarray,
              dt: float, # Time step
              theta: float,
              control: str,
              value: float) -> np.ndarray:
        """Solve the system of equations."""
        self.last_args = (pot, dt, theta, control, value)
        band = theta * self.band_K
        band[-1] += self.C / dt + self.WI_full
        b = self.rhs(pot, dt, theta)

        if control == "bhp":
            cells = solveh_banded(band, b + self.WI_full * value,
                                  check_finite=False)
            return np.append(cells, value)

        y = solveh_banded(band, np.column_stack([b, self.WI_full]),
                          check_finite=False)
        wi = self.grid.WI
        nz = self.grid.Nz
        pwf = (value - wi @ y[:nz, 0]) / (wi @ y[:nz, 1] - wi.sum())

        return np.append(y[:, 0] + pwf * y[:, 1], pwf)

    def solve_step(self, pot: np.ndarray, 
                   dt: float, # Time step
                   theta: float, # Theta
                   ) -> tuple[np.ndarray, str, bool]:
        """Solve the system of equations for the next step."""
        inp = self.inp
        floor = inp.pwf_floor # BHP floor

        if inp.well_mode == "rate":
            capped = inp.q_max is not None and inp.q > inp.q_max # Rate is greater than maximum rate
            q_set = inp.q_max if capped else inp.q # Rate set
            x = self.solve(pot, dt, theta, "rate", q_set)
            if x[-1] >= floor: # BHP floor is reached
                return x, ("q_cap" if capped else "target"), False # Rate capped or target
            x = self.solve(pot, dt, theta, "bhp", floor)
            return x, "pwf_floor", True # BHP floor

        pwf_set = max(inp.pwf, floor) # BHP set
        x = self.solve(pot, dt, theta, "bhp", pwf_set) # Solve the system of equations
        if inp.q_max is not None and self.well_rate(x) > inp.q_max: # Well rate is greater than maximum rate
            x = self.solve(pot, dt, theta, "rate", inp.q_max) # Rate capped
            return x, "q_cap", False # Rate capped
        mode = "pwf_floor" if pwf_set > inp.pwf else "target" # Mode is pwf floor or target
        # Return the pressure, mode, and BHP controlled
        return x, mode, True

    def run(self) -> None:
        """Run the simulation."""
        gr, inp = self.grid, self.inp
        n_steps = len(self.dt) # Number of steps
        pot = np.full(gr.N, float(inp.pi)) # Initial pressure

        pot_hist = np.zeros((n_steps + 1, gr.N)) # Pressure history
        pot_hist[0] = pot # Initial pressure
        pwf = np.zeros(n_steps) # Well pressure
        q = np.zeros(n_steps) # Well rate
        modes = [] # Modes
        start = IMPLICIT_START_STEPS if inp.theta < 1.0 else 0 # Start steps
        left = start
        previous = None # Previous mode
        ended_by = "horizon" # Ended by horizon
        n_done = n_steps

        for s, dt in enumerate(self.dt): # Time step
            theta = 1.0 if left > 0 else inp.theta # Theta
            x, mode, bhp_controlled = self.solve_step(pot, dt, theta) # Solve the system of equations
            switched = previous is not None and mode != previous # Switched mode
            if start and switched and theta != 1.0:
                left = start # Start steps
                x, mode, bhp_controlled = self.solve_step(pot, dt, 1.0)
            previous = mode # Previous mode
            left = max(left - 1, 0) # Left steps

            pot = x[:-1] # Pressure
            pot_hist[s + 1] = pot # Pressure history
            pwf[s] = x[-1] # Well pressure
            q[s] = self.well_rate(x) # Well rate
            modes.append(mode) # Modes

            below = inp.q_abandon is not None and q[s] < inp.q_abandon # Below abandonment rate
            if bhp_controlled and below: # BHP controlled and below abandonment rate
                ended_by = "abandonment" # Ended by abandonment
                n_done = s + 1 # Number of done steps
                break

        self.dt = self.dt[:n_done] # Time steps
        self.t = self.t[:n_done] # Time
        self.pot_hist = pot_hist[:n_done + 1] # Pressure history
        self.pwf = pwf[:n_done] # Well pressure
        self.q = q[:n_done] # Well rate
        self.modes = modes # Modes
        self.ended_by = ended_by # Ended by
        self.Np = np.cumsum(self.q * self.dt) # Cumulative production
        self.p_avg = (self.pot_hist[1:] @ self.C) / self.C.sum() # Average pressure
        self.A_last = self.system(*self.last_args)[0] # Last system matrix


    def ei_applies(self) -> bool:
        """Check if the EI applies."""
        return (self.inp.well_mode == "rate" # Well mode is rate
                and set(self.modes) == {"target"} # All modes are target
                and bool(self.grid.open.all())) # All cells are open


    def analytic_ei(self, t: np.ndarray) -> np.ndarray: # Time
        """Calculate the analytic EI."""
        inp = self.inp
        k = inp.kro * inp.kh # Permeability
        x = inp.rw ** 2 / (4.0 * self.eta * t) # Radial distance
        pref = inp.q * inp.Bo * inp.mu / (4.0 * np.pi * DARCY * k * inp.h) # Pressure
        return inp.pi - pref * (exp1(x) + 2.0 * inp.skin) # Return the analytic EI


    def fields(self, step: int = -1
               ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calculate the vector velocity fields."""
        gr, inp = self.grid, self.inp
        pot = self.pot_hist[step].reshape(gr.Nr, gr.Nz)
        press = pot + gr.gamma * (gr.z_cell[None, :] - gr.z_ref)
        dpdr = np.gradient(pot, gr.r_cell, axis=0) # Radial gradient
        dpdz = np.zeros_like(pot)
        if gr.Nz > 1:
            dpdz = np.gradient(pot, gr.z_cell, axis=1) # Vertical gradient
        mob = VEL_FACTOR * inp.kro / inp.mu
        u_r = -mob * inp.kh * dpdr # Radial velocity
        u_z = -mob * inp.kh * inp.kv_kh * dpdz # Vertical velocity
        # Return the pressure, radial velocity, and vertical velocity
        return press, u_r, u_z
