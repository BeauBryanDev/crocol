import asyncio
import hashlib
import re
from dataclasses import dataclass

from config.settings import (
    CORE_COLLECTIONS,
    KG_EVIDENCE_CHUNKS,
    KG_FACT_ROWS,
    KG_LABEL,
    KG_MAX_ENTITIES,
)
from crocol.application.ports.graph import GraphSearch
from crocol.domains.models.chunks import Chunk
from crocol.domains.models.graphs import GraphEntity

MIN_SCORE_KIND = 0.6
MIN_SCORE_ANY = 0.8
DOCUMENTS_SHOWN = 6
TITLE = "Crocol – grafo de conocimiento del VMM"
CUE_PREFIX_RE = re.compile(
    r"(?i)^(?:el |la |los |las )?(?:pozo|campo|formaci[oó]n|fm\.?|grupo|"
    r"miembro|falla|municipio|bloque|contrato|well|field|formation|group|"
    r"member|fault)\s+")
UNITS = ["formation", "member", "group"]
KIND_HINTS = {
    "formation": UNITS, "member": UNITS, "group": UNITS,
    "field": ["field"], "well": ["well"], "municipality": ["municipality"],
    "organization": ["organization"], "fault": ["fault"],
    "contract_area": ["contract_area", "contract"],
    "seismic_3d": ["seismic_3d"], "person": ["person"],
    "document": ["document"], "topic": ["topic"],
    "regulation": ["regulation"], "basin": ["basin"],
}
PHRASES = {
    ("in", "PART_OF"): "Incluye",
    ("out", "PART_OF"): "Hace parte de",
    ("out", "OVERLIES"): "Suprayace a (está encima de)",
    ("in", "OVERLIES"): "Infrayace a (está debajo de)",
    ("out", "EQUIVALENT_OF"): "Equivalente lateral de",
    ("in", "EQUIVALENT_OF"): "Equivalente lateral de",
    ("in", "IN_FIELD"): "Pozos del campo",
    ("out", "IN_FIELD"): "Pertenece al campo",
    ("out", "LOCATED_IN"): "Ubicado en el municipio",
    ("in", "LOCATED_IN"): "Pozos ubicados en el municipio",
    ("out", "OPERATED_BY"): "Operado por",
    ("in", "OPERATED_BY"): "Opera",
    ("out", "IN_CONTRACT"): "Atributo CONTRATO (ANH)",
    ("in", "IN_CONTRACT"): "Pozos o programas con este atributo CONTRATO",
    ("out", "IN_BASIN"): "En la cuenca",
    ("in", "IN_BASIN"): "Contiene",
    ("in", "DESCRIBES"): "Descrita en los metadatos de",
    ("out", "DESCRIBES"): "Describe las unidades",
    ("out", "AUTHORED_BY"): "Autores",
    ("in", "AUTHORED_BY"): "Autor de",
    ("out", "PUBLISHED_BY"): "Publicado por",
    ("in", "PUBLISHED_BY"): "Publicó",
    ("out", "ABOUT"): "Temas",
    ("in", "ABOUT"): "Documentos sobre el tema",
    ("in", "HOLDS"): "Contratista",
    ("out", "HOLDS"): "Titular de",
    ("out", "COVERS"): "Área contratada",
    ("in", "COVERS"): "Contrato",
    ("out", "GOVERNED_BY"): "Regido por",
    ("in", "GOVERNED_BY"): "Rige",
    ("out", "DESCRIBED_IN"): "Documento",
    ("in", "DESCRIBED_IN"): "Describe",
}
CO_MENTION = "Co-mencionado en el corpus con (co-ocurrencia, no relación geológica)"
PROPS = {
    "age": "Edad", "status": "Estado", "field": "Campo", "uwi": "UWI",
    "department": "Departamento", "acq_year": "Año de adquisición",
    "fault_type": "Tipo", "length_km": "Longitud (km)",
    "contract_type": "Tipo de contrato", "signing_date": "Firma",
    "contractor": "Contratista", "citation": "Cita", "year": "Año",
}


@dataclass(frozen=True)
class GraphFound:
    entities: tuple[GraphEntity, ...]
    chunks: tuple[Chunk, ...]
    facts: tuple[Chunk, ...]


def clean_name(name: str) -> str:

    return CUE_PREFIX_RE.sub("", name.strip())


def pick(rows: tuple[dict, ...], hint: str | None) -> GraphEntity | None:
    """Best match: the hinted kind at 0.6, any kind at 0.8."""
    wanted = KIND_HINTS.get(hint or "", None)
    for row in rows:
        kind_ok = wanted is None or row["kind"] in wanted
        if (kind_ok and row["score"] >= MIN_SCORE_KIND) or \
                row["score"] >= MIN_SCORE_ANY:
            return GraphEntity(row["entity_id"], 
                               row["kind"], 
                               row["name"],
                               float(row["score"]),
                               dict(row["props"] or {}))
    return None


async def resolve(graph: GraphSearch,
                  mentions: list[dict]) -> list[GraphEntity]:

    async def one(mention: dict) -> GraphEntity | None:
        result = await graph.run("resolve", {
            "name": clean_name(mention["name"]), "kinds": None,
            "max_rows": 5})
        return pick(result.rows, mention.get("kind"))

    found = await asyncio.gather(*[one(m) for m in mentions])
    unique: dict[int, GraphEntity] = {}
    for entity in found:
        if entity is not None:
            unique.setdefault(entity.entity_id, entity)
            
    return list(unique.values())[:KG_MAX_ENTITIES]


def fact_line(row: dict) -> str:

    phrase = PHRASES.get((row["direction"], row["rel"]))
    if row["rel"] == "CO_MENTIONED":
        phrase = CO_MENTION
        
    if phrase is None:
        phrase = f"{row['rel']} ({row['direction']})"
        
    names = ", ".join(row["names"])
    extra = row["total"] - len(row["names"])
    more = f" y {extra} más" if extra > 0 else ""
    
    return f"- {phrase} [{row['other_kind']}] ({row['total']}): {names}{more}"


def prop_lines(entity: GraphEntity) -> list[str]:

    lines = []
    for key, label in PROPS.items():
        value = entity.props.get(key)
        if value not in (None, ""):
            lines.append(f"{label}: {value}")
    return lines


def render_facts(entity: GraphEntity,
                 facts: tuple[dict, ...],
                 documents: tuple[dict, ...],
                 path: list[dict]
                 ) -> str:

    lines = [f"Grafo de conocimiento de Crocol ({KG_LABEL}): relaciones de "
             f"metadatos, atributos ANH y estratigrafía curada.",
             f"Entidad: {entity.name} (tipo: {entity.kind})."]
    lines.extend(prop_lines(entity))
    lines.extend(fact_line(row) for row in facts)
    
    if documents:
        cites = "; ".join(f"{d['citation']} ({d['chunks']} pasajes)"
                          for d in documents[:DOCUMENTS_SHOWN])
        
        lines.append(f"- Documentos del corpus que la mencionan: {cites}")
    if path:
        steps = [path[0]["name"]]
        for step in path[1:]:
            steps.append(f"—{step['rel']}→ {step['name']}")
        lines.append("- Ruta en el grafo: " + " ".join(steps))
    return "\n".join(lines)


def facts_chunk(entity: GraphEntity, text: str) -> Chunk:

    digest = hashlib.sha1(str(entity.entity_id).encode()).hexdigest()[:12]
    return Chunk(
        chunk_id=f"kg-{digest}",
        doc_id=f"kg-{entity.kind}",
        text=text,
        citation=KG_LABEL,
        title=TITLE,
        collection="Crocol_KG",
        doc_type="graph_fact",
        chunk_type="graph",
        heading_path=f"kg.facts/{entity.kind}",
    )


def chunk_from_row(row: dict, score: float) -> Chunk:

    return Chunk(
        chunk_id=row["chunk_id"], doc_id=row["doc_id"], text=row["text"],
        citation=row["citation"], title=row["title"],
        source_path=row["source_path"], collection=row["collection"],
        doc_type=row["doc_type"], chunk_type=row["chunk_type"],
        heading_path=row["heading_path"] or "",
        page_start=int(row["page_start"] or 0),
        page_end=int(row["page_end"] or 0), score=score)


async def evidence(graph: GraphSearch, entities: list[GraphEntity],
                   corpus_scope: str) -> list[Chunk]:

    core = corpus_scope != "all"
    ranked = await graph.run("evidence_chunks", {
        "ids": [e.entity_id for e in entities],
        "max_rows": KG_EVIDENCE_CHUNKS,
        "collections": list(CORE_COLLECTIONS) if core else None,
        "peripheral": not core})
    if not ranked.rows:
        return []
    scores = {r["chunk_id"]: float(r["score"]) for r in ranked.rows}
    texts = await graph.run("chunk_texts", {"chunk_ids": list(scores)})
    by_id = {row["chunk_id"]: row for row in texts.rows}
    return [chunk_from_row(by_id[cid], score)
            for cid, score in scores.items() if cid in by_id]


async def entity_facts(graph: GraphSearch, entity: GraphEntity,
                       path: list[dict]) -> Chunk:

    facts, documents = await asyncio.gather(
        graph.run("facts", {"entity_id": entity.entity_id,
                            "max_rows": KG_FACT_ROWS}),
        graph.run("entity_documents", {"entity_id": entity.entity_id,
                                       "max_rows": DOCUMENTS_SHOWN}))
    text = render_facts(entity, facts.rows, documents.rows, path)
    return facts_chunk(entity, text)


async def graph_search(graph: GraphSearch, mentions: list[dict],
                       corpus_scope: str) -> GraphFound:
    """Resolve mentions, then graph evidence chunks and fact passages."""
    entities = await resolve(graph, mentions)
    if not entities:
        return GraphFound((), (), ())

    path: list[dict] = []
    if len(entities) >= 2:
        result = await graph.run("path", {"a": entities[0].entity_id,
                                          "b": entities[1].entity_id,
                                          "max_depth": 3})
        path = list(result.rows)

    chunks, *facts = await asyncio.gather(
        evidence(graph, entities, corpus_scope),
        *[entity_facts(graph, e, path if i == 0 else [])
          for i, e in enumerate(entities)])
    
    return GraphFound(tuple(entities), tuple(chunks), tuple(facts))
