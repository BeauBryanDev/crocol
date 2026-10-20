import pytest
from fakes import FakeLLM, FakeStore, row

from config.roles import LLM_CALL_BUDGET, RECURSION_LIMIT
from crocol.application.agent import routing
from crocol.application.agent.graph import build_graph
from crocol.application.agent.nodes.evaluate import (
    find_conflicts,
    property_key,
)
from crocol.application.agent.schemas import (
    Analysis,
    ClaimCheck,
    ConflictRecord,
    ConflictRecords,
    DraftAnswer,
    Grade,
    ResearchPlan,
    SubQuestion,
    Verification,
)
from crocol.application.agent.state import AgentDeps, initial_state
from crocol.domains.models.chunks import Chunk

TOC_A = "El TOC de la Formación La Luna alcanza 7,72 % en el Miembro Galembo."
TOC_B = ("La Formación La Luna tiene un TOC promedio de 3.1 % en el "
         "sector norte.")
ROWS = [
    row("c1", "d1", TOC_A, "Guerrero et al., 2020", page=12),
    row("c2", "d2", TOC_B, "Mantilla Barrios, 2014", page=28),
]
RESEARCH = Analysis(language="es", mode="research", intents=["compare"],
                    corpus_scope="core", chunk_policy="numeric",
                    query_type="conceptual", variants=[])


def sub(question: str) -> SubQuestion:
    return SubQuestion(question=question, corpus_scope="core",
                       chunk_policy="numeric", query_type="conceptual")


def chunk(label: str, doc_id: str, text: str) -> Chunk:
    return Chunk(f"id-{label}", doc_id, text, f"Autor {doc_id}, 2020",
                 page_start=3, page_end=3, label=label)


def record(label: str, value: str, unit: str, quote: str) -> ConflictRecord:
    return ConflictRecord(entity="Formación La Luna", property="TOC",
                          value=value, unit=unit, label=label, quote=quote)


EVIDENCE = [chunk("C1", "d1", TOC_A), chunk("C2", "d2", TOC_B)]


def test_different_documents_with_different_values_conflict() -> None:
    records = [record("C1", "7,72", "%", "alcanza 7,72 %"),
               record("[C2]", "3.1", "%", "TOC promedio de 3.1 %")]
    conflicts = find_conflicts(records, EVIDENCE)
    assert len(conflicts) == 1
    assert conflicts[0]["comparable"] is True
    assert {s["doc_id"] for s in conflicts[0]["sides"]} == {"d1", "d2"}


def test_same_value_in_other_notation_is_not_a_conflict() -> None:
    records = [record("C1", "7,72", "%", "alcanza 7,72 %"),
               record("C2", "7.72", "%", "La Formación La Luna")]
    assert find_conflicts(records, EVIDENCE) == []


def test_value_inside_a_range_is_not_a_conflict() -> None:
    records = [record("C1", "2-12", "%", "alcanza 7,72 %"),
               record("C2", "3.1", "%", "TOC promedio de 3.1 %")]
    assert find_conflicts(records, EVIDENCE) == []


def test_different_units_are_flagged_not_comparable() -> None:
    records = [record("C1", "7,72", "%", "alcanza 7,72 %"),
               record("C2", "3.1", "wt%", "TOC promedio de 3.1 %")]
    assert find_conflicts(records, EVIDENCE)[0]["comparable"] is False


def test_unverifiable_quote_is_dropped() -> None:
    records = [record("C1", "7,72", "%", "alcanza 7,72 %"),
               record("C2", "1.0", "%", "texto inventado por el modelo")]
    assert find_conflicts(records, EVIDENCE) == []


@pytest.mark.usefixtures("corpus_only")
def test_research_routing() -> None:
    state = dict(initial_state("q"))
    state.update(mode="research",
                 sub_questions=[sub("a").model_dump(), sub("b").model_dump()])
    assert routing.after_analyze(state) == ["plan"]
    sends = routing.after_plan(state)
    assert [s.node for s in sends] == ["investigate", "investigate"]
    assert [s.arg["index"] for s in sends] == [0, 1]
    assert routing.after_merge({**state, "evidence": []}) == "abstain"
    assert routing.after_merge({**state, "evidence": EVIDENCE}) == (
        "conflict_check")


async def run(script: dict) -> tuple[dict, FakeLLM]:
    llm = FakeLLM(script)
    graph = build_graph(AgentDeps(llm=llm, store=FakeStore(ROWS)))
    final = await graph.ainvoke(initial_state("¿Difieren las fuentes en el "
                                              "TOC de La Luna?"),
                                config={"recursion_limit": RECURSION_LIMIT})
    return final, llm


@pytest.mark.anyio
async def test_research_run_reports_disagreement_within_budget() -> None:
    plan = ResearchPlan(sub_questions=[sub("TOC de La Luna, Galembo"),
                                       sub("TOC de La Luna, sector norte")])
    grade = Grade(relevant=["C1", "C2"], sufficient=True, missing="",
                  reason="ok")
    conflicts = ConflictRecords(records=[
        record("C1", "7,72", "%", "alcanza 7,72 %"),
        record("C2", "3.1", "%", "TOC promedio de 3.1 %")])
    draft = DraftAnswer(text="Las fuentes difieren [C1, C2].",
                        cited=["C1", "C2"])
    passed = Verification(claims=[ClaimCheck(
        claim="Las fuentes difieren", labels=["C1"], verdict="supported")])
    final, llm = await run({"analyze": [RESEARCH], "plan": [plan],
                            "grade": [grade], "conflict": [conflicts],
                            "synthesize": [draft], "verify": [passed]})

    assert llm.roles().count("grade") == 2
    assert final["llm_calls"] <= LLM_CALL_BUDGET["research"]
    assert len(final["evidence"]) == 2
    answer = final["answer"]
    assert answer.status == "answered"
    assert len(answer.conflicts) == 1
    synth_request = dict(llm.calls)["synthesize"]
    assert "MODE: RESEARCH REPORT" in synth_request
    assert "SOURCES DISAGREE" in synth_request


@pytest.mark.anyio
@pytest.mark.usefixtures("corpus_only")
async def test_plan_is_cut_to_the_budget() -> None:
    plan = ResearchPlan(sub_questions=[sub(f"pregunta {i}")
                                       for i in range(6)])
    grade = Grade(relevant=[], sufficient=False, missing="x", reason="no")
    final, llm = await run({"analyze": [RESEARCH], "plan": [plan],
                            "grade": [grade]})
    assert len(final["sub_questions"]) == 3
    assert llm.roles().count("grade") == 3
    assert final["answer"].status == "abstained"


@pytest.mark.parametrize(
    ("label", "code"),
    [
        ("thermal maturity (ro or tmax)", "tmax"),
        ("Tmax", "tmax"),
        ("%Ro", "ro"),
        ("reflectancia de vitrinita", "ro"),
        ("TOC", "toc"),
        ("carbono orgánico total", "toc"),
        ("espesor", "thickness"),
        ("porosidad efectiva", "porosity"),
    ],
)
def test_property_labels_map_to_codes(label: str, code: str) -> None:
    assert property_key(label) == code
