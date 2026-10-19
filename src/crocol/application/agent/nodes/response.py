import re

from crocol.application.agent.state import AgentDeps, AgentState, verify_failed
from crocol.domains.models.answers import Answer
from crocol.domains.models.chunks import Chunk
from crocol.domains.models.citations import Citation
from config.settings import KG_LABEL
from crocol.domains.services.citations import (
    KG,
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
        "graph": "No se pudo consultar el grafo de conocimiento; la "
                 "respuesta usa las demás fuentes.",
        "kg_reference": "Crocol-KG-2026. Grafo de conocimiento de Crocol y "
                        "conocimiento general del modelo (no es un "
                        "documento del corpus).",
        "unverified_answer": "La verificación automática de las afirmaciones "
                             "no terminó a tiempo; las citas son las del "
                             "redactor.",
        "production": "Producción fiscalizada ANH 2025–2026: promedios "
                      "mensuales por día calendario (crudo en BPDC, gas en "
                      "MPCPDC); la tendencia la calcula Crocol por regresión "
                      "lineal.",
        "kg_note": "Las citas (Crocol-KG-2026) provienen del grafo de "
                   "conocimiento de Crocol o del conocimiento general del "
                   "modelo, no de un pasaje del corpus.",
        "spatial": "Datos espaciales de ANH-Informacion-Petrolera-2026: "
                   "municipio y campo según los atributos de los pozos (sin "
                   "polígonos); la sísmica es geometría de adquisición, no "
                   "interpretación del subsuelo.",
        "unverified": "Cifras sin respaldo en la evidencia:",
        "vision_model": "Mediciones del modelo MobileNetV2-UNet en píxeles "
                        "y ángulos en el marco de la imagen; la severidad "
                        "es heurística, no un estándar de ingeniería.",
        "vision_ai": "La descripción de la roca es una interpretación "
                     "visual de IA a partir de la foto, sin verificación "
                     "de campo.",
        "vision_failed": "No se pudo leer la imagen enviada (formato o "
                         "tamaño no admitido).",
        "spatial_failed": "No se pudo consultar la base de datos espacial; "
                          "la respuesta usa solo texto.",
        "removed": "Se retiraron afirmaciones que no pasaron la "
                   "verificación:",
        "partial_evidence": "Respuesta con evidencia parcial: el corpus "
                            "no cubre todos los aspectos de la pregunta.",
        "ai": "Parte de la evidencia proviene de informes generados por IA "
              "no verificados.",
    },
    "en": {
        "abstain": "I did not find enough evidence in the corpus to answer "
                   "this question.",
        "closest": "Closest sources found:",
        "partial": "Partial answer: a time or model-call limit was reached.",
        "graph": "The knowledge graph could not be queried; the answer "
                 "uses the other sources.",
        "kg_reference": "Crocol-KG-2026. Crocol knowledge graph and the "
                        "model's general knowledge (not a corpus "
                        "document).",
        "unverified_answer": "Automatic claim verification did not finish "
                             "in time; citations are the writer's.",
        "production": "ANH fiscalized production 2025–2026: monthly "
                      "averages per calendar day (oil in BPDC, gas in "
                      "MPCPDC); Crocol computes the trend by linear "
                      "regression.",
        "kg_note": "Citations (Crocol-KG-2026) come from the Crocol "
                   "knowledge graph or the model's general knowledge, not "
                   "from a corpus passage.",
        "spatial": "Spatial data from ANH-Informacion-Petrolera-2026: "
                   "municipality and field membership come from well "
                   "attributes (no polygons); seismic is acquisition "
                   "geometry, not subsurface interpretation.",
        "unverified": "Figures not supported by the evidence:",
        "vision_model": "MobileNetV2-UNet measurements are in pixels and "
                        "angles are in the image frame; severity is a "
                        "heuristic, not an engineering standard.",
        "vision_ai": "The rock description is an AI visual interpretation "
                     "of the photo, without field verification.",
        "vision_failed": "The attached image could not be read (unsupported "
                         "format or size).",
        "spatial_failed": "The spatial database could not be queried; the "
                          "answer uses text only.",
        "removed": "Claims that failed verification were removed:",
        "partial_evidence": "Answer based on partial evidence: the corpus "
                            "does not cover every aspect of the question.",
        "ai": "Some evidence comes from unverified AI-generated reports.",
    },
}
CLOSEST_SOURCES = 3
NUMBER_ONLY_RE = re.compile(r"^\d+(?:[.,]\d+)*$")


def messages(state: AgentState) -> dict[str, str]:
    return MESSAGES.get(state.get("language", "es"), MESSAGES["es"])


def closest_sources(state: AgentState) -> list[str]:
    seen: list[str] = []
    
    for chunk in state.get("chunks") or []:
        cite = render_citation(chunk.citation, 
                               chunk.page_start,
                               chunk.page_end)
        if cite not in seen:
            seen.append(cite)
            
        if len(seen) == CLOSEST_SOURCES:
            break
        
    return seen


async def abstain(state: AgentState,
                  deps: AgentDeps
                  ) -> tuple[dict, dict]:
    """ do not answer if retrieval returned nothing or verification failed """
    text = messages(state)["abstain"]
    sources = closest_sources(state)
    if sources:
        text = f"{text}\n\n{messages(state)['closest']} " + "; ".join(sources)
    draft = {"text": text, "cited": [], "insufficient": True}
    
    return {"draft": draft}, {"closest_sources": len(sources), "llm_calls": 1}


def drop_failing(text: str,
                 state: AgentState
                 ) -> tuple[str, list[str], list[str]]:
    """Remove failing sentence claims; bare numbers are only flagged."""
    removed, unverified = [], []
    for claim in state.get("claims") or []:
        if not claim.failing or not claim.text:
            continue
        
        if NUMBER_ONLY_RE.match(claim.text):
            unverified.append(claim.text)
            
        elif claim.text in text:
            text = text.replace(claim.text, "").strip()
            removed.append(claim.text)
            
    return text, removed, unverified


def citations_for(text: str, 
                  chunks: list[Chunk]) -> list[Citation]:
    by_label = {c.label: c for c in chunks}
    citations = []
    for label in cited_labels(text):
        if label == KG:
            citations.append(Citation(KG, "kg-general-knowledge", "kg",
                                      f"({KG_LABEL})"))
            continue
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
    titles = {c.doc_id: f"{c.citation}. {c.title}." for c in chunks}
    short = reference_list(titles.get(doc_id, "") for doc_id in doc_ids)
    if deps.documents is None or not doc_ids:
        return short

    try:
        documents = await deps.documents.get_many(doc_ids)
    except Exception:
        return short

    found = [documents[d].reference for d in doc_ids if d in documents]
    missing = [titles.get(d, "") for d in doc_ids if d not in documents]
    return reference_list([*found, *missing])


async def references_with_kg(state: AgentState,
                             citations: list[Citation],
                             chunks: list[Chunk],
                             deps: AgentDeps,
                             general: bool) -> list[str]:

    corpus = [c for c in citations if c.label != KG]
    references = await references_for(corpus, chunks, deps)
    if general:
        references = reference_list([*references,
                                     messages(state)["kg_reference"]])
    return references


def caveats_for(state: AgentState,
                removed: list[str],
                unverified: list[str],
                cited: list[Chunk],
                general: bool = False
                ) -> list[str]:
    
    text = messages(state)
    caveats = []
    channels = state.get("channels") or {}
    graph = channels.get("graph")
    if graph is not None and graph["status"] == "error":
        caveats.append(text["graph"])
    if general or any(c.doc_type == "graph_fact" for c in cited):
        caveats.append(text["kg_note"])
    if any(c.doc_type == "production_series" for c in cited):
        caveats.append(text["production"])
    if verify_failed(state):
        caveats.append(text["unverified_answer"])
    if any(c.doc_type == "spatial_query" for c in cited):
        caveats.append(text["spatial"])
    if state.get("partial"):
        caveats.append(text["partial"])
    if state.get("partial_evidence"):
        caveats.append(text["partial_evidence"])
    if removed:
        caveats.append(f"{text['removed']} " + " | ".join(removed))
    if unverified:
        caveats.append(f"{text['unverified']} " + ", ".join(unverified))
    if any(c.doc_type == "crack_model" for c in cited):
        caveats.append(text["vision_model"])
    if any(c.doc_type == "visual_interpretation" for c in cited):
        caveats.append(text["vision_ai"])
    vision = channels.get("vision")
    if vision is not None and vision["status"] == "error":
        caveats.append(text["vision_failed"])
    spatial = channels.get("spatial")
    if spatial is not None and spatial["status"] == "error":
        caveats.append(text["spatial_failed"])
    if any(c.doc_type == "ai_research_report" for c in cited):
        caveats.append(text["ai"])
        
    return caveats


def status_of(state: AgentState, draft: dict | None) -> str:
    if draft is None:
        return "partial"
    if draft.get("insufficient"):
        return "abstained"
    if state.get("partial") or state.get("partial_evidence"):
        return "partial"
    return "answered"


async def finalize(state: AgentState,
                   deps: AgentDeps
                   ) -> tuple[dict, dict]:
    """Citations from metadata, never from model text; caveats appended."""
    draft = state.get("draft")
    chunks = state.get("evidence") or state.get("chunks") or []
    
    text, removed, unverified = "", [], []
    
    if draft is not None:
        text, removed, unverified = drop_failing(draft["text"], state)
        
    if draft is None:
        sources = closest_sources(state)
        text = f"{messages(state)['partial']}\n\n{messages(state)['closest']} "
        text += "; ".join(sources)

    citations = citations_for(text, chunks)
    rendered = {c.label: c.rendered for c in citations}
    cited_ids = {c.chunk_id for c in citations}
    cited = [c for c in chunks if c.chunk_id in cited_ids]
    general = any(c.label == KG for c in citations)
    
    answer = Answer(
        text=replace_labels(text, rendered),
        status=status_of(state, draft),
        citations=tuple(citations),
        references=tuple(await references_with_kg(state, citations, 
                                                  chunks,
                                                  deps, general)),
        caveats=tuple(caveats_for(state, removed,
                                  unverified, cited,
                                  general)),
        conflicts=tuple(state.get("conflicts") or []),
        partial=bool(state.get("partial")) or draft is None,
        overlay_webp=state.get("overlay") or b"",
        production=tuple(state.get("production") or []),
    )
    summary = {
        "answer_status": answer.status,
        "citations": len(answer.citations),
        "references": len(answer.references),
        "removed_claims": len(removed),
    }
    return {"answer": answer}, summary
