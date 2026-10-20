from dataclasses import dataclass, field
from decimal import Decimal

import pytest
from fakes import FakeLLM, FakeStore
from test_graph import DRAFT, PASSED, ROWS

from crocol.application.agent.graph import build_graph
from crocol.application.agent.schemas import Analysis, Grade, PlaceMention
from crocol.application.agent.state import AgentDeps, initial_state
from crocol.application.tools.spatial_search import (
    plan_calls,
    render,
    spatial_search,
)
from crocol.domains.models.spatials import SpatialCall, SpatialResult
from crocol.infrastructure.repository.spatials import checked

SOURCE = "ANH-Informacion-Petrolera-2026"
FIELD_ROWS = (
    {"field": "YARIGUI-CANTAGALLO", "wells": 99, "producing": 60},
    {"field": "GARZAS", "wells": 20, "producing": 5},
)


@dataclass
class FakeSpatial:
    kinds: dict[str, str]
    calls: list[tuple[str, dict]] = field(default_factory=list)

    async def run(self, function: str, arguments: dict) -> SpatialResult:
        self.calls.append((function, arguments))
        if function == "resolve_place":
            kind = self.kinds.get(arguments["name"])
            rows = ({"kind": kind, "name": arguments["name"],
                     "score": 0.9},) if kind else ()
            return SpatialResult(function, rows, SOURCE)
        return SpatialResult(function, FIELD_ROWS, SOURCE)


@pytest.mark.parametrize(
    ("intents", "resolved", "functions"),
    [
        (["municipality_fields"], [("municipality", "Puerto Wilches")],
         ["fields_in_municipality"]),
        (["field_summary"], [("field", "Casabe")], ["field_summary"]),
        (["seismic_coverage"], [("field", "Casabe")], ["seismic_coverage"]),
        (["seismic_coverage"], [("well", "Casabe-1")], ["nearest_lines"]),
        (["faults"], [("field", "La Cira")], ["faults_near"]),
        (["other"], [("fault", "Falla de Cimitarra")], ["wells_near_fault"]),
        (["conceptual_geology"], [("", "Formación La Luna")], []),
        (["seismic_coverage", "faults"],
         [("field", "A"), ("field", "B")],
         ["seismic_coverage", "faults_near", "seismic_coverage"]),
    ],
)
def test_plan_calls(intents: list[str], resolved: list[tuple[str, str]],
                    functions: list[str]) -> None:
    calls = plan_calls(intents, resolved)
    assert [call.function for call in calls] == functions


def test_render_adds_totals_and_note() -> None:
    call = SpatialCall("fields_in_municipality", {"name": "Puerto Wilches"})
    text = render(call, SpatialResult(call.function, FIELD_ROWS, SOURCE))
    assert "field: YARIGUI-CANTAGALLO; wells: 99; producing: 60" in text
    assert "TOTAL (2 filas): wells: 119; producing: 65" in text
    assert "no hay polígonos" in text


def test_render_totals_per_seismic_layer() -> None:
    rows = (
        {"layer": "2D", "survey": "A", "items": 4,
         "length_km": Decimal("19.9")},
        {"layer": "2D", "survey": "B", "items": 2,
         "length_km": Decimal("5.1")},
        {"layer": "3D", "survey": "C", "items": 1,
         "area_km2": Decimal("12.5")},
    )
    call = SpatialCall("seismic_coverage", {"kind": "field", "name": "X",
                                            "buffer_km": 2})
    text = render(call, SpatialResult(call.function, rows, SOURCE))
    assert "TOTAL 2D (2 filas): items: 6; length_km: 25.0" in text
    assert "TOTAL 3D (1 filas): items: 1; area_km2: 12.5" in text


@pytest.mark.anyio
async def test_unknown_places_produce_no_calls() -> None:
    spatial = FakeSpatial(kinds={})
    chunks, calls = await spatial_search(
        spatial, ["municipality_fields"], [{"name": "Atlantis",
                                            "kind": "municipality"}])
    assert chunks == [] and calls == []


def test_store_rejects_unlisted_functions_and_kinds() -> None:
    with pytest.raises(ValueError):
        checked("drop_everything", {})
    with pytest.raises(ValueError):
        checked("faults_near", {"kind": "planet", "name": "x", "km": 5})
    sql, params = checked("fields_in_municipality", {"name": "  Yondó  "})
    assert params == ("Yondó",) and "%s" in sql


@pytest.mark.anyio
async def test_graph_cites_spatial_evidence_with_its_caveat() -> None:
    analysis = Analysis(
        language="es", mode="quick", intents=["municipality_fields"],
        corpus_scope="core", chunk_policy="numeric", query_type="exact",
        variants=[], places=[PlaceMention(name="Puerto Wilches",
                                          kind="municipality")])
    grade = Grade(relevant=["C1", "C2", "C3"], sufficient=True, missing="",
                  reason="ok")
    draft = DRAFT.model_copy(update={
        "text": "Hay 119 pozos en dos campos [C1, C2, C3].",
        "cited": ["C1", "C2", "C3"]})
    llm = FakeLLM({"analyze": [analysis], "grade": [grade],
                   "synthesize": [draft], "verify": [PASSED]})
    spatial = FakeSpatial(kinds={"Puerto Wilches": "municipality"})
    deps = AgentDeps(llm=llm, store=FakeStore(ROWS), spatial=spatial)
    final = await build_graph(deps).ainvoke(
        initial_state("¿Qué campos tienen pozos en Puerto Wilches?"))

    statuses = {event.node: event.status for event in final["trace"]}
    assert statuses["retrieve_spatial"] == "ok"
    answer = final["answer"]
    assert SOURCE in answer.text
    assert any("ANH-Informacion-Petrolera-2026" in c for c in answer.caveats)
    assert final["verified"] is True
    summary = [e.summary for e in final["trace"]
               if e.node == "retrieve_spatial"][0]
    assert summary == {"functions": ["fields_in_municipality"],
                       "argument_keys": ["name"], "results": 1}


class BrokenSpatial:
    async def run(self, function: str, arguments: dict) -> SpatialResult:
        raise ConnectionError("database down")


@pytest.mark.anyio
async def test_spatial_outage_is_a_caveat_not_a_partial_answer() -> None:
    analysis = Analysis(
        language="es", mode="quick", intents=["field_summary"],
        corpus_scope="core", chunk_policy="prose_tables",
        query_type="conceptual", variants=[],
        places=[PlaceMention(name="Casabe", kind="field")])
    grade = Grade(relevant=["C1"], sufficient=True, missing="", reason="ok")
    llm = FakeLLM({"analyze": [analysis], "grade": [grade],
                   "synthesize": [DRAFT], "verify": [PASSED]})
    deps = AgentDeps(llm=llm, store=FakeStore(ROWS), spatial=BrokenSpatial())
    final = await build_graph(deps).ainvoke(initial_state("¿Casabe?"))

    statuses = {event.node: event.status for event in final["trace"]}
    assert statuses["retrieve_spatial"] == "error"
    assert final["partial"] is False
    assert final["answer"].status == "answered"
    assert any("espacial" in c for c in final["answer"].caveats)
