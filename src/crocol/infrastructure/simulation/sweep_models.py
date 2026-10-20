from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from crocol.infrastructure.simulation.results import ASSUMPTIONS

COLUMNS = ("control", "target", "np_stb", "rf", "pct_of_limit",
           "plateau_days", "days_pwf_floor", "days_q_cap", "t_end_days",
           "ended_by", "q_30d_stb_d", "q_final_stb_d", "pwf_final_psi",
           "drawdown_max_psi", "discounted_np_stb", "t90_days", "limit",
           "valid")

TABLE_HEAD = ("control", "target", "Np (STB)", "RF %", "% limit",
              "plateau d", "end d", "ended", "q30 STB/d", "max dd psi",
              "disc Np", "t90 d", "limit")

RECOMMENDATION_RULE = (
    "recommended_rate is the lowest rate whose Np at the horizon is within "
    "`tolerance` of the best rate. Above it, extra rate adds no recovery, "
    "it only advances production and raises drawdown."
)


def default_controls() -> list[str]:
    return ["rate", "bhp"]


class SweepOptions(BaseModel):
    """Search options; reservoir, well and constraints come from the well."""

    model_config = ConfigDict(extra="forbid")

    controls: list[Literal["rate", "bhp"]] = Field(
        default_factory=default_controls, 
        min_length=1, 
        max_length=2,
        description="Controls to sweep over: rate and bhp")
    n_rate: int = Field(10, ge=3, le=20, description="Coarse rate grid size")
    n_bhp: int = Field(8, ge=3, le=15, description="BHP grid size")
    rate_min: Optional[float] = Field(
        None, gt=0, description="Lowest rate to try (STB/d)")
    rate_max: Optional[float] = Field(
        None, gt=0, description="Highest rate to try (STB/d)")
    tolerance: float = Field(
        0.01, gt=0, le=0.1, description="Recovery tolerance for the knee")
    refine_rounds: int = Field(
        2, ge=0, le=3, description="Refinement rounds around the knee")
    discount_rate: float = Field(
        0.10, ge=0, le=1.0, description="Annual discount rate")

    @model_validator(mode="after")
    def check_range(self) -> "SweepOptions":
        """Check the range of the rates."""
        both = self.rate_min is not None and self.rate_max is not None
        if both and self.rate_min >= self.rate_max:
            raise ValueError("rate_min must be below rate_max")
        """Check the controls."""
        if len(set(self.controls)) != len(self.controls):
            raise ValueError("controls must not repeat")
        return self # Return the sweep options


def sweep_tool_spec() -> dict[str, Any]:
    return {
        "name": "run_well_sweep",
        "description": (
            "Run the well simulator over a grid of rate and bottomhole-"
            "pressure controls for the current well and return a table of " # Description
            "cumulative oil (Np) at the horizon, recovery factor, plateau, "
            "drawdown and binding constraints. Reservoir properties, skin "
            "and operating constraints are fixed by the session. Use it to " # Description
            "find the rate that maximizes recovery, narrowing rate_min and " # Description
            "rate_max on later calls."), # Description
        "input_schema": SweepOptions.model_json_schema(),
    }


def rounded(row: dict | None) -> dict | None:
    if row is None:
        return None
    out = {}
    for key, value in row.items():
        if not isinstance(value, float):
            out[key] = value
        elif key == "rf":
            out[key] = round(value, 6)
        elif key == "pct_of_limit":
            out[key] = round(value, 4)
        else:
            out[key] = round(value, 2)
    return out


def num(value: float | None, fmt: str) -> str:
    return "-" if value is None else format(value, fmt)


def table_line(r: dict) -> str:
    limit = r["limit"] if r["valid"] else r["limit"] + " INVALID"
    cells = [
        r["control"],
        num(r["target"], ",.1f"),
        num(r["np_stb"], ",.0f"),
        num(100 * r["rf"], ".2f"),
        num(100 * r["pct_of_limit"], ".1f"),
        num(r["plateau_days"], ".1f"),
        num(r["t_end_days"], ".1f"),
        r["ended_by"],
        num(r["q_30d_stb_d"], ",.0f"),
        num(r["drawdown_max_psi"], ".0f"),
        num(r["discounted_np_stb"], ",.0f"),
        num(r["t90_days"], ".1f"),
        limit,
    ]
    return "| " + " | ".join(cells) + " |"


@dataclass
class SweepResult:
    options: SweepOptions
    inputs: dict
    bounds: dict
    rows: list
    best_overall: dict
    best_rate: Optional[dict]
    best_bhp: Optional[dict]
    recommended_rate: Optional[dict]
    best_discounted_rate: Optional[dict]
    notes: list
    curves: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        rows = [rounded(r) for r in self.rows] # Rounded rows
        horizon = self.inputs["horizon_days"]
        return { # Return the dictionary
            "objective": f"maximize Np at the horizon of {horizon:g} days",
            "inputs": self.inputs,
            "bounds": self.bounds,
            "columns": list(COLUMNS),
            "rows": [[r[c] for c in COLUMNS] for r in rows],
            "best_overall": rounded(self.best_overall),
            "best_rate": rounded(self.best_rate),
            "best_bhp": rounded(self.best_bhp),
            "recommended_rate": rounded(self.recommended_rate),
            "best_discounted_rate": rounded(self.best_discounted_rate),
            "recommendation_rule": RECOMMENDATION_RULE,
            "notes": self.notes,
            "assumptions": list(ASSUMPTIONS),
        }

    def to_markdown(self) -> str:
        lines = ["| " + " | ".join(TABLE_HEAD) + " |",
                 "|" + "---|" * len(TABLE_HEAD)]
        for r in self.rows:
            lines.append(table_line(r))
        return "\n".join(lines)
