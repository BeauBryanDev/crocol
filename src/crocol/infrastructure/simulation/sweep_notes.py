from crocol.infrastructure.simulation.schemas import SimulationInput
from crocol.infrastructure.simulation.sweep_models import SweepOptions


def recommended_notes(rec: dict, base_inp: SimulationInput) -> list[str]:
    notes = [
        f"Np(T) stops improving above about {rec['target']:,.0f} STB/d: "
        f"recovery is depletion-limited ({rec['rf']:.2%} of OOIP, "
        f"{rec['pct_of_limit']:.0%} of the material-balance limit). More "
        f"rate only advances production and raises drawdown, see "
        f"discounted_np_stb and t90_days."
    ]
    if rec["days_pwf_floor"] > 0.0:
        notes.append(
            f"At the recommended rate the plateau lasts "
            f"{rec['plateau_days']:.0f} days before the pwf floor "
            f"({base_inp.floor_source}, {base_inp.pwf_floor:.0f} psi) "
            f"takes control.")
    return notes


def discounted_note(disc: dict, rec: dict, opts: SweepOptions) -> str:
    return (
        f"Time value at {opts.discount_rate:.0%}/yr favors "
        f"{disc['target']:,.0f} STB/d (discounted Np "
        f"{disc['discounted_np_stb']:,.0f} STB against "
        f"{rec['discounted_np_stb']:,.0f} at the recommended rate, 90% of "
        f"the oil in {disc['t90_days']:.0f} days against "
        f"{rec['t90_days']:.0f}). Choose between them with the field's "
        f"economics and drawdown tolerance.")


def sweep_notes(base_inp: SimulationInput, 
                opts: SweepOptions,
                rec: dict | None,
                disc: dict | None,
                best_rate: dict | None, n_invalid: int
                ) -> list[str]:

    notes = []
    if rec is not None:
        notes.extend(recommended_notes(rec, base_inp))
        if disc is not None and disc["target"] > rec["target"]:
            notes.append(discounted_note(disc, rec, opts))

    q_max = base_inp.q_max
    if (q_max is not None and best_rate is not None
            and best_rate["target"] >= 0.999 * q_max):
        notes.append("The best rate equals q_max: the well is "
                     "facility-limited, not reservoir-limited.")
    if n_invalid:
        notes.append(f"{n_invalid} runs fell below the bubble point and "
                     f"were excluded.")
    notes.append(f"Skin is fixed at {base_inp.skin:g}: stimulation is an "
                 f"engineering decision, not part of this optimization.")
    return notes
