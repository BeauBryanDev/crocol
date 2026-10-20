import pytest
from fakes import FakeGraph, FakeLLM, FakeStore, graph_rows, row

from config.settings import KG_LABEL
from crocol.application.agent.graph import build_graph
from crocol.application.agent.nodes.retrieve import retrieve_graph
from crocol.application.agent.schemas import (
    Analysis,
    DraftAnswer,
    EntityMention,
    Grade,
)
from crocol.application.agent.state import AgentDeps, initial_state
from crocol.application.tools.graph_search import clean_name, graph_search, pick

MENTIONS = [{"name": "Formación La Luna", "kind": "formation"}]


def test_clean_name_drops_cue_words() -> None:
    assert clean_name("Formación La Luna") == "La Luna"
    assert clean_name("pozo Infantas-1613") == "Infantas-1613"
    assert clean_name("Barrancabermeja") == "Barrancabermeja"


def test_pick_prefers_hinted_kind_and_rejects_weak_matches() -> None:
    rows = (
        {"entity_id": 1, "kind": "well", "name": "LA LUNA-1", "score": 0.7,
         "props": {}},
        {"entity_id": 2, "kind": "formation", "name": "La Luna",
         "score": 0.65, "props": {}},
    )
    assert pick(rows, "formation").entity_id == 2
    assert pick(rows, "fault") is None
    assert pick(rows, "unknown").entity_id == 1


@pytest.mark.anyio
async def test_graph_search_renders_facts_and_fetches_chunks() -> None:
    graph = FakeGraph(graph_rows())
    found = await graph_search(graph, MENTIONS, "core")

    assert [e.name for e in found.entities] == ["La Luna"]
    assert [c.chunk_id for c in found.chunks] == ["g1"]
    facts = found.facts[0]
    assert facts.citation == KG_LABEL
    assert facts.doc_type == "graph_fact"
    assert "Incluye [member] (3): Galembo, Pujamana, Salada" in facts.text
    assert "Suprayace a (está encima de) [formation] (1): Simití" in facts.text
    assert "co-ocurrencia, no relación geológica" in facts.text
    assert "Edad: Turoniano–Santoniano" in facts.text
    assert "Rueda Acevedo, 2016 (11 pasajes)" in facts.text

    resolve = dict(graph.calls)["resolve"]
    assert resolve["name"] == "La Luna"
    evidence = dict(graph.calls)["evidence_chunks"]
    assert evidence["collections"] == ["VMM_Basin"]
    assert evidence["peripheral"] is False


@pytest.mark.anyio
async def test_scope_all_searches_every_collection() -> None:
    graph = FakeGraph(graph_rows())
    await graph_search(graph, MENTIONS, "all")
    evidence = dict(graph.calls)["evidence_chunks"]
    assert evidence["collections"] is None
    assert evidence["peripheral"] is True


@pytest.mark.anyio
async def test_unresolved_mentions_return_nothing() -> None:
    rows = graph_rows()
    rows["resolve"] = []
    found = await graph_search(FakeGraph(rows), MENTIONS, "core")
    assert found.entities == () and found.chunks == () and found.facts == ()


def state_with(**fields: object) -> dict:
    state = dict(initial_state("¿Qué miembros tiene La Luna?"))
    state.update(fields)
    return state


@pytest.mark.anyio
async def test_retrieve_graph_channel_ok_without_user_text() -> None:
    deps = AgentDeps(llm=FakeLLM({}), store=FakeStore([]),
                     graph=FakeGraph(graph_rows()))
    update, summary = await retrieve_graph(state_with(entities=MENTIONS),
                                           deps)
    channel = update["channels"]["graph"]
    assert channel["status"] == "ok"
    assert [len(lst) for lst in channel["lists"]] == [1, 1]
    assert summary == {"mentions": 1, "resolved_kinds": ["formation"],
                       "chunks": 1, "facts": 1}


@pytest.mark.anyio
async def test_retrieve_graph_skips_and_fails_softly() -> None:
    store = FakeStore([])
    no_graph = AgentDeps(llm=FakeLLM({}), store=store)
    update, _ = await retrieve_graph(state_with(entities=MENTIONS), no_graph)
    assert update["channels"]["graph"]["status"] == "skipped"

    deps = AgentDeps(llm=FakeLLM({}), store=store,
                     graph=FakeGraph(graph_rows()))
    update, _ = await retrieve_graph(state_with(), deps)
    assert update["channels"]["graph"]["status"] == "skipped"

    broken = AgentDeps(llm=FakeLLM({}), store=store,
                       graph=FakeGraph({}, fail=True))
    update, summary = await retrieve_graph(state_with(entities=MENTIONS),
                                           broken)
    assert update["channels"]["graph"]["status"] == "error"
    assert summary["error"] == "RuntimeError"


ANALYSIS = Analysis(language="es", mode="quick", intents=["conceptual"],
                    corpus_scope="core", chunk_policy="prose_tables",
                    query_type="conceptual", variants=[],
                    entities=[EntityMention(name="La Luna", kind="formation")])
NOTHING = Grade(relevant=[], sufficient=False, missing="todo", reason="no")


@pytest.mark.anyio
async def test_graph_facts_reach_the_answer_with_kg_citation() -> None:
    facts_label = Grade(relevant=["C1", "C2"], sufficient=True, missing="",
                        reason="ok")
    draft = DraftAnswer(text="La Luna incluye los miembros Galembo, Pujamana "
                             "y Salada [C1].", cited=["C1"])
    llm = FakeLLM({"analyze": [ANALYSIS], "grade": [facts_label],
                   "synthesize": [draft], "verify": [None]})
    deps = AgentDeps(llm=llm, store=FakeStore([]),
                     graph=FakeGraph(graph_rows()))
    final = await build_graph(deps).ainvoke(
        initial_state("¿Qué miembros tiene La Luna?"))
    answer = final["answer"]
    assert f"({KG_LABEL})" in answer.text
    assert any("provienen del grafo de conocimiento" in c for c in answer.caveats)


@pytest.mark.anyio
async def test_no_evidence_answers_from_general_knowledge() -> None:
    draft = DraftAnswer(text="El corpus no tiene pasajes sobre esto. La "
                             "refinería de Barrancabermeja inició en 1922 "
                             "[KG].", cited=["KG"])
    llm = FakeLLM({"analyze": [ANALYSIS.model_copy(update={"entities": []})],
                   "grade": [NOTHING], "synthesize": [draft]})
    rows = [row("c1", "d1", "Texto sin relación.", "Autor, 2016")]
    final = await build_graph(AgentDeps(llm=llm, store=FakeStore(rows))
                              ).ainvoke(initial_state("¿Refinería?"))
    answer = final["answer"]

    assert llm.roles() == ["analyze", "grade", "synthesize"]
    assert "EVIDENCE STATUS: NONE" in dict(llm.calls)["synthesize"]
    assert answer.status == "answered"
    assert answer.text.endswith("inició en 1922 (Crocol-KG-2026).")
    assert [c.rendered for c in answer.citations] == ["(Crocol-KG-2026)"]
    assert any("conocimiento general del modelo" in c for c in answer.caveats)
    assert any(r.startswith("Crocol-KG-2026.") for r in answer.references)
