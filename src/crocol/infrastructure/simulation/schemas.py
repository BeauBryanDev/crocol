import math
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

ATMOSPHERIC_PSI = 14.7


class SimulationInput(BaseModel):
    """Field units: ft, md, psi, cP, rb/STB, 1/psi, lb/ft3, STB/d, days.

    All pressures are referred to mid-depth of the producing layer.
    """

    model_config = ConfigDict(extra="forbid")

    rw: float = Field(gt=0, description="Well radius (ft)")
    re: float = Field(gt=0, description="Drainage radius (ft)")
    h: float = Field(gt=0, description="Producing thickness (ft)")
    Nr: int = Field(30, ge=3, le=200, description="Radial cells")
    Nz: int = Field(10, ge=1, le=60, description="Vertical cells")

    kh: float = Field(gt=0, description="Horizontal permeability (md)")
    kv_kh: float = Field(0.1, gt=0, le=1.0, description="Anisotropy kv/kh")
    phi: float = Field(gt=0, lt=1, description="Porosity (fraction)")
    cf: float = Field(ge=0, description="Rock compressibility (1/psi)")
    pi: float = Field(gt=0, description="Initial reservoir pressure (psi)")
    pb: float = Field(gt=0, description="Bubble point pressure (psi)")

    mu: float = Field(gt=0, description="Oil viscosity (cP)")
    Bo: float = Field(
        gt=0, description="Oil formation volume factor (rb/STB)")
    co: float = Field(ge=0, description="Oil compressibility (1/psi)")
    rho: float = Field(gt=0, description="Oil density (lb/ft3)")
    kro: float = Field(
        1.0, gt=0, le=1.0, description="Oil relative permeability")

    skin: float = Field(0.0, ge=-6.0, le=100.0, description="Skin factor")
    perf_top: float = Field(
        0.0, ge=0, description="Perforation top (ft below layer top)")
    perf_bot: Optional[float] = Field(
        None, gt=0, description="Perforation bottom (ft), default h")
    well_mode: Literal["rate", "bhp"] = Field(
        "rate", description="Primary well control")
    q: Optional[float] = Field(
        None, gt=0, description="Target rate (STB/d), rate mode")
    pwf: Optional[float] = Field(
        None, gt=0, description="Target flowing BHP (psi), bhp mode")

    pwf_min: Optional[float] = Field(
        None, gt=0, description="Operating minimum BHP (psi)")
    max_drawdown: Optional[float] = Field(
        None, gt=0, description="Maximum drawdown pi - pwf (psi)")
    q_max: Optional[float] = Field(
        None, gt=0, description="Facility rate limit (STB/d)")
    q_abandon: Optional[float] = Field(
        None, gt=0, description="Economic limit rate (STB/d)")
    enforce_pb: bool = Field(
        True, description="Keep every cell above the bubble point")

    outer_bc: Literal["closed", "pressure"] = "closed"
    pe: Optional[float] = Field(None, gt=0, description="Pressure at re (psi)")
    top_bc: Literal["noflow", "pressure"] = "noflow"
    p_top: Optional[float] = Field(
        None, gt=0, description="Pressure at top (psi)")
    bottom_bc: Literal["noflow", "pressure"] = "noflow"
    p_bot: Optional[float] = Field(
        None, gt=0, description="Pressure at bottom (psi)")

    T: float = Field(365.0, gt=0, description="Simulated horizon (days)")
    Nt: int = Field(
        100, ge=1, le=20000, description="Number of time steps")
    dt_mode: Literal["uniform", "geometric"] = "geometric"
    dt0: float = Field(
        1e-3, gt=0, description="First step for geometric spacing (days)")
    theta: float = Field(
        1.0, ge=0.5, le=1.0,
        description="Time weighting: 1.0 implicit, 0.5 Crank-Nicolson")
    checkpoints: list[float] = Field(
        default_factory=list, description="Report Np at these days")

    @property
    def rw_eff(self) -> float:
        if self.skin < 0.0:
            return self.rw * math.exp(-self.skin)
        return self.rw

    @property
    def skin_eff(self) -> float:
        return max(self.skin, 0.0)

    @property
    def pb_floor(self) -> float:
        gamma = self.rho / 144.0
        return self.pb + gamma * 0.5 * self.h * (1.0 - 1.0 / self.Nz)

    @property
    def floor_candidates(self) -> dict[str, float]:
        candidates = {"atmospheric": ATMOSPHERIC_PSI}
        if self.enforce_pb:
            candidates["bubble_point"] = self.pb_floor
        if self.pwf_min is not None:
            candidates["pwf_min"] = self.pwf_min
        if self.max_drawdown is not None:
            candidates["max_drawdown"] = self.pi - self.max_drawdown
        return candidates

    @property
    def pwf_floor(self) -> float:
        return max(self.floor_candidates.values())

    @property
    def floor_source(self) -> str:
        candidates = self.floor_candidates
        return max(candidates, key=candidates.get)

    def check_well_control(self) -> None:
        if self.well_mode == "rate":
            if self.q is None:
                raise ValueError("q is required when well_mode is 'rate'")
            q_eff = self.q
            if self.q_max is not None:
                q_eff = min(self.q, self.q_max)
            if self.q_abandon is not None and q_eff <= self.q_abandon:
                raise ValueError("q must exceed q_abandon, otherwise the "
                                 "well is abandoned at start")
            return

        if self.pwf is None:
            raise ValueError("pwf is required when well_mode is 'bhp'")
        if self.pwf > self.pi:
            raise ValueError("pwf must not exceed pi for a producer")

    @model_validator(mode="after")
    def check_consistency(self) -> "SimulationInput":
        if self.perf_bot is None:
            self.perf_bot = self.h
        if not self.perf_top < self.perf_bot <= self.h:
            raise ValueError("Require perf_top < perf_bot <= h")
        if self.re <= 1.5 * self.rw_eff:
            raise ValueError("re must exceed 1.5 times the effective well "
                             "radius rw*exp(-skin)")
        if self.co + self.cf <= 0.0:
            raise ValueError("Total compressibility co + cf must be positive")
        if self.pb >= self.pi:
            raise ValueError("pb must be below pi: a saturated reservoir "
                             "needs a multiphase model")

        self.check_well_control()

        if self.pe is None:
            self.pe = self.pi
        if self.p_top is None:
            self.p_top = self.pi
        if self.p_bot is None:
            self.p_bot = self.pi

        if self.pwf_floor >= self.pi:
            raise ValueError(
                f"Operating constraints leave no drawdown: pwf floor "
                f"{self.pwf_floor:.1f} psi ({self.floor_source}) is not "
                f"below pi")
        for c in self.checkpoints:
            if not 0.0 < c <= self.T:
                raise ValueError("Every checkpoint must be in (0, T]")
        return self
