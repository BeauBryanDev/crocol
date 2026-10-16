from config.roles import SYNTH_MAX_CHUNKS
from crocol.application.agent.schemas import Grade, render_evidence
from crocol.application.agent.state import AgentDeps, AgentState, ask

INSUFFICIENT = {
    "relevant": [],
    "sufficient": False,
    "missing": "no usable grade from the judge",
    "reason": "grader output missing or invalid",
}


def grade_request(state: AgentState) -> str:
    return (
        f"QUESTION:\n{state['question']}\n\n"
        f"EVIDENCE:\n{render_evidence(state.get('chunks') or [])}"
    )


async def grade(state: AgentState, deps: AgentDeps) -> tuple[dict, dict]:
    chunks = state.get("chunks") or []
    if not chunks:
        verdict = {**INSUFFICIENT, "missing": "retrieval returned nothing"}
        update = {"grade": verdict, "evidence": []}
        return update, {"sufficient": False, "relevant": 0, "llm": False}

    parsed, usage = await ask(
        deps, "grade", "grader", grade_request(state), Grade)
    verdict = dict(INSUFFICIENT)
    if isinstance(parsed, Grade):
        verdict = parsed.model_dump()

    relevant = set(verdict["relevant"])
    evidence = [c for c in chunks if c.label in relevant]
    evidence = evidence[:SYNTH_MAX_CHUNKS]
    if not evidence:
        verdict["sufficient"] = False

    update = {
        "grade": verdict,
        "evidence": evidence,
        "llm_calls": 1,
        "llm_usage": [usage],
    }
    summary = {
        "sufficient": verdict["sufficient"],
        "relevant": len(evidence),
        "cross_family": usage["cross_family"],
    }
    return update, summary
