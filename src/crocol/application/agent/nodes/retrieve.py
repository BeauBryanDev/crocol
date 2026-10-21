import asyncio

from config.roles import RETRIEVE_LIMIT
from crocol.application.agent.state import (
    AgentDeps,
    AgentState,
    ChannelResult,
    graph_mentions,
)
from crocol.application.tools.graph_search import graph_search
from crocol.application.tools.production_search import (
    search_production_by_field,
    series_payload,
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
    """ANH database lookups: the well query and the places named."""
    places = state.get("places") or []
    well_query = state.get("well_query")
    if deps.spatial is None:
        return skipped(state, "spatial", "no spatial store configured")
    if not places and not well_query:
        return skipped(state, "spatial", "no place and no well query")

    try:
        chunks, calls = await spatial_search(
            deps.spatial, state.get("intents") or [], places, well_query)
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
    """Knowledge-graph evidence: linked chunks plus one facts passage each."""
    mentions = graph_mentions(state)
    if deps.graph is None:
        return skipped(state, "graph", "no graph store configured")
    if not mentions:
        return skipped(state, "graph", "the question names no entity")

    try:
        found = await graph_search(deps.graph, mentions,
                                   state.get("corpus_scope", "core"))
    except Exception as exc:
        failed = ChannelResult(attempt=state.get("attempts", 0),
                               status="error", lists=[],
                               detail=type(exc).__name__)
        return ({"channels": {"graph": failed}},
                {"status": "error", "error": type(exc).__name__})
    if not found.entities:
        return skipped(state, "graph", "no entity matched the graph")

    lists = [list(found.facts)]
    if found.chunks:
        lists.append(list(found.chunks))
    channel = ChannelResult(
        attempt=state.get("attempts", 0),
        status="ok",
        lists=lists,
        detail="",
    )
    summary = {
        "mentions": len(mentions),
        "resolved_kinds": sorted({e.kind for e in found.entities}),
        "chunks": len(found.chunks),
        "facts": len(found.facts),
    }
    return {"channels": {"graph": channel}}, summary


async def retrieve_production(
    state: AgentState,
    deps: AgentDeps,
) -> tuple[dict, dict]:
    """ANH monthly oil and gas production of the fields the question names."""
    if "production" not in (state.get("intents") or []):
        return skipped(state, "production", "not a production question")
    if deps.production is None:
        return skipped(state, "production", "no production store configured")
    mentions = graph_mentions(state)
    if not mentions:
        return skipped(state, "production", "the question names no field")

    try:
        found = await search_production_by_field(deps.production, mentions)
    except Exception as exc:
        failed = ChannelResult(attempt=state.get("attempts", 0),
                               status="error", lists=[],
                               detail=type(exc).__name__)
        return ({"channels": {"production": failed}},
                {"status": "error", "error": type(exc).__name__})
    if not found.series:
        return skipped(state, "production", "no field matched the ANH tables")

    channel = ChannelResult(
        attempt=state.get("attempts", 0),
        status="ok",
        lists=[list(found.chunks)],
        detail="",
    )
    update = {
        "channels": {"production": channel},
        "production": [series_payload(s) for s in found.series],
    }
    summary = {
        "series": len(found.series),
        "kinds": sorted({s.kind for s in found.series}),
        "oil_trends": [s.oil_trend.label for s in found.series],
        "gas_trends": [s.gas_trend.label for s in found.series],
    }
    return update, summary

