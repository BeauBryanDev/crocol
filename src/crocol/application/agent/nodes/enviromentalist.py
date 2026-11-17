from config.roles import CONTEXT_BUDGETS
from crocol.application.agent.context import fit_evidence
from crocol.application.agent.schemas import (
    EnvironmentalBrief,
    load_prompt,
    render_evidence,
)
from crocol.application.agent.state import AgentDeps, AgentState, ask
from crocol.domains.services.citations import normalize_labels
from crocol.domains.services.token_budget import estimate

PROMPT = "enviromentalist"
LANGUAGES = {
    "es": "Spanish",
    "en": "English",
}
SECTIONS = (
    ("ecosystems", "ECOSYSTEMS"),
    ("species", "SPECIES"),
    ("pressures", "PRESSURES AND IMPACTS"),
    ("processes", "RIVER PROCESSES"),
    ("governance", "GOVERNANCE"),
    ("risks", "RISKS AND GAPS"),
)


def brief_request(state: AgentState) -> str:

    language = LANGUAGES.get(state.get("language", "es"), "Spanish")
    header = (
        f"ANSWER LANGUAGE: {language}\n\n"
        f"QUESTION:\n{state['question']}\n\n"
    )
    fixed = estimate(load_prompt(PROMPT).text) + estimate(header)
    evidence = fit_evidence(state.get("evidence") or [],
                            CONTEXT_BUDGETS["environment"] - fixed)

    return f"{header}EVIDENCE:\n{render_evidence(evidence)}"


def brief_of(parsed: object, known: set[str]) -> dict | None:
    """The specialist's sections, with labels limited to real passages."""
    if not isinstance(parsed, EnvironmentalBrief):
        return None
    sections = {field: getattr(parsed, field).strip() for field, _ in SECTIONS}
    labels = [label for label in normalize_labels(parsed.labels) if label in known]

    return {**sections, "labels": labels}


def brief_block(brief: dict | None) -> str:
    """The brief as the writer sees it, before the EVIDENCE."""
    if not brief:
        return ""
    lines = ["ENVIRONMENTAL SPECIALIST BRIEF (analysis, not evidence):"]
    for field, title in SECTIONS:
        if brief.get(field):
            lines.append(f"{title}: {brief[field]}")

    return "\n".join(lines) + "\n\n"


async def environmentalist(state: AgentState,
                           deps: AgentDeps
                           ) -> tuple[dict, dict]:
    """Gemini's environmental reading of the graded evidence."""
    known = {chunk.label for chunk in state.get("evidence") or []}
    parsed, usage = await ask(deps, "environment", PROMPT,
                              brief_request(state), EnvironmentalBrief)
    brief = brief_of(parsed, known)

    update = {
        "environment_brief": brief,
        "briefed": True,
        "llm_calls": 1,
        "llm_usage": [usage],
    }
    summary = {
        "ok": brief is not None,
        "labels": brief["labels"] if brief else [],
        "chars": sum(len(brief[f]) for f, _ in SECTIONS) if brief else 0,
        "cross_family": usage["cross_family"],
    }
    return update, summary
