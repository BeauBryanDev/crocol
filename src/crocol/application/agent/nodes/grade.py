from config.roles import CONTEXT_BUDGETS, SYNTH_MAX_CHUNKS
from crocol.application.agent.context import fit_evidence
from crocol.application.agent.schemas import Grade, render_evidence
from crocol.application.agent.state import AgentDeps, AgentState, ask
from crocol.domains.services.citations import normalize_labels

INSUFFICIENT = {
    "relevant": [],
    "sufficient": False,
    "missing": "no usable grade from the judge",
    "reason": "grader output missing or invalid",
}


def graded_chunks(state: AgentState) -> list:

    return fit_evidence(state.get("chunks") or [], CONTEXT_BUDGETS["grade"])


def grade_request(state: AgentState) -> str:
    return (
        f"QUESTION:\n{state['question']}\n\n"
        f"EVIDENCE:\n{render_evidence(graded_chunks(state))}"
    )


async def grade(state: AgentState,
                deps: AgentDeps) -> tuple[dict, dict]:
    
    chunks = state.get("chunks") or []
    if not chunks:
        verdict = {**INSUFFICIENT, 
                   "missing": "retrieval returned nothing"
                   }
        update = {"grade": verdict, "evidence": [], 
                  "partial_evidence": False
                  }
        return update, {"sufficient": False, 
                        "relevant": 0,
                        "llm": False}

    parsed, usage = await ask(
        deps, "grade", "grader", 
        grade_request(state),
        Grade)
    
    verdict = dict(INSUFFICIENT)
    
    if isinstance(parsed, Grade):
        verdict = parsed.model_dump()

    verdict["relevant"] = normalize_labels(verdict["relevant"])
    relevant = set(verdict["relevant"])
    evidence = [c for c in chunks if c.label in relevant]
    vision = [c for c in chunks if c.chunk_type == "vision"]
    others = [c for c in evidence if c.chunk_type != "vision"]
    evidence = (vision + others)[:SYNTH_MAX_CHUNKS]
    
    if not evidence:
        verdict["sufficient"] = False

    update = {
        "grade": verdict,
        "evidence": evidence,
        "partial_evidence": bool(evidence) and not verdict["sufficient"],
        "llm_calls": 1,
        "llm_usage": [usage],
    }
    summary = {
        "sufficient": verdict["sufficient"],
        "relevant": len(evidence),
        "partial_evidence": update["partial_evidence"],
        "cross_family": usage["cross_family"],
    }
    return update, summary
