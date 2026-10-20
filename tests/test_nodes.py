import pytest
from fakes import FakeDocuments, FakeLLM, FakeStore

from config.roles import PER_DOC_CAP
from crocol.application.agent.nodes import analyze as analyze_module
from crocol.application.agent.nodes.analyze import analyze
from crocol.application.agent.nodes.fuse import fuse_chunks
from crocol.application.agent.nodes.grade import grade
from crocol.application.agent.nodes.response import finalize
from crocol.application.agent.nodes.rewrite import rewrite
from crocol.application.agent.nodes.verify import verify
from crocol.application.agent.schemas import (
    Analysis,
    Grade,
    RewritePlan,
    Verification,
)
from crocol.application.agent.state import (
    AgentDeps,
    initial_state,
    strategy_of,
)
from crocol.domains.models.chunks import Chunk
from crocol.domains.models.claims import Claim
from crocol.domains.models.documents import Document


def chunk(chunk_id: str, doc_id: str, label: str = "", text: str = "t",
          page: int = 4) -> Chunk:
    return Chunk(chunk_id, doc_id, text, f"Autor {doc_id}, 2016",
                 page_start=page, page_end=page, label=label)


def deps_for(script: dict, documents: dict | None = None) -> AgentDeps:
    store = FakeStore([])
    docs = FakeDocuments(documents) if documents is not None else None
    return AgentDeps(llm=FakeLLM(script), store=store, documents=docs)


def test_fuse_dedupes_caps_per_document_and_labels() -> None:
    same_doc = [chunk(f"a{i}", "doc-a") for i in range(5)]
    other = [chunk("b1", "doc-b"), chunk("a0", "doc-a")]
    fused = fuse_chunks([same_doc, other])
    ids = [c.chunk_id for c in fused]
    assert len(ids) == len(set(ids))
    assert sum(1 for c in fused if c.doc_id == "doc-a") == PER_DOC_CAP
    assert [c.label for c in fused] == [f"C{i + 1}" for i in range(len(ids))]


@pytest.mark.anyio
async def test_analyze_falls_back_when_model_fails() -> None:
    state = initial_state("What controls La Luna maturity?")
    update, summary = await analyze(state, deps_for({"analyze": [None]}))
    assert summary["fallback"] is True
    assert update["language"] == "en"
    assert update["query_type"] == "cross_language"
    assert update["query_variants"] == ["What controls La Luna maturity?"]


@pytest.mark.anyio
async def test_rewrite_flags_a_repeated_strategy() -> None:
    state = initial_state("pregunta")
    state["strategies"] = [strategy_of(["pregunta"], "core",
                                       "prose_tables", "conceptual")]
    same = RewritePlan(variants=[], corpus_scope="core",
                       chunk_policy="prose_tables", query_type="conceptual",
                       reason="same")
    update, _ = await rewrite(state, deps_for({"rewrite": [same]}))
    assert update["repeated"] is True
    assert update["attempts"] == 1


@pytest.mark.anyio
async def test_rewrite_fallback_widens_scope() -> None:
    state = initial_state("pregunta")
    update, _ = await rewrite(state, deps_for({"rewrite": [None]}))
    assert update["corpus_scope"] == "all"
    assert update["repeated"] is False


@pytest.mark.anyio
async def test_grade_fails_closed_without_judge() -> None:
    state = initial_state("pregunta")
    state["chunks"] = [chunk("c1", "d1", "C1")]
    update, summary = await grade(state, deps_for({"grade": [None]}))
    assert update["grade"]["sufficient"] is False
    assert update["evidence"] == []
    assert summary["cross_family"] is False


@pytest.mark.anyio
async def test_verify_catches_invented_number_and_unknown_label() -> None:
    state = initial_state("pregunta")
    state["evidence"] = [chunk("c1", "d1", "C1", "Espesor de 300 m")]
    state["draft"] = {"text": "Espesor de 350 m [C1] y [C5].",
                      "cited": ["C1", "C5"], "insufficient": False}
    judge = Verification(claims=[])
    update, summary = await verify(state, deps_for({"verify": [judge]}))
    assert update["verified"] is False
    assert summary["failing"] == 2


@pytest.mark.anyio
async def test_finalize_renders_citations_from_metadata() -> None:
    state = initial_state("pregunta")
    state["evidence"] = [chunk("c1", "d1", "C1", page=41)]
    state["draft"] = {"text": "La Luna es roca generadora [C1].",
                      "cited": ["C1"], "insufficient": False}
    state["channels"] = {"graph": {"attempt": 0, "status": "skipped",
                                   "lists": [], "detail": ""}}
    documents = {"d1": Document("d1", "Autor d1, 2016", "Autor (2016). T.")}
    update, summary = await finalize(state, deps_for({}, documents))
    answer = update["answer"]
    assert answer.text == "La Luna es roca generadora (Autor d1, 2016, p. 41)."
    assert answer.references == ("Autor (2016). T.",)
    assert answer.status == "answered"
    assert answer.caveats == ()


@pytest.mark.anyio
async def test_grade_accepts_bracketed_labels_from_the_judge() -> None:
    state = initial_state("pregunta")
    state["chunks"] = [chunk("c1", "d1", "C1"), chunk("c2", "d2", "C2")]
    judge = Grade(relevant=["[C2]", "c1"], sufficient=True, missing="",
                  reason="ok")
    update, _ = await grade(state, deps_for({"grade": [judge]}))
    assert [c.label for c in update["evidence"]] == ["C1", "C2"]
    assert update["grade"]["sufficient"] is True


@pytest.mark.anyio
async def test_research_request_runs_quick_until_enabled(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(analyze_module, "RESEARCH_MODE_ENABLED", False)
    research = Analysis(language="es", mode="research", intents=["other"],
                        corpus_scope="core", chunk_policy="prose_tables",
                        query_type="conceptual", variants=[])
    state = initial_state("pregunta compuesta")
    update, summary = await analyze(state, deps_for({"analyze": [research]}))
    assert update["mode"] == "quick"
    assert summary["requested_mode"] == "research"


@pytest.mark.anyio
async def test_failing_number_is_flagged_not_cut_from_the_text() -> None:
    state = initial_state("pregunta")
    state["evidence"] = [chunk("c1", "d1", "C1", text="sísmica 3D en 2007")]
    state["draft"] = {"text": "En la década de 2000 hubo sísmica 3D [C1].",
                      "cited": ["C1"], "insufficient": False}
    state["claims"] = [Claim("2000", (), "unsupported", numeric=True)]
    update, _ = await finalize(state, deps_for({}))
    answer = update["answer"]
    assert "década de 2000" in answer.text
    assert any("2000" in caveat for caveat in answer.caveats)
