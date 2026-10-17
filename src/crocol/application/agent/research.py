from dataclasses import replace

from config.roles import (
    MAX_SUBQUESTIONS,
    PER_DOC_CAP,
    RESEARCH_MAX_CHUNKS,
    RESEARCH_RESERVED_CALLS,
)
from crocol.application.agent.nodes.fuse import fuse_chunks
from crocol.application.agent.nodes.grade import grade
from crocol.application.agent.nodes.retrieve import search_variant
from crocol.application.agent.routing import calls_left
from crocol.application.agent.schemas import ResearchPlan, SubQuestion
from crocol.application.agent.state import AgentDeps, AgentState, ask
from crocol.domains.models.chunks import Chunk


def allowed_sub_questions(state: AgentState) -> int:
    """Sub-questions that fit the budget after plan, conflict, answer."""
    room = calls_left(state) - 1 - RESEARCH_RESERVED_CALLS

    return max(1, min(MAX_SUBQUESTIONS, room))


def fallback_plan(state: AgentState) -> list[SubQuestion]:

    return [SubQuestion(
        question=state["question"],
        corpus_scope=state.get("corpus_scope", "core"),
        chunk_policy=state.get("chunk_policy", "prose_tables"),
        query_type=state.get("query_type", "conceptual"),
    )]


def unique_sub_questions(subs: list[SubQuestion]) -> list[SubQuestion]:

    seen: set[str] = set()
    unique = []
    for sub in subs:
        key = sub.question.strip().casefold()
        if key and key not in seen:
            seen.add(key)
            unique.append(sub)

    return unique


async def plan(state: AgentState, deps: AgentDeps) -> tuple[dict, dict]:

    allowed = allowed_sub_questions(state)
    parsed, usage = await ask(
        deps, "plan", "planner", state["question"], ResearchPlan)

    subs: list[SubQuestion] = []
    if isinstance(parsed, ResearchPlan):
        subs = unique_sub_questions(parsed.sub_questions)
    fallback = not subs
    if fallback:
        subs = fallback_plan(state)

    subs = subs[:allowed]
    update = {
        "sub_questions": [sub.model_dump() for sub in subs],
        "llm_calls": 1,
        "llm_usage": [usage],
    }
    summary = {
        "sub_questions": len(subs),
        "allowed": allowed,
        "fallback": fallback,
    }
    return update, summary


async def investigate(sub: dict, deps: AgentDeps) -> tuple[dict, dict]:
    """One sub-question: retrieve, fuse and grade, with no retry."""
    local: AgentState = {
        "question": sub["question"],
        "query_variants": [sub["question"]],
        "corpus_scope": sub["corpus_scope"],
        "chunk_policy": sub["chunk_policy"],
        "query_type": sub["query_type"],
        "bm25_query": None,
        "attempts": 0,
    }
    found = await search_variant(local, deps, sub["question"])
    local["chunks"] = fuse_chunks([found])
    graded, _ = await grade(local, deps)

    result = {
        "index": sub["index"],
        "evidence": graded["evidence"],
        "sufficient": bool(graded["grade"]["sufficient"]),
        "missing": graded["grade"]["missing"],
    }
    update = {
        "sub_results": [result],
        "llm_calls": graded.get("llm_calls", 0),
        "llm_usage": graded.get("llm_usage", []),
    }
    summary = {
        "index": sub["index"],
        "hits": len(found),
        "relevant": len(result["evidence"]),
        "sufficient": result["sufficient"],
    }
    return update, summary


def sub_index(result: dict) -> int:

    return result["index"]


def merged_evidence(results: list[dict]) -> list[Chunk]:

    seen: set[str] = set()
    per_doc: dict[str, int] = {}
    merged: list[Chunk] = []
    for result in sorted(results, key=sub_index):
        for chunk in result["evidence"]:
            if chunk.chunk_id in seen:
                continue
            if per_doc.get(chunk.doc_id, 0) >= PER_DOC_CAP:
                continue
            seen.add(chunk.chunk_id)
            per_doc[chunk.doc_id] = per_doc.get(chunk.doc_id, 0) + 1
            merged.append(replace(chunk, label=f"C{len(merged) + 1}"))
            if len(merged) == RESEARCH_MAX_CHUNKS:
                return merged

    return merged


async def merge(state: AgentState, deps: AgentDeps) -> tuple[dict, dict]:

    results = state.get("sub_results") or []
    evidence = merged_evidence(results)
    complete = bool(results) and all(r["sufficient"] for r in results)
    missing = "; ".join(r["missing"] for r in results
                        if not r["sufficient"] and r["missing"])

    update = {
        "chunks": evidence,
        "evidence": evidence,
        "grade": {
            "relevant": [c.label for c in evidence],
            "sufficient": complete and bool(evidence),
            "missing": missing,
            "reason": "merged research evidence",
        },
        "partial_evidence": bool(evidence) and not complete,
    }
    summary = {
        "sub_results": len(results),
        "evidence": len(evidence),
        "documents": len({c.doc_id for c in evidence}),
        "partial_evidence": update["partial_evidence"],
    }
    return update, summary
