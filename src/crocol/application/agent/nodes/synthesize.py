from config.roles import ALLOW_GENERAL_KNOWLEDGE
from crocol.application.agent.schemas import DraftAnswer, render_evidence
from crocol.application.agent.state import AgentDeps, AgentState, ask
from crocol.domains.services.citations import cited_labels

LANGUAGES = {
    "es": "Spanish",
    "en": "English",
}


def partial_note(state: AgentState) -> str:

    if not state.get("evidence"):
        return "EVIDENCE STATUS: NONE\n\n"
    if not state.get("partial_evidence"):
        return ""

    missing = (state.get("grade") or {}).get("missing", "")
    return (
        "EVIDENCE STATUS: PARTIAL\n"
        f"NOT COVERED BY THE EVIDENCE: {missing}\n\n"
    )


def conflict_line(conflict: dict) -> str:

    sides = []
    for side in conflict["sides"]:
        sides.append(f"[{side['label']}] {side['value']} {side['unit']}")
    note = "" if conflict["comparable"] else " (NOT COMPARABLE: units differ)"
    return (f"- {conflict['entity']} / {conflict['property']}: "
            + " vs ".join(sides) + note)


def research_note(state: AgentState) -> str:

    subs = state.get("sub_questions") or []
    if state.get("mode") != "research" or not subs:
        return ""

    lines = ["MODE: RESEARCH REPORT", "SUB-QUESTIONS:"]
    for number, sub in enumerate(subs, 1):
        lines.append(f"{number}. {sub['question']}")
    conflicts = state.get("conflicts") or []
    if conflicts:
        lines.append("SOURCES DISAGREE (quotes verified):")
        for conflict in conflicts:
            lines.append(conflict_line(conflict))

    return "\n".join(lines) + "\n\n"


def synthesis_request(state: AgentState) -> str:
    
    language = LANGUAGES.get(state.get("language", "es"), "Spanish")
    
    return (
        f"ANSWER LANGUAGE: {language}\n"
        f"ALLOW_GENERAL_KNOWLEDGE: {str(ALLOW_GENERAL_KNOWLEDGE).lower()}\n\n"
        f"{partial_note(state)}"
        f"{research_note(state)}"
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
