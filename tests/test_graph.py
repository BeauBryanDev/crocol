import pytest
from fakes import FakeLLM, FakeStore, row

from config.roles import LLM_CALL_BUDGET, MAX_ATTEMPTS, RECURSION_LIMIT
from crocol.application.agent import routing
from crocol.application.agent.graph import build_graph
from crocol.application.agent.schemas import (
    Analysis,
    ClaimCheck,
    DraftAnswer,
    Grade,
    RewritePlan,
    Verification,
)
from crocol.application.agent.state import AgentDeps, initial_state

ROWS = [
    row("c1", "d1", "La Formación Mugrosa se depositó en ríos meándricos.",
        "Prada Gómez & Salcedo Rodríguez, 2018", page=17),
    row("c2", "d2", "Ambiente fluvial con canales y llanuras de inundación.",
        "Rueda Acevedo, 2016", page=41),
]
ANALYSIS = Analysis(language="es", mode="quick", intents=["conceptual"],
                    corpus_scope="core", chunk_policy="prose_tables",
                    query_type="conceptual", variants=["ambiente Mugrosa"])
SUFFICIENT = Grade(relevant=["C1", "C2"], sufficient=True, missing="",
                   reason="ok")
INSUFFICIENT = Grade(relevant=[], sufficient=False, missing="ambiente",
                     reason="no")
DRAFT = DraftAnswer(text="Mugrosa es fluvial meándrica [C1, C2].",
                    cited=["C1", "C2"])
PASSED = Verification(claims=[ClaimCheck(
    claim="Mugrosa es fluvial meándrica", labels=["C1"],
    verdict="supported")])
FAILED = Verification(claims=[ClaimCheck(
    claim="Mugrosa tiene 900 m", labels=[], verdict="contradicted",
    numeric=True)])


def plan(scope: str, query_type: str) -> RewritePlan:
    return RewritePlan(variants=[f"variante {scope} {query_type}"],
                       corpus_scope=scope, chunk_policy="prose_tables",
                       query_type=query_type, reason="new")


async def run(script: dict) -> tuple[dict, FakeLLM]:
    llm = FakeLLM(script)
    graph = build_graph(AgentDeps(llm=llm, store=FakeStore(ROWS)))
    config = {"recursion_limit": RECURSION_LIMIT}
    final = await graph.ainvoke(initial_state("¿Ambiente de Mugrosa?"),
                                config=config)
    return final, llm


def nodes(final: dict) -> list[str]:
    return [event.node for event in final["trace"]]


@pytest.fixture
def loop_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    budget = {"quick": 12, "research": 24}
    monkeypatch.setattr(routing, "LLM_CALL_BUDGET", budget)


@pytest.mark.anyio
@pytest.mark.usefixtures("corpus_only")
async def test_default_budget_insufficient_abstains_without_retry() -> None:
    final, llm = await run({"analyze": [ANALYSIS], "grade": [INSUFFICIENT]})
    assert final["answer"].status == "abstained"
    assert llm.roles() == ["analyze", "grade"]
    assert final["llm_calls"] <= LLM_CALL_BUDGET["quick"]


@pytest.mark.anyio
async def test_default_budget_failed_verification_drops_claims() -> None:
    failing = Verification(claims=[ClaimCheck(
        claim="Mugrosa es fluvial meándrica", labels=["C1"],
        verdict="contradicted")])
    final, llm = await run({"analyze": [ANALYSIS], "grade": [SUFFICIENT],
                            "synthesize": [DRAFT], "verify": [failing]})
    assert "revise" not in llm.roles()
    assert final["llm_calls"] == LLM_CALL_BUDGET["quick"]
    assert "Mugrosa es fluvial meándrica" not in final["answer"].text
    assert final["answer"].caveats


@pytest.mark.anyio
async def test_first_pass_answer_with_rendered_citations() -> None:
    final, llm = await run({"analyze": [ANALYSIS], "grade": [SUFFICIENT],
                            "synthesize": [DRAFT], "verify": [PASSED]})
    answer = final["answer"]
    assert answer.status == "answered"
    assert "(Prada Gómez & Salcedo Rodríguez, 2018, p. 17; " in answer.text
    assert "[C" not in answer.text
    assert llm.roles() == ["analyze", "grade", "synthesize", "verify"]
    statuses = {e.node: e.status for e in final["trace"]}
    assert statuses["retrieve_spatial"] == "skipped"
    assert statuses["retrieve_graph"] == "skipped"
    assert statuses["finalize"] == "ok"
    assert nodes(final)[-1] == "finalize"


@pytest.mark.anyio
@pytest.mark.usefixtures("loop_budget")
async def test_insufficient_evidence_triggers_rewrite_then_answers() -> None:
    final, llm = await run({
        "analyze": [ANALYSIS], "grade": [INSUFFICIENT, SUFFICIENT],
        "rewrite": [plan("all", "conceptual")], "synthesize": [DRAFT],
        "verify": [PASSED]})
    assert final["attempts"] == 1
    assert final["corpus_scope"] == "all"
    assert final["answer"].status == "answered"
    assert llm.roles().count("rewrite") == 1


@pytest.mark.anyio
@pytest.mark.usefixtures("loop_budget")
@pytest.mark.usefixtures("corpus_only")
async def test_persistent_insufficiency_abstains_after_retries() -> None:
    final, llm = await run({
        "analyze": [ANALYSIS], "grade": [INSUFFICIENT],
        "rewrite": [plan("all", "conceptual"), plan("all", "exact")]})
    assert final["answer"].status == "abstained"
    assert final["attempts"] == MAX_ATTEMPTS
    assert "synthesize" not in llm.roles()
    assert "Fuentes más cercanas" in final["answer"].text


@pytest.mark.anyio
@pytest.mark.usefixtures("loop_budget", "corpus_only")
async def test_repeated_strategy_abstains_immediately() -> None:
    same = RewritePlan(variants=["ambiente Mugrosa"], corpus_scope="core",
                       chunk_policy="prose_tables", query_type="conceptual",
                       reason="same")
    final, llm = await run({"analyze": [ANALYSIS], "grade": [INSUFFICIENT],
                            "rewrite": [same]})
    assert final["repeated"] is True
    assert final["answer"].status == "abstained"
    assert llm.roles().count("rewrite") == 1


@pytest.mark.anyio
@pytest.mark.usefixtures("loop_budget")
async def test_failed_verification_gets_one_revision() -> None:
    final, llm = await run({
        "analyze": [ANALYSIS], "grade": [SUFFICIENT],
        "synthesize": [DRAFT], "revise": [DRAFT],
        "verify": [FAILED, PASSED]})
    assert llm.roles().count("revise") == 1
    assert final["verified"] is True
    assert final["answer"].status == "answered"


@pytest.mark.anyio
async def test_model_outage_degrades_to_partial_not_crash() -> None:
    final, _ = await run({})
    assert final["answer"].status == "partial"
    assert "límite de tiempo" in final["answer"].text
    assert final["llm_calls"] <= 8


@pytest.mark.anyio
async def test_partial_evidence_answers_with_caveat() -> None:
    partial = Grade(relevant=["C1"], sufficient=False,
                    missing="los controles regionales", reason="parcial")
    final, llm = await run({"analyze": [ANALYSIS], "grade": [partial],
                            "synthesize": [DRAFT], "verify": [PASSED]})
    answer = final["answer"]
    assert llm.roles() == ["analyze", "grade", "synthesize", "verify"]
    assert answer.status == "partial"
    assert any("parcial" in caveat for caveat in answer.caveats)
    synth_request = dict(llm.calls)["synthesize"]
    assert "EVIDENCE STATUS: PARTIAL" in synth_request


@pytest.mark.anyio
async def test_writer_failure_is_partial_not_no_evidence() -> None:
    final, llm = await run({"analyze": [ANALYSIS], "grade": [SUFFICIENT],
                            "synthesize": [None]})
    answer = final["answer"]
    assert answer.status == "partial"
    assert "límite de tiempo" in answer.text
    assert "No encontré evidencia" not in answer.text
    assert "abstain" not in nodes(final)


def test_writer_nodes_get_a_longer_timeout() -> None:
    from config.roles import NODE_TIMEOUT_S, NODE_TIMEOUTS, TOTAL_TIMEOUT_S
    assert NODE_TIMEOUTS["synthesize"] > NODE_TIMEOUT_S
    assert NODE_TIMEOUTS["revise"] == NODE_TIMEOUTS["synthesize"]
    assert NODE_TIMEOUTS["synthesize"] < TOTAL_TIMEOUT_S["research"]

