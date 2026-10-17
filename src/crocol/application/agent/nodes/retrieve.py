import asyncio

from config.roles import RETRIEVE_LIMIT
from crocol.application.agent.state import (
    AgentDeps,
    AgentState,
    ChannelResult,
)
from crocol.application.tools.spatial_search import spatial_search
from crocol.application.tools.text_search import text_search
from crocol.domains.models.chunks import Chunk


def chunk_from_row(row: dict) -> Chunk:
    meta = row.get("metadata") or {}
    return Chunk(
        chunk_id=row["id"],
        doc_id=meta.get("doc_id", ""),
        text=row.get("document") or "",
        citation=meta.get("citation", ""),
        title=meta.get("title", ""),
        source_path=meta.get("source_path", ""),
        collection=meta.get("collection", ""),
        doc_type=meta.get("doc_type", ""),
        chunk_type=meta.get("chunk_type", "text"),
        heading_path=meta.get("heading_path", ""),
        page_start=int(meta.get("page_start") or 0),
        page_end=int(meta.get("page_end") or 0),
        score=float(row.get("score") or 0.0),
    )


def skipped(state: AgentState,
            name: str, 
            detail: str
            ) -> tuple[dict, dict]:
    
    channel = ChannelResult(
        attempt=state.get("attempts", 0),
        status="skipped",
        lists=[],
        detail=detail,
    )
    return {"channels": {name: channel}}, {"status": "skipped"}


async def search_variant(
    state: AgentState,
    deps: AgentDeps,
    variant: str,
) -> list[Chunk]:
    
    bm25_query = None
    
    if state.get("query_type") == "cross_language":
        bm25_query = state.get("bm25_query")
        
    rows = await asyncio.to_thread(
        text_search,
        deps.store,
        variant,
        state.get("query_type", "conceptual"),
        bm25_query,
        state.get("corpus_scope", "core"),
        state.get("chunk_policy", "prose_tables"),
        None,
        RETRIEVE_LIMIT,
    )
    return [chunk_from_row(row) for row in rows]


async def retrieve_text(
    state: AgentState,
    deps: AgentDeps,
) -> tuple[dict, dict]:
    
    variants = state.get("query_variants") or [state["question"]]
    jobs = [search_variant(state, deps, v) for v in variants]
    lists = await asyncio.gather(*jobs)
    
    channel = ChannelResult(
        attempt=state.get("attempts", 0),
        status="ok",
        lists=list(lists),
        detail="",
    )
    summary = {
        "variants": len(variants),
        "hits": [len(found) for found in lists],
        "corpus_scope": state.get("corpus_scope"),
        "chunk_policy": state.get("chunk_policy"),
    }
    
    return {"channels": {"text": channel}}, summary


async def retrieve_spatial(
    state: AgentState,
    deps: AgentDeps,
) -> tuple[dict, dict]:
    """ANH database lookups for the places the question names."""
    places = state.get("places") or []
    if deps.spatial is None:
        return skipped(state, "spatial", "no spatial store configured")
    if not places:
        return skipped(state, "spatial", "the question names no place")

    try:
        chunks, calls = await spatial_search(
            deps.spatial, state.get("intents") or [], places)
    except Exception as exc:
        failed = ChannelResult(attempt=state.get("attempts", 0),
                               status="error", lists=[],
                               detail=type(exc).__name__)
        return ({"channels": {"spatial": failed}},
                {"status": "error", "error": type(exc).__name__})
    if not chunks:
        return skipped(state, "spatial", "no place matched the database")

    channel = ChannelResult(
        attempt=state.get("attempts", 0),
        status="ok",
        lists=[chunks],
        detail="",
    )
    keys = sorted({key for call in calls for key in call.arguments})
    summary = {
        "functions": [call.function for call in calls],
        "argument_keys": keys,
        "results": len(chunks),
    }

    return {"channels": {"spatial": channel}}, summary


async def retrieve_graph(
    state: AgentState,
    deps: AgentDeps,
) -> tuple[dict, dict]:
    
    return skipped(state, "graph", "knowledge graph arrives in Phase 3")
