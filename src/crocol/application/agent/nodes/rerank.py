import asyncio
import logging
from collections import Counter
from dataclasses import replace

from config.roles import FUSE_TOP, PER_DOC_CAP, RERANK_ENABLED, RERANK_TIMEOUT_S
from crocol.application.agent.state import AgentDeps, AgentState
from crocol.domains.models.chunks import Chunk

LOGGER = logging.getLogger("crocol.rerank")
# Database results, graph facts and crack measurements are not prose a
# reranker can judge; they keep their place at the front.
SYNTHETIC_TYPES = ("spatial_query", "graph_fact", "crack_model",
                   "visual_interpretation", "production_series")
# Unverified AI-generated reports (owner rule, 2026-10-16) only fill the
# slots left after every genuine source.
AI_REPORT = "ai_research_report"


def final_cut(synthetic: list[Chunk], prose: list[Chunk]) -> list[Chunk]:
    """Synthetic first, then verified prose, then unverified AI reports."""
    genuine = [c for c in prose if c.doc_type != AI_REPORT]
    unverified = [c for c in prose if c.doc_type == AI_REPORT]
    per_doc: Counter = Counter()
    chosen: list[Chunk] = []
    for chunk in [*synthetic, *genuine, *unverified]:
        if per_doc[chunk.doc_id] >= PER_DOC_CAP:
            continue
        per_doc[chunk.doc_id] += 1
        chosen.append(replace(chunk, label=f"C{len(chosen) + 1}"))
        if len(chosen) == FUSE_TOP:
            break
    return chosen


async def rerank_chunks(question: str, chunks: list[Chunk],
                        deps: AgentDeps) -> tuple[list[Chunk], dict]:
    """Rerank prose candidates; on any failure keep the fused order."""
    synthetic = [c for c in chunks if c.doc_type in SYNTHETIC_TYPES]
    prose = [c for c in chunks if c.doc_type not in SYNTHETIC_TYPES]
    summary = {"candidates": len(chunks), "synthetic": len(synthetic)}

    if not RERANK_ENABLED or deps.reranker is None or not prose:
        summary["status"] = "skipped"
        return final_cut(synthetic, prose), summary

    try:
        ranked = await asyncio.wait_for(deps.reranker.rerank(question, prose),
                                        timeout=RERANK_TIMEOUT_S)
    except Exception as exc:
        LOGGER.warning("rerank fell back to fused order: %s",
                       type(exc).__name__)
        summary.update(status="fallback", error=type(exc).__name__)
        return final_cut(synthetic, prose), summary

    chosen = final_cut(synthetic, ranked)
    kept = [c.score for c in chosen if c.doc_type not in SYNTHETIC_TYPES]
    summary["top_score"] = round(max(kept), 3) if kept else None
    summary["kept"] = len(chosen)
    return chosen, summary


async def rerank(state: AgentState,
                 deps: AgentDeps) -> tuple[dict, dict]:

    chunks, summary = await rerank_chunks(state["question"],
                                          state.get("chunks") or [], deps)
    return {"chunks": chunks}, summary
