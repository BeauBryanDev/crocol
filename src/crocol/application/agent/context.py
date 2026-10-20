from config.roles import DIGEST_TOKENS, MEMORY_TOKENS, MIN_EVIDENCE_CHUNKS
from crocol.application.agent.schemas import chunk_header
from crocol.application.agent.state import AgentState
from crocol.domains.models.chunks import Chunk
from crocol.domains.services.token_budget import estimate, fit_count, fit_text

UI_LABELS = {
    "formation": "stratigraphic or map unit the user selected",
    "place": "place the user located on the map",
}


def one_line(text: str | None) -> str:

    return " ".join((text or "").split())


def turn_text(number: int, record: dict) -> str:

    lines = [
        f"TURN {number} ({record.get('kind', 'text')}):",
        f"User asked: {one_line(record.get('question'))}",
    ]
    standalone = one_line(record.get("standalone"))
    if standalone and standalone != one_line(record.get("question")):
        lines.append(f"Resolved as: {standalone}")
    if record.get("summary"):
        lines.append(f"Answer summary: {one_line(record['summary'])}")
    if record.get("entities"):
        lines.append("Entities: " + ", ".join(record["entities"]))

    facts = record.get("facts") or {}
    if facts:
        pairs = [f"{key}={value}" for key, value in facts.items()]
        lines.append("Facts: " + "; ".join(pairs))

    return "\n".join(lines)


def conversation(records: list[dict], budget: int = MEMORY_TOKENS) -> str:
    """Oldest turns are dropped first until the rest fits the budget."""
    turns = [turn_text(n, r) for n, r in enumerate(records, 1)]
    while turns and estimate("\n\n".join(turns)) > budget:
        turns.pop(0)

    return "\n\n".join(turns)


def ui_block(state: AgentState) -> str:

    ui = state.get("ui_context") or {}
    lines = []
    for key, label in UI_LABELS.items():
        value = one_line(ui.get(key))
        if value:
            lines.append(f"- {label}: {value}")

    return "UI CONTEXT:\n" + "\n".join(lines) + "\n\n" if lines else ""


def analysis_request(state: AgentState) -> str:
    """Haiku sees the full memory: it resolves follow-ups for everyone."""
    question = state["question"]
    history = conversation(state.get("history") or [])
    ui = ui_block(state)
    if not history and not ui:
        return question

    block = f"CONVERSATION (oldest first):\n{history}\n\n" if history else ""
    return f"{block}{ui}QUESTION:\n{question}"


def digest_block(state: AgentState) -> str:
    """Sonnet's short view of the conversation; never in research mode."""
    if state.get("mode") == "research" or not state.get("follows_up"):
        return ""

    lines = [f"FOLLOW-UP AS ASKED: {one_line(state.get('user_question'))}"]
    coverage = fit_text(one_line(state.get("prior_coverage")),
                        DIGEST_TOKENS)
    if coverage:
        lines.append(f"ALREADY COVERED IN EARLIER TURNS: {coverage}")

    return "CONVERSATION DIGEST:\n" + "\n".join(lines) + "\n\n"


def wellsim_history(state: AgentState) -> str:

    records = [r for r in state.get("history") or []
               if r.get("kind") == "wellsim"]
    history = conversation(records)
    if not history:
        return ""

    return f"EARLIER SIMULATIONS (oldest first):\n{history}\n\n"


def fit_evidence(chunks: list[Chunk], budget: int) -> list[Chunk]:
    """Best-ranked passages that fit; the lowest-ranked go first."""
    sizes = [estimate(f"{chunk_header(c)}\n{c.text}") for c in chunks]
    return chunks[:fit_count(sizes, budget, MIN_EVIDENCE_CHUNKS)]
