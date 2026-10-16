from crocol.application.agent.state import AgentDeps, AgentState
from crocol.domains.models.answers import Answer
from crocol.domains.models.chunks import Chunk
from crocol.domains.models.citations import Citation
from crocol.domains.services.citations import (
    cited_labels,
    reference_list,
    render_citation,
    replace_labels,
)

MESSAGES = {
    "es": {
        "abstain": "No encontré evidencia suficiente en el corpus para "
                   "responder esta pregunta.",
        "closest": "Fuentes más cercanas encontradas:",
        "partial": "Respuesta parcial: se alcanzó un límite de tiempo o "
                   "de llamadas al modelo.",
        "skipped": "La búsqueda espacial y el grafo de conocimiento aún no "
                   "están disponibles; la respuesta usa solo texto.",
        "removed": "Se retiraron afirmaciones que no pasaron la "
                   "verificación:",
        "ai": "Parte de la evidencia proviene de informes generados por IA "
              "no verificados.",
    },
    "en": {
        "abstain": "I did not find enough evidence in the corpus to answer "
                   "this question.",
        "closest": "Closest sources found:",
        "partial": "Partial answer: a time or model-call limit was reached.",
        "skipped": "Spatial search and the knowledge graph are not available "
                   "yet; the answer uses text only.",
        "removed": "Claims that failed verification were removed:",
        "ai": "Some evidence comes from unverified AI-generated reports.",
    },
}
CLOSEST_SOURCES = 3


def messages(state: AgentState) -> dict[str, str]:
    return MESSAGES.get(state.get("language", "es"), MESSAGES["es"])


def closest_sources(state: AgentState) -> list[str]:
    seen: list[str] = []
    for chunk in state.get("chunks") or []:
        cite = render_citation(chunk.citation, chunk.page_start,
                               chunk.page_end)
        if cite not in seen:
            seen.append(cite)
        if len(seen) == CLOSEST_SOURCES:
            break
    return seen


async def abstain(state: AgentState,
                  deps: AgentDeps) -> tuple[dict, dict]:
    text = messages(state)["abstain"]
    sources = closest_sources(state)
    if sources:
        text = f"{text}\n\n{messages(state)['closest']} " + "; ".join(sources)
    draft = {"text": text, "cited": [], "insufficient": True}
    return {"draft": draft}, {"closest_sources": len(sources)}


def drop_failing(text: str, 
                 state: AgentState) -> tuple[str, list[str]]:
    removed = []
    for claim in state.get("claims") or []:
        if claim.failing and claim.text and claim.text in text:
            text = text.replace(claim.text, "").strip()
            removed.append(claim.text)
    return text, removed


def citations_for(text: str, 
                  chunks: list[Chunk]) -> list[Citation]:
    by_label = {c.label: c for c in chunks}
    citations = []
    for label in cited_labels(text):
        chunk = by_label.get(label)
        if chunk is None:
            continue
        rendered = render_citation(chunk.citation, chunk.page_start,
                                   chunk.page_end)
        citations.append(Citation(label, chunk.chunk_id, chunk.doc_id,
                                  rendered))
    return citations


async def references_for(
    citations: list[Citation],
    chunks: list[Chunk],
    deps: AgentDeps,
) -> list[str]:
    doc_ids = sorted({c.doc_id for c in citations})
    if deps.documents is not None and doc_ids:
        documents = await deps.documents.get_many(doc_ids)
        return reference_list(d.reference for d in documents.values())
    titles = {c.doc_id: f"{c.citation}. {c.title}." for c in chunks}
    return reference_list(titles.get(doc_id, "") for doc_id in doc_ids)


def caveats_for(state: AgentState,
                removed: list[str],
                cited: list[Chunk]
                ) -> list[str]:
    
    text = messages(state)
    caveats = []
    channels = state.get("channels") or {}
    if any(ch["status"] == "skipped" for ch in channels.values()):
        caveats.append(text["skipped"])
    if state.get("partial"):
        caveats.append(text["partial"])
    if removed:
        caveats.append(f"{text['removed']} " + " | ".join(removed))
    if any(c.doc_type == "ai_research_report" for c in cited):
        caveats.append(text["ai"])
    return caveats


def status_of(state: AgentState, draft: dict | None) -> str:
    if draft is None:
        return "partial"
    if draft.get("insufficient"):
        return "abstained"
    return "partial" if state.get("partial") else "answered"


async def finalize(state: AgentState,
                   deps: AgentDeps
                   ) -> tuple[dict, dict]:
    """Citations from metadata, never from model text; caveats appended."""
    draft = state.get("draft")
    chunks = state.get("evidence") or state.get("chunks") or []
    text, removed = "", []
    if draft is not None:
        text, removed = drop_failing(draft["text"], state)
    if draft is None:
        sources = closest_sources(state)
        text = f"{messages(state)['partial']}\n\n{messages(state)['closest']} "
        text += "; ".join(sources)

    citations = citations_for(text, chunks)
    rendered = {c.label: c.rendered for c in citations}
    cited_ids = {c.chunk_id for c in citations}
    cited = [c for c in chunks if c.chunk_id in cited_ids]
    answer = Answer(
        text=replace_labels(text, rendered),
        status=status_of(state, draft),
        citations=tuple(citations),
        references=tuple(await references_for(citations, chunks, deps)),
        caveats=tuple(caveats_for(state, removed, cited)),
        conflicts=tuple(state.get("conflicts") or []),
        partial=bool(state.get("partial")) or draft is None,
    )
    summary = {
        "answer_status": answer.status,
        "citations": len(answer.citations),
        "references": len(answer.references),
        "removed_claims": len(removed),
    }
    return {"answer": answer}, summary
