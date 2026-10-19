from collections import Counter
from dataclasses import replace

from config.roles import (
    CANDIDATE_PER_DOC_CAP,
    FUSE_TOP,
    PER_DOC_CAP,
    RERANK_CANDIDATES,
)
from crocol.application.agent.state import AgentDeps, AgentState
from crocol.domains.models.chunks import Chunk
from crocol.domains.services.fusion import rrf_merge


def current_lists(state: AgentState) -> list[list[Chunk]]:
    attempt = state.get("attempts", 0)
    lists: list[list[Chunk]] = []
    for channel in (state.get("channels") or {}).values():
        if channel["attempt"] == attempt and channel["status"] == "ok":
            lists.extend(channel["lists"])
    return lists


def fuse_chunks(lists: list[list[Chunk]],
                limit: int = FUSE_TOP,
                per_doc_cap: int = PER_DOC_CAP) -> list[Chunk]:
    """RRF across lists, one copy per chunk, per_doc_cap per document."""
    rows = []
    for ranked in lists:
        rows.append([{"id": c.chunk_id, "chunk": c} for c in ranked])
    merged = rrf_merge(rows, [1.0] * len(rows))

    per_doc: Counter = Counter()
    chosen: list[Chunk] = []
    for row in merged:
        chunk = row["chunk"]
        if per_doc[chunk.doc_id] >= per_doc_cap:
            continue
        per_doc[chunk.doc_id] += 1
        label = f"C{len(chosen) + 1}"
        chosen.append(replace(chunk, label=label, score=row["fused_score"]))
        if len(chosen) == limit:
            break
    return chosen


async def fuse(state: AgentState, deps: AgentDeps) -> tuple[dict, dict]:
    lists = current_lists(state)
    chunks = fuse_chunks(lists, RERANK_CANDIDATES, CANDIDATE_PER_DOC_CAP)
    summary = {
        "lists": len(lists),
        "chunks": len(chunks),
        "documents": len({c.doc_id for c in chunks}),
        "chunk_ids": [c.chunk_id for c in chunks],
    }
    return {"chunks": chunks}, summary
