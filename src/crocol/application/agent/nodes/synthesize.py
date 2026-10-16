from config.roles import ALLOW_GENERAL_KNOWLEDGE
from crocol.application.agent.schemas import DraftAnswer, render_evidence
from crocol.application.agent.state import AgentDeps, AgentState, ask
from crocol.domains.services.citations import cited_labels

LANGUAGES = {
    "es": "Spanish",
    "en": "English",
}


def synthesis_request(state: AgentState) -> str:
    
    language = LANGUAGES.get(state.get("language", "es"), "Spanish")
    
    return (
        f"ANSWER LANGUAGE: {language}\n"
        f"ALLOW_GENERAL_KNOWLEDGE: {str(ALLOW_GENERAL_KNOWLEDGE).lower()}\n\n"
        f"QUESTION:\n{state['question']}\n\n"
        f"EVIDENCE:\n{render_evidence(state.get('evidence') or [])}"
    )


def revision_request(state: AgentState) -> str:
    draft = state.get("draft") or {}
    failing = []
    for claim in state.get("claims") or []:
        if claim.failing:
            failing.append(f"- ({claim.verdict}) {claim.text}")
    return (
        f"{synthesis_request(state)}\n\n"
        f"TASK: REVISE\n"
        f"PREVIOUS ANSWER:\n{draft.get('text', '')}\n\n"
        f"CLAIMS THAT FAILED VERIFICATION:\n" + "\n".join(failing)
    )


def draft_update(
    parsed: DraftAnswer | None,
    usage: dict,
) -> tuple[dict, dict]:
    
    draft = None
    if isinstance(parsed, DraftAnswer):
        draft = parsed.model_dump()
        draft["cited"] = cited_labels(draft["text"])
        
    update = {
            "draft": draft, 
            "llm_calls": 1,
            "llm_usage": [usage]
            }
    
    summary = {
        "ok": draft is not None,
        "cited": draft["cited"] if draft else [],
        "insufficient": bool(draft and draft["insufficient"]),
        "chars": len(draft["text"]) if draft else 0,
    }
    return update, summary


async def synthesize(state: AgentState, 
                     deps: AgentDeps
                     ) -> tuple[dict, dict]:
    
    parsed, usage = await ask(
        deps, "synthesize",
        "synthesizer", 
        synthesis_request(state),
        DraftAnswer)
    
    return draft_update(parsed, usage)


async def revise(state: AgentState, 
                 deps: AgentDeps
                 ) -> tuple[dict, dict]:
    
    parsed, usage = await ask(
        deps, "revise", "synthesizer",
        revision_request(state), 
        DraftAnswer)
    
    update, summary = draft_update(parsed, usage)
    
    if update["draft"] is None:
        update["draft"] = state.get("draft")
        
    update["revised"] = True
    
    return update, summary
