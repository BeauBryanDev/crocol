from dataclasses import dataclass, field

import pytest
from fakes import FakeLLM, FakeStore
from test_geo_pg import connect
from test_graph import DRAFT, PASSED, ROWS

from crocol.application.agent.graph import build_graph
from crocol.application.agent.research import merge
from crocol.application.agent.schemas import Analysis, Grade, WellQuery
from crocol.application.agent.state import AgentDeps, initial_state
from crocol.application.tools.spatial_search import (
    render,
    spatial_search,
    well_calls,
)
from crocol.domains.models.chunks import Chunk
from crocol.domains.models.spatials import SpatialCall, SpatialResult
from crocol.infrastructure.repository.spatials import checked

SOURCE = "ANH-Informacion-Petrolera-2026"
DEEP = {"well_name": "ESCUELA-2 ST2", "field_name": "DINDAL",
        "depth_ft": 20250.0, "depth_m": 6172.2, "depth_reliable": True,
        "matched": "todos los pozos del VMM"}
BAD = {"well_name": "INFANTAS-3394", "field_name": "INFANTAS",
       "depth_ft": 45363.0, "depth_m": 13826.6, "depth_reliable": False,
       "matched": "todos los pozos del VMM"}
STATS = {"grp": "TODOS", "wells": 1502, "producing": 457, "with_depth": 1401,
         "without_depth": 101, "matched": 'campo "Casabe" = CASABE'}


@dataclass
class FakeWells:
    kinds: dict[str, str] = field(default_factory=dict)
    calls: list[tuple[str, dict]] = field(default_factory=list)

    async def run(self, function: str, arguments: dict) -> SpatialResult:
        self.calls.append((function, arguments))
        if function == "resolve_place":
            kind = self.kinds.get(arguments["name"])
            rows = ({"kind": kind, "name": arguments["name"],
                     "score": 0.9},) if kind else ()
            return SpatialResult(function, rows, SOURCE)
        if function == "well_list":
            return SpatialResult(function, (DEEP,), SOURCE)
        return SpatialResult(function, (STATS,), SOURCE)


@pytest.mark.parametrize(
    ("query", "function", "expected"),
    [
        ({"op": "count", "municipality": "Yondó"}, "well_stats",
         {"municipality": "Yondó", "group_by": None}),
        ({"op": "group_by", "group_by": "field"}, "well_stats",
         {"group_by": "field", "field": None}),
        ({"op": "top_depth"}, "well_list", {"order_by": "depth", "n": 5}),
        ({"op": "near_fault", "field": "Casabe", "max_fault_km": 1},
         "well_list", {"order_by": "fault", "max_fault_km": 1, "n": 20}),
        ({"op": "list", "field": "Nare", "n": 10, "max_fault_km": 3},
         "well_list", {"order_by": "name", "max_fault_km": None, "n": 10}),
        ({"op": "distance", "wells": ["Casabe-1", "Casabe-2"]},
         "well_distance", {"well_a": "Casabe-1", "well_b": "Casabe-2"}),
    ],
)
def test_well_calls(query: dict, function: str, expected: dict) -> None:
    calls = well_calls(query)
    assert [call.function for call in calls] == [function]
    for name, value in expected.items():
        assert calls[0].arguments[name] == value


@pytest.mark.parametrize("query", [
    None, {}, {"op": "distance", "wells": ["Casabe-1"]},
    {"op": "drop_table"},
])
def test_incomplete_well_queries_make_no_call(query: dict | None) -> None:
    assert well_calls(query) == []


def test_store_checks_well_arguments() -> None:
    sql, params = checked("well_list", {
        "field": "  Casabe ", "statuses": ["PRODUCTOR"], "order_by": "depth",
        "n": 500, "max_fault_km": 99})
    assert "geo.well_list(" in sql and "%s::text[]" in sql
    assert params == (None, "Casabe", None, None, ["PRODUCTOR"], None, None,
                      "depth", 20.0, 50)
    _, params = checked("well_stats", {"group_by": None})
    assert params == (None,) * 8
    with pytest.raises(ValueError):
        checked("well_stats", {"group_by": "planet"})
    with pytest.raises(ValueError):
        checked("well_list", {"statuses": ["'; DROP"], "order_by": "name",
                              "n": 5})
    with pytest.raises(ValueError):
        checked("well_list", {"order_by": "random()", "n": 5})


def test_render_gives_both_units_and_flags_unreliable() -> None:
    call = SpatialCall("well_list", {"order_by": "depth"})
    text = render(call, SpatialResult(call.function, (DEEP, BAD), SOURCE))
    assert "Filtro: todos los pozos del VMM." in text
    assert "depth: 20250 ft / 6172.2 m" in text
    assert "depth: 45363 ft / 13826.6 m (NO CONFIABLE)" in text
    assert "matched" not in text and "depth_reliable" not in text
    assert "profundidad medida" in text and "1.714 pozos" in text


def test_render_single_group_has_no_total_line() -> None:
    call = SpatialCall("well_stats", {"field": "Casabe"})
    text = render(call, SpatialResult(call.function, (STATS,), SOURCE))
    assert 'Filtro: campo "Casabe" = CASABE.' in text
    assert "without_depth: 101" in text and "TOTAL" not in text


@pytest.mark.anyio
async def test_well_query_runs_first_and_without_places() -> None:
    spatial = FakeWells(kinds={"Casabe": "field"})
    _, calls = await spatial_search(spatial, ["well_query"], [],
                                    {"op": "top_depth", "n": 3})
    assert [c.function for c in calls] == ["well_list"]

    _, calls = await spatial_search(
        spatial, ["field_summary"], [{"name": "Casabe", "kind": "field"}],
        {"op": "count", "field": "Casabe"})
    assert [c.function for c in calls] == ["well_stats", "field_summary"]


def test_analysis_parses_a_well_query() -> None:
    analysis = Analysis.model_validate({
        "language": "en", "mode": "quick", "intents": ["well_query"],
        "corpus_scope": "core", "chunk_policy": "numeric",
        "query_type": "cross_language", "variants": [],
        "well_query": top_depth_query()})
    assert analysis.well_query == WellQuery(**top_depth_query())


def top_depth_query() -> dict:
    fields = dict.fromkeys(WellQuery.model_fields)
    return {**fields, "op": "top_depth", "n": 5, "statuses": [], "wells": []}


def optional_fields(schema: dict) -> int:
    count = 0
    for node in [schema, *schema.get("$defs", {}).values()]:
        required = set(node.get("required", []))
        count += sum(1 for name in node.get("properties", {})
                     if name not in required)
    return count


def test_analyzer_schema_stays_simple_enough_for_anthropic() -> None:
    """18 optional fields got 400 'Schema is too complex' live (2026-10-20)."""
    assert optional_fields(WellQuery.model_json_schema()) == 0
    assert optional_fields(Analysis.model_json_schema()) <= 8


@pytest.mark.anyio
async def test_basin_question_reaches_the_database_with_a_depth_caveat(
) -> None:
    analysis = Analysis(
        language="en", mode="quick", intents=["well_query"],
        corpus_scope="core", chunk_policy="numeric",
        query_type="cross_language", variants=[],
        well_query=WellQuery(**top_depth_query()))
    grade = Grade(relevant=["C1"], sufficient=True, missing="", reason="ok")
    draft = DRAFT.model_copy(update={
        "text": "The deepest well is ESCUELA-2 ST2 [C1].", "cited": ["C1"]})
    llm = FakeLLM({"analyze": [analysis], "grade": [grade],
                   "synthesize": [draft], "verify": [PASSED]})
    spatial = FakeWells()
    deps = AgentDeps(llm=llm, store=FakeStore(ROWS), spatial=spatial)
    final = await build_graph(deps).ainvoke(
        initial_state("Which are the five deepest wells in the VMM?"))

    statuses = {event.node: event.status for event in final["trace"]}
    assert statuses["retrieve_spatial"] == "ok"
    assert spatial.calls[0][0] == "well_list"
    analyze = [e.summary for e in final["trace"] if e.node == "analyze"][0]
    assert analyze["well_query"] == "top_depth"
    assert any("measured depth" in c for c in final["answer"].caveats)


@pytest.mark.anyio
async def test_research_merge_puts_database_passages_first() -> None:
    deps = AgentDeps(llm=FakeLLM({}), store=FakeStore([]),
                     spatial=FakeWells())
    paper = Chunk("p1", "doc-1", "Casabe produce de Mugrosa.", "Autor, 2010")
    state = dict(initial_state("¿Cuántos pozos tiene Casabe y por qué?"))
    state.update(mode="research", intents=["well_query", "history"],
                 well_query={"op": "count", "field": "Casabe"},
                 sub_results=[{"index": 0, "evidence": [paper],
                               "sufficient": True, "missing": ""}])
    update, summary = await merge(state, deps)

    labels = [(c.label, c.citation) for c in update["evidence"]]
    assert labels == [("C1", SOURCE), ("C2", "Autor, 2010")]
    assert summary["spatial_passages"] == 1
    assert update["channels"]["spatial"]["status"] == "ok"


@pytest.fixture(scope="module")
def conn():

    connection = connect()
    if connection is None:
        pytest.skip("vmm-postgis is not reachable")
    loaded = connection.execute(
        "SELECT to_regclass('core.well_metrics') IS NOT NULL").fetchone()[0]
    if not loaded:
        pytest.skip("well metrics are not loaded")
    yield connection
    connection.close()


def run(conn, function: str, arguments: dict) -> list[dict]:

    sql, params = checked(function, arguments)
    cursor = conn.execute(sql, params)
    columns = [column.name for column in cursor.description]
    return [dict(zip(columns, record)) for record in cursor.fetchall()]


@pytest.mark.integration
def test_casabe_count_matches_field_summary(conn) -> None:
    rows = run(conn, "well_stats", {"field": "Casabe"})
    assert rows[0]["wells"] == 1502
    assert rows[0]["matched"] == 'campo "Casabe" = CASABE'
    assert rows[0]["with_depth"] + rows[0]["without_depth"] == 1502


@pytest.mark.integration
def test_basin_top_depth_skips_unreliable_values(conn) -> None:
    rows = run(conn, "well_list", {"order_by": "depth", "n": 5})
    names = [row["well_name"] for row in rows]
    assert len(rows) == 5 and "INFANTAS-3394" not in names
    assert all(row["depth_reliable"] for row in rows)
    depths = [row["depth_ft"] for row in rows]
    assert depths == sorted(depths, reverse=True) and depths[0] <= 25000
    assert float(rows[0]["depth_m"]) == round(depths[0] * 0.3048, 1)


@pytest.mark.integration
def test_wells_per_field_covers_every_well(conn) -> None:
    rows = run(conn, "well_stats", {"group_by": "field"})
    total = conn.execute("SELECT count(*) FROM core.wells").fetchone()[0]
    assert sum(row["wells"] for row in rows) == total
    fields = conn.execute("SELECT count(*) FROM core.fields").fetchone()[0]
    assert len(rows) in (fields, fields + 1)


@pytest.mark.integration
def test_field_operator_pairs_cover_the_municipality(conn) -> None:
    pairs = run(conn, "well_stats", {"municipality": "Puerto Boyacá",
                                     "group_by": "field_operator"})
    plain = run(conn, "well_stats", {"municipality": "Puerto Boyacá"})
    assert sum(row["wells"] for row in pairs) == plain[0]["wells"]
    assert all(" | " in row["grp"] for row in pairs)


@pytest.mark.integration
def test_unmatched_filter_returns_no_wells(conn) -> None:
    assert run(conn, "well_stats", {"municipality": "Atlantis"}) == []


@pytest.mark.integration
def test_department_filter_ignores_accents(conn) -> None:
    plain = run(conn, "well_stats", {"department": "Boyaca"})
    accent = run(conn, "well_stats", {"department": "BOYACÁ"})
    assert plain[0]["wells"] == accent[0]["wells"] > 2500


@pytest.mark.integration
def test_three_d_distance_matches_hand_computation(conn) -> None:
    row = run(conn, "well_distance", {"well_a": "CASABE-175",
                                      "well_b": "CASABE-1097DIR"})[0]
    surface_m = conn.execute(
        "SELECT ST_Distance(a.geom_ctm12, b.geom_ctm12) FROM core.wells a, "
        "core.wells b WHERE a.well_name = 'CASABE-175' "
        "AND b.well_name = 'CASABE-1097DIR'").fetchone()[0]
    dz_m = ((row["depth_a_ft"] - 500) - (row["depth_b_ft"] - 500)) * 0.3048
    expected = round((surface_m ** 2 + dz_m ** 2) ** 0.5, 1)
    assert float(row["distance_3d_m"]) == expected
    assert row["pay_a_ft"] == row["depth_a_ft"] - 500


@pytest.mark.integration
def test_distance_with_unreliable_depth_is_surface_only(conn) -> None:
    row = run(conn, "well_distance", {"well_a": "INFANTAS-3394",
                                      "well_b": "CASABE-175"})[0]
    assert row["distance_3d_m"] is None and row["surface_km"] > 0
    assert row["note"].startswith("solo distancia en superficie")
