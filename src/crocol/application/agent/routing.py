from config.roles import LLM_CALL_BUDGET, MAX_ATTEMPTS
from crocol.application.agent.state import AgentState

RETRIEVERS = ["retrieve_text", "retrieve_spatial", "retrieve_graph"]
SYNTHESIS_CALLS = 2
REVISION_CALLS = 2


def calls_left(state: AgentState) -> int:
    budget = LLM_CALL_BUDGET[state.get("mode", "quick")]
    return budget - state.get("llm_calls", 0)


def after_analyze(state: AgentState) -> list[str]:
    return list(RETRIEVERS)


def after_grade(state: AgentState) -> str:
    """Synthesize, retry with a new strategy, abstain, or stop on budget."""
    grade = state.get("grade") or {}
    has_evidence = bool(state.get("evidence"))
    if grade.get("sufficient") and has_evidence:
        if calls_left(state) >= SYNTHESIS_CALLS:
            return "synthesize"
        return "finalize"
    if state.get("attempts", 0) >= MAX_ATTEMPTS:
        return "abstain"
    if calls_left(state) < 1 + 1 + SYNTHESIS_CALLS:
        return "abstain"
    return "rewrite"


def after_rewrite(state: AgentState) -> list[str] | str:
    if state.get("repeated"):
        return "abstain"
    return list(RETRIEVERS)


def after_verify(state: AgentState) -> str:
    draft = state.get("draft")
    if not draft or draft.get("insufficient"):
        return "abstain"
    if state.get("verified"):
        return "finalize"
    if state.get("revised"):
        return "finalize"
    if calls_left(state) < REVISION_CALLS:
        return "finalize"
    return "revise"
