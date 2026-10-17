import re
from collections import defaultdict
from itertools import combinations

from config.roles import CONFLICT_PROPERTIES
from crocol.application.agent.schemas import (
    ConflictRecord,
    ConflictRecords,
    render_evidence,
)
from crocol.application.agent.state import AgentDeps, AgentState, ask
from crocol.domains.models.chunks import Chunk
from crocol.domains.services.citations import normalize_labels, render_citation
from crocol.domains.services.verification import number_tokens, readings

ENTITY_PREFIX_RE = re.compile(
    r"^(formaci[oó]n|formation|fm\.?|miembro|member|pozo|well|campo|field)"
    r"\s+",
    re.I,
)
PROPERTY_PATTERNS = (
    ("tmax", re.compile(r"\btmax\b|t\s*max")),
    ("ro", re.compile(r"\bro\b|\b%ro\b|vitrinit")),
    ("toc", re.compile(r"\btoc\b|carbono org|organic carbon")),
    ("thickness", re.compile(r"thickness|espesor")),
    ("porosity", re.compile(r"porosi")),
)
Interval = tuple[float, float]


def squeeze(text: str) -> str:

    return " ".join(text.split()).casefold()


def entity_key(entity: str) -> str:

    return ENTITY_PREFIX_RE.sub("", squeeze(entity)).strip()


def property_key(name: str) -> str:
    """Map a model's property label to a controlled code by keyword."""
    text = squeeze(name)
    for code, pattern in PROPERTY_PATTERNS:
        if pattern.search(text):
            return code

    return text


def intervals(value: str) -> list[Interval]:
    """Candidate [low, high] readings of a value or a range like 2-12."""
    tokens = number_tokens(value)
    if not tokens:
        return []
    if len(tokens) == 1:
        return [(v, v) for v in readings(tokens[0])]

    candidates = []
    for low in readings(tokens[0]):
        for high in readings(tokens[1]):
            candidates.append((min(low, high), max(low, high)))
    return candidates


def overlap(a: list[Interval], b: list[Interval]) -> bool:

    for low_a, high_a in a:
        for low_b, high_b in b:
            if low_a <= high_b and low_b <= high_a:
                return True
    return False


def side_of(record: ConflictRecord, chunk: Chunk) -> dict:

    return {
        "entity": record.entity.strip(),
        "value": record.value.strip(),
        "unit": record.unit.strip(),
        "label": chunk.label,
        "chunk_id": chunk.chunk_id,
        "doc_id": chunk.doc_id,
        "citation": render_citation(chunk.citation, chunk.page_start,
                                    chunk.page_end),
        "quote": record.quote.strip(),
    }


def grouped_sides(records: list[ConflictRecord],
                  evidence: list[Chunk]
                  ) -> dict[tuple[str, str], dict[str, dict]]:
    """Numeric records whose quote is verbatim in the cited chunk."""
    by_label = {c.label: c for c in evidence}
    groups: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)

    for record in records:
        prop = property_key(record.property)
        labels = normalize_labels([record.label])
        chunk = by_label.get(labels[0]) if labels else None
        if prop not in CONFLICT_PROPERTIES or chunk is None:
            continue
        if not record.quote.strip():
            continue
        if squeeze(record.quote) not in squeeze(chunk.text):
            continue
        if not intervals(record.value):
            continue
        key = (entity_key(record.entity), prop)
        groups[key].setdefault(chunk.doc_id, side_of(record, chunk))

    return groups


def find_conflicts(records: list[ConflictRecord],
                   evidence: list[Chunk]
                   ) -> list[dict]:
    """Different documents, non-overlapping values; units decide comparable."""
    conflicts = []
    for (_, prop), by_doc in grouped_sides(records, evidence).items():
        sides = list(by_doc.values())
        if len(sides) < 2:
            continue

        differ = False
        for a, b in combinations(sides, 2):
            if not overlap(intervals(a["value"]), intervals(b["value"])):
                differ = True
        if not differ:
            continue

        units = {squeeze(side["unit"]) for side in sides}
        conflicts.append({
            "entity": sides[0]["entity"],
            "property": prop,
            "comparable": len(units) == 1,
            "sides": sides,
        })

    return conflicts


async def conflict_check(state: AgentState,
                         deps: AgentDeps
                         ) -> tuple[dict, dict]:

    evidence = state.get("evidence") or []
    request = f"EVIDENCE:\n{render_evidence(evidence)}"
    parsed, usage = await ask(
        deps, "conflict", "investigator", request, ConflictRecords)

    records = parsed.records if isinstance(parsed, ConflictRecords) else []
    conflicts = find_conflicts(records, evidence)
    update = {
        "conflicts": conflicts,
        "llm_calls": 1,
        "llm_usage": [usage],
    }
    groups = grouped_sides(records, evidence)
    verified: dict[str, int] = {}
    for (_, prop), by_doc in groups.items():
        verified[prop] = verified.get(prop, 0) + len(by_doc)
    summary = {
        "records": len(records),
        "verified": verified,
        "conflicts": sum(1 for c in conflicts if c["comparable"]),
        "not_comparable": sum(1 for c in conflicts if not c["comparable"]),
        "cross_family": usage["cross_family"],
    }
    return update, summary
