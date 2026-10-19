import asyncio
import base64
import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from config.roles import (
    RECURSION_LIMIT,
    RESEARCH_MODE_ENABLED,
    TOTAL_TIMEOUT_S,
)
from config.settings import APP_VERSION, PIPELINE_VERSION
from crocol.application.agent.state import initial_state
from crocol.application.ports.trace_store import TraceStore
from crocol.domains.models.answers import Answer

LOGGER = logging.getLogger("crocol.usecases.ask")
JUDGE_ROLES = ("grade", "verify", "conflict")
TIMEOUT_TEXT = {
    "es": "No fue posible completar la respuesta dentro del tiempo límite.",
    "en": "The answer could not be completed within the time limit.",
}


def chunk_rows(state: dict, answer: Answer | None) -> list[dict]:
    """Retrieved, graded and cited chunk ids; never their text."""
    rows = []
    for rank, chunk in enumerate(state.get("chunks") or [], 1):
        rows.append({"stage": "retrieved", "chunk_id": chunk.chunk_id,
                     "channel": "fused", "rank": rank,
                     "score": chunk.score, "relevant": None})

    for rank, chunk in enumerate(state.get("evidence") or [], 1):
        rows.append({"stage": "graded", "chunk_id": chunk.chunk_id,
                     "channel": "fused", "rank": rank,
                     "score": chunk.score, "relevant": True})

    citations = answer.citations if answer else ()
    for rank, citation in enumerate(citations, 1):
        rows.append({"stage": "cited", "chunk_id": citation.chunk_id,
                     "channel": None, "rank": rank, "score": None,
                     "relevant": True})

    return rows


def conflicts_log(state: dict) -> list[dict]:
    """Property, comparability and chunk ids only; no quotes or values."""
    logged = []
    for conflict in state.get("conflicts") or []:
        logged.append({
            "property": conflict["property"],
            "comparable": conflict["comparable"],
            "chunk_ids": [side["chunk_id"] for side in conflict["sides"]],
        })
    return logged


def cross_family_of(usages: list[dict]) -> bool | None:

    judges = [u["cross_family"] for u in usages if u["role"] in JUDGE_ROLES]
    return all(judges) if judges else None


def verification_of(state: dict) -> dict:

    claims = state.get("claims") or []
    return {
        "verified": bool(state.get("verified")),
        "revised": bool(state.get("revised")),
        "claims": len(claims),
        "failing": sum(1 for c in claims if c.failing),
        "partial_evidence": bool(state.get("partial_evidence")),
    }


def record_of(trace_id: str,
              state: dict,
              answer: Answer | None,
              status: str,
              latency_ms: int
              ) -> dict:
    """The persisted app log: metrics and ids only, no user text."""
    usages = state.get("llm_usage") or []
    return {
        "trace_id": trace_id,
        "language": state.get("language"),
        "mode": state.get("mode", "quick"),
        "corpus_scope": state.get("corpus_scope"),
        "chunk_policy": state.get("chunk_policy"),
        "status": status,
        "attempts": state.get("attempts", 0),
        "llm_calls": state.get("llm_calls", 0),
        "tokens_in": sum(u["input_tokens"] for u in usages),
        "tokens_out": sum(u["output_tokens"] for u in usages),
        "latency_ms": latency_ms,
        "cross_family": cross_family_of(usages),
        "verification": verification_of(state),
        "conflicts": conflicts_log(state),
        "trace": [event.to_dict() for event in state.get("trace") or []],
        "pipeline_version": PIPELINE_VERSION,
        "app_version": APP_VERSION,
        "chunks": chunk_rows(state, answer),
    }


def timeout_answer(state: dict) -> Answer:

    language = state.get("language", "es")
    text = TIMEOUT_TEXT.get(language, TIMEOUT_TEXT["es"])
    return Answer(text=text, status="partial", partial=True)


def final_event(trace_id: str, answer: Answer, record: dict) -> dict:

    return {
        "event": "final",
        "trace_id": trace_id,
        "status": answer.status,
        "usage": {
            "llm_calls": record["llm_calls"],
            "tokens": record["tokens_in"] + record["tokens_out"],
        },
        "answer": answer.text,
        "citations": [c.rendered for c in answer.citations],
        "references": list(answer.references),
        "caveats": list(answer.caveats),
        "conflicts": list(answer.conflicts),
        "overlay_webp_b64": base64.b64encode(answer.overlay_webp).decode()
        if answer.overlay_webp else None,
        "production": list(answer.production),
    }


class AskQuestion:
    """Runs the agent graph, streams node events, saves the app log."""

    def __init__(self,
                 graph: Any,
                 traces: TraceStore | None = None
                 ) -> None:

        self._graph = graph
        self._traces = traces

    async def save(self, record: dict) -> None:

        if self._traces is None:
            return
        try:
            await self._traces.save(record)
        except Exception as exc:
            LOGGER.warning("trace %s not saved: %s", record["trace_id"],
                           type(exc).__name__)

    async def stream(self,
                     question: str,
                     image: bytes | None = None
                     ) -> AsyncIterator[dict]:

        trace_id = str(uuid.uuid4())
        state: dict = dict(initial_state(question, image))
        started = time.perf_counter()
        config = {"recursion_limit": RECURSION_LIMIT}
        budget = TOTAL_TIMEOUT_S["research" if RESEARCH_MODE_ENABLED
                                 else "quick"]
        seen = 0

        try:
            async with asyncio.timeout(budget):
                async for state in self._graph.astream(
                        state, config=config, stream_mode="values"):
                    events = state.get("trace") or []
                    for event in events[seen:]:
                        yield {"event": "node", **event.to_dict()}
                    seen = len(events)
            answer = state.get("answer") or timeout_answer(state)
        except TimeoutError:
            answer = timeout_answer(state)

        latency_ms = int((time.perf_counter() - started) * 1000)
        record = record_of(trace_id, state, answer, answer.status,
                           latency_ms)
        await self.save(record)
        yield final_event(trace_id, answer, record)

    async def ask(self,
                  question: str,
                  image: bytes | None = None) -> dict:

        final: dict = {}
        async for event in self.stream(question, image):
            final = event
        return final
