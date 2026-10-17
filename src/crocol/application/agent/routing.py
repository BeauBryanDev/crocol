from langgraph.types import Send

from config.roles import (
    LLM_CALL_BUDGET,
    MAX_ATTEMPTS,
    RESEARCH_RESERVED_CALLS,
    VISION_LLM_CALLS,
)
from crocol.application.agent.state import AgentState

RETRIEVERS = ["retrieve_text", "retrieve_spatial", "retrieve_graph",
              "retrieve_vision"]
SYNTHESIS_CALLS = 2
REVISION_CALLS = 2


def calls_left(state: AgentState) -> int:
    
    budget = LLM_CALL_BUDGET[state.get("mode", "quick")]
    if state.get("image"):
        budget += VISION_LLM_CALLS

    return budget - state.get("llm_calls", 0)


def after_analyze(state: AgentState) -> list[str]:

    if state.get("mode") == "research":
        return ["plan"]

    return list(RETRIEVERS)


def after_plan(state: AgentState) -> list[Send]:
    """One parallel investigate task per planned sub-question."""
    sends = []
    for index, sub in enumerate(state.get("sub_questions") or []):
        sends.append(Send("investigate", {**sub, "index": index}))

    return sends


def after_merge(state: AgentState) -> str:

    if not state.get("evidence"):
        return "abstain"

    if calls_left(state) >= RESEARCH_RESERVED_CALLS:
        return "conflict_check"

    if calls_left(state) >= SYNTHESIS_CALLS:
        return "synthesize"

    return "finalize"


def after_grade(state: AgentState) -> str:
    """Synthesize, retry with a new strategy, abstain, or stop on budget."""
    grade = state.get("grade") or {}
    has_evidence = bool(state.get("evidence"))
    
    if grade.get("sufficient") and has_evidence:
        
        if calls_left(state) >= SYNTHESIS_CALLS:
            return "synthesize"
        
        return "finalize"
    
    can_retry = state.get("attempts", 0) < MAX_ATTEMPTS
    if can_retry and calls_left(state) >= 1 + 1 + SYNTHESIS_CALLS:
        return "rewrite"

    if has_evidence and calls_left(state) >= SYNTHESIS_CALLS:
        return "synthesize"

    return "abstain"


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
