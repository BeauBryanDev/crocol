from langgraph.types import Send

from config.roles import (
    ALLOW_GENERAL_KNOWLEDGE,
    LLM_CALL_BUDGET,
    MAX_ATTEMPTS,
    RESEARCH_RESERVED_CALLS,
    VISION_LLM_CALLS,
)
from crocol.application.agent.state import (
    AgentState,
    graph_mentions,
    verify_failed,
)

RETRIEVERS = ["retrieve_text", "retrieve_spatial", "retrieve_graph",
              "retrieve_vision", "retrieve_production"]
SYNTHESIS_CALLS = 2
REVISION_CALLS = 2


def calls_left(state: AgentState) -> int:
    
    budget = LLM_CALL_BUDGET[state.get("mode", "quick")]
    if state.get("image"):
        budget += VISION_LLM_CALLS

    return budget - state.get("llm_calls", 0)


def without_evidence(state: AgentState) -> str:
    """Answer from general knowledge when allowed and affordable."""
    if ALLOW_GENERAL_KNOWLEDGE and calls_left(state) >= SYNTHESIS_CALLS:
        return "synthesize"
    return "abstain"


def after_analyze(state: AgentState) -> list[str]:

    if state.get("mode") == "research":
        return ["plan"]

    return list(RETRIEVERS)


def after_plan(state: AgentState) -> list[Send]:
    """One parallel investigate task per planned sub-question."""
    sends = []
    mentions = graph_mentions(state)
    for index, sub in enumerate(state.get("sub_questions") or []):
        sends.append(Send("investigate", {**sub, "index": index,
                                          "mentions": mentions}))

    return sends


def after_merge(state: AgentState) -> str:

    if not state.get("evidence"):
        return without_evidence(state)

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

    return without_evidence(state)


def after_rewrite(state: AgentState) -> list[str] | str:
    
    if state.get("repeated"):
        return without_evidence(state)
    
    return list(RETRIEVERS)


def after_verify(state: AgentState) -> str:
    """A missing draft (writer failed or timed out) is a partial answer."""
    draft = state.get("draft")
    if not draft:
        return "finalize"
    if draft.get("insufficient"):
        return "abstain"
    
    if state.get("verified") or verify_failed(state):
        return "finalize"
    
    if state.get("revised"):
        return "finalize"
    
    if calls_left(state) < REVISION_CALLS:
        return "finalize"
    
    return "revise"
