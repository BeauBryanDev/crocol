import asyncio
import json
from dataclasses import dataclass, field

import httpx
import pytest

from config.roles import FUSE_TOP, PER_DOC_CAP
from crocol.application.agent import research
from crocol.application.agent.graph import failed
from crocol.application.agent.nodes import rerank as rerank_node
from crocol.application.agent.nodes.rerank import final_cut, rerank_chunks
from crocol.application.agent.state import AgentDeps
from crocol.domains.models.chunks import Chunk
from crocol.infrastructure import reranker as cohere


def chunk(cid: str, doc: str = "d1", doc_type: str = "thesis") -> Chunk:
    return Chunk(chunk_id=cid, doc_id=doc, text=f"texto {cid}",
                 citation="Autor, 2020", doc_type=doc_type, heading_path="1. Sec")


@dataclass
class FakeReranker:
    order: list[str] | None = None
    fail: bool = False
    delay_s: float = 0.0
    calls: list[tuple[str, list[str]]] = field(default_factory=list)

    async def rerank(self, query: str, chunks: list[Chunk]) -> list[Chunk]:
        self.calls.append((query, [c.chunk_id for c in chunks]))
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        if self.fail:
            raise RuntimeError("cohere down")
        by_id = {c.chunk_id: c for c in chunks}
        ids = self.order or list(reversed(by_id))
        return [by_id[i] for i in ids]


def deps(reranker: FakeReranker | None) -> AgentDeps:
    return AgentDeps(llm=None, store=None, reranker=reranker)


def test_final_cut_pins_synthetic_caps_documents_and_relabels() -> None:
    graph = chunk("kg-1", "kg-formation", "graph_fact")
    prose = [chunk(f"p{i}", "d1") for i in range(5)] + [chunk("q1", "d2")]
    cut = final_cut([graph], prose)
    assert [c.chunk_id for c in cut] == ["kg-1", "p0", "p1", "p2", "q1"]
    assert [c.label for c in cut] == ["C1", "C2", "C3", "C4", "C5"]
    assert sum(c.doc_id == "d1" for c in cut) == PER_DOC_CAP


def test_final_cut_keeps_at_most_fuse_top() -> None:
    many = [chunk(f"p{i}", f"d{i}") for i in range(FUSE_TOP + 10)]
    assert len(final_cut([], many)) == FUSE_TOP


@pytest.mark.anyio
async def test_rerank_reorders_prose_and_keeps_synthetic_first() -> None:
    fake = FakeReranker(order=["b", "a"])
    spatial = chunk("spatial-1", "spatial-x", "spatial_query")
    chosen, summary = await rerank_chunks(
        "¿Casabe?", [chunk("a", "d1"), spatial, chunk("b", "d2")], deps(fake))
    assert [c.chunk_id for c in chosen] == ["spatial-1", "b", "a"]
    assert fake.calls == [("¿Casabe?", ["a", "b"])]
    assert summary["synthetic"] == 1 and "status" not in summary


@pytest.mark.anyio
async def test_rerank_failure_falls_back_to_fused_order() -> None:
    chunks = [chunk("a", "d1"), chunk("b", "d2")]
    chosen, summary = await rerank_chunks("q", chunks, deps(FakeReranker(fail=True)))
    assert [c.chunk_id for c in chosen] == ["a", "b"]
    assert summary["status"] == "fallback"
    assert summary["error"] == "RuntimeError"


@pytest.mark.anyio
async def test_rerank_timeout_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rerank_node, "RERANK_TIMEOUT_S", 0.01)
    chosen, summary = await rerank_chunks(
        "q", [chunk("a", "d1"), chunk("b", "d2")], deps(FakeReranker(delay_s=0.2)))
    assert [c.chunk_id for c in chosen] == ["a", "b"]
    assert summary["status"] == "fallback"


@pytest.mark.anyio
async def test_no_reranker_is_skipped_but_still_cut() -> None:
    many = [chunk(f"p{i}", f"d{i}") for i in range(FUSE_TOP + 5)]
    chosen, summary = await rerank_chunks("q", many, deps(None))
    assert summary["status"] == "skipped"
    assert len(chosen) == FUSE_TOP


@pytest.mark.anyio
async def test_cohere_adapter_maps_scores_and_sends_heading(
        monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(200, json={"results": [
            {"index": 1, "relevance_score": 0.9},
            {"index": 0, "relevance_score": 0.2}]})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(cohere.httpx, "AsyncClient",
                        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    adapter = cohere.CohereReranker("secret", "rerank-v4.0-fast", 3.0, 50)
    ranked = await adapter.rerank("roca generadora", [chunk("a"), chunk("b")])

    assert [c.chunk_id for c in ranked] == ["b", "a"]
    assert [c.score for c in ranked] == [0.9, 0.2]
    assert seen["auth"] == "Bearer secret"
    assert seen["body"]["model"] == "rerank-v4.0-fast"
    assert seen["body"]["documents"][0].startswith("1. Sec\ntexto a")


@pytest.mark.parametrize(("flags", "partial"), [
    ([True, True, False], False),
    ([True, False, False], True),
    ([False, False, False], True),
])
@pytest.mark.anyio
async def test_research_is_partial_only_when_most_subquestions_fail(
        flags: list[bool], partial: bool) -> None:
    results = [{"index": i, "evidence": [chunk(f"e{i}", f"d{i}")],
                "sufficient": ok, "missing": "" if ok else "algo"}
               for i, ok in enumerate(flags)]
    update, _ = await research.merge({"sub_results": results}, deps(None))
    assert update["partial_evidence"] is partial


def test_optional_nodes_never_make_an_answer_partial() -> None:
    update, _, status = failed("conflict_check", "timeout")
    assert status == "timeout" and "partial" not in update
    update, _, status = failed("synthesize", "timeout")
    assert update["partial"] is True
    update, _, status = failed("rerank", "RuntimeError")
    assert status == "error" and "partial" not in update


@pytest.mark.anyio
async def test_slow_grader_keeps_the_reranked_top(
        monkeypatch: pytest.MonkeyPatch) -> None:
    async def slow_grade(state: dict, deps: AgentDeps) -> tuple[dict, dict]:
        await asyncio.sleep(0.2)
        return {}, {}

    monkeypatch.setattr(research, "grade", slow_grade)
    monkeypatch.setattr(research, "INVESTIGATE_GRADE_TIMEOUT_S", 0.01)
    local = {"chunks": [chunk(f"p{i}", f"d{i}") for i in range(10)]}
    graded = await research.bounded_grade(local, deps(None))

    assert [c.chunk_id for c in graded["evidence"]] == [f"p{i}" for i in range(6)]
    assert graded["grade"]["sufficient"] is False
    assert graded["llm_calls"] == 1


def test_unverified_ai_reports_only_fill_leftover_slots() -> None:
    ai = [chunk(f"ai{i}", f"ai-doc{i}", "ai_research_report") for i in range(3)]
    genuine = [chunk(f"g{i}", f"d{i}") for i in range(FUSE_TOP)]
    cut = final_cut([], [*ai, *genuine])
    assert not any(c.doc_type == "ai_research_report" for c in cut)
    few = final_cut([], [*ai, chunk("g0", "d0")])
    assert [c.chunk_id for c in few] == ["g0", "ai0", "ai1", "ai2"]


def test_timed_out_verify_finalizes_with_a_note() -> None:
    from crocol.application.agent import routing
    state = {"draft": {"text": "x [C1]."}, "verified": False,
             "errors": ["verify: timeout"], "llm_calls": 0, "mode": "quick"}
    assert routing.after_verify(state) == "finalize"
