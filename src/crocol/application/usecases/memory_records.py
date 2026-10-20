from typing import Any

from config.settings import MEMORY_FIELD_CHARS

MAX_ENTITIES = 8
VERSION = 1


def clip(text: str | None) -> str:

    text = " ".join((text or "").split())
    return text[:MEMORY_FIELD_CHARS]


def kind_of(state: dict) -> str:

    if state.get("well_params"):
        return "wellsim"
    if state.get("vision_report") is not None:
        return "image"
    return "text"


def image_facts(report: Any) -> dict[str, str]:
    """Strings only: a JSON round trip in the browser keeps them exact."""
    return {
        "severity": str(report.severity),
        "density_pct": f"{report.density_pct:.2f}",
        "fractal_dimension": f"{report.fractal_dimension:.3f}",
        "crack_count": str(report.crack_count),
        "mean_width_px": f"{report.mean_width_px:.1f}",
    }


def wellsim_facts(result: dict) -> dict[str, str]:

    facts = {
        "pwf_floor_psi": f"{result['inputs']['pwf_floor_psi']:.0f}",
        "pb_psi": f"{result['well']['pb']:g}",
    }
    best = result.get("recommended_rate")
    if best:
        facts["recommended_rate_stb_d"] = f"{best['target']:.1f}"
        facts["recommended_np_stb"] = f"{best['np_stb']:.0f}"
        facts["recommended_pwf_final_psi"] = f"{best['pwf_final_psi']:.0f}"

    return facts


def facts_of(state: dict, kind: str) -> dict[str, str]:

    if kind == "image":
        return image_facts(state["vision_report"])
    if kind == "wellsim" and state.get("simulation"):
        return wellsim_facts(state["simulation"])
    return {}


def entity_names(state: dict) -> list[str]:

    names = []
    for item in state.get("entities") or []:
        name = clip(item.get("name"))[:80]
        if name and name not in names:
            names.append(name)

    return names[:MAX_ENTITIES]


def memory_record(state: dict, now: int) -> dict:
    """What the next turn may recall; held by the browser, signed, unsaved."""
    kind = kind_of(state)
    draft = state.get("draft") or {}
    return {
        "v": VERSION,
        "ts": now,
        "kind": kind,
        "language": state.get("language", "es"),
        "question": clip(state.get("user_question") or state["question"]),
        "standalone": clip(state["question"]),
        "summary": clip(draft.get("summary")),
        "entities": entity_names(state),
        "facts": facts_of(state, kind),
    }
