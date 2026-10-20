import dataclasses

from config.exceptions import CrocolError
from crocol.application.agent.schemas import SimulationAnswer, render_evidence
from crocol.application.agent.state import (
    AgentDeps,
    AgentState,
    ChannelResult,
    ask,
)
from crocol.application.tools.well_simulation import search_well_sweep
from crocol.domains.services.citations import cited_labels

LABEL = "C1"


def channel(status: str, detail: str = "") -> dict:
    result = ChannelResult(attempt=0, status=status, lists=[],
                           detail=detail)
    return {"channels": {"simulation": result}}


async def simulate(state: AgentState,
                   deps: AgentDeps) -> tuple[dict, dict]:
    """Rate and BHP sweep of the attached well; no model call."""
    if deps.simulation is None:
        return channel("skipped", "no simulator"), {"status": "skipped"}

    try:
        found = await search_well_sweep(deps.simulation,
                                        state["well_params"])
    except CrocolError as exc:
        update = channel("error", exc.public_message)
        update["errors"] = [f"simulate: {type(exc).__name__}"]
        return update, {"status": "error", "error": type(exc).__name__}

    chunk = dataclasses.replace(found.chunk, label=LABEL)
    update = {
        **channel("ok"),
        "chunks": [chunk],
        "evidence": [chunk],
        "simulation": found.result,
    }
    summary = {
        "cases": len(found.result["rows"]),
        "recommended": found.result["recommended_rate"] is not None,
    }
    return update, summary


def interpretation_request(state: AgentState) -> str:

    return (f"QUESTION:\n{state['question']}\n\n"
            f"EVIDENCE:\n{render_evidence(state['evidence'])}")


async def interpret(state: AgentState,
                    deps: AgentDeps) -> tuple[dict, dict]:
    """One Haiku call explains the sweep; it never recomputes numbers."""
    parsed, usage = await ask(deps, "interpret", "simulation_analyst",
                              interpretation_request(state),
                              SimulationAnswer)
    update: dict = {"llm_calls": 1, "llm_usage": [usage]}
    if not isinstance(parsed, SimulationAnswer):
        update["draft"] = None
        return update, {"ok": False}

    update["language"] = parsed.language
    update["draft"] = {
        "text": parsed.text,
        "cited": cited_labels(parsed.text),
        "insufficient": False,
    }
    summary = {
        "ok": True,
        "language": parsed.language,
        "chars": len(parsed.text),
    }
    return update, summary
