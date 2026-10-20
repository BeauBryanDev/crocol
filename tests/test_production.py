from dataclasses import dataclass, field

import psycopg
import pytest
from fakes import FakeLLM, FakeStore

from config.settings import get_settings
from crocol.application.agent.graph import build_graph
from crocol.application.agent.nodes.retrieve import retrieve_production
from crocol.application.agent.schemas import (
    Analysis,
    DraftAnswer,
    Grade,
    PlaceMention,
    Verification,
)
from crocol.application.agent.state import AgentDeps, initial_state
from crocol.application.tools.production_search import (
    field_mentions,
    search_production_by_field,
)
from crocol.domains.models.productions import ProductionResult
from crocol.domains.services.production_trend import classify
from crocol.infrastructure.repository.productions import checked

MONTHS = [f"2025-{m:02d}-28" for m in range(1, 9)]
CIRA = {"kind": "contract", "name": "LA CIRA INFANTAS",
        "field_keys": ["INFANTAS", "LACIRA"], "score": 0.95,
        "has_oil": True, "has_gas": True}


@dataclass
class FakeProduction:
    resolved: list[dict]
    oil: list[float | None]
    gas: list[float | None]
    calls: list[tuple[str, dict]] = field(default_factory=list)

    async def run(self, function: str, arguments: dict) -> ProductionResult:
        self.calls.append((function, dict(arguments)))
        if function == "resolve_field":
            rows = self.resolved
        elif function == "field_series":
            rows = [{"month_end": m, "oil_bpdc": o, "gas_mpcpdc": g}
                    for m, o, g in zip(MONTHS, self.oil, self.gas)]
        else:
            rows = [{"fields": ["INFANTAS", "LA CIRA"],
                     "departments": ["SANTANDER"],
                     "municipalities": ["BARRANCABERMEJA"],
                     "operators": ["ECOPETROL S.A."],
                     "contracts": ["LA CIRA INFANTAS"]}]
        return ProductionResult(function, tuple(rows), "ANH-Produccion-Fiscalizada-2026")


DECLINING_OIL = [26128.0, 26000.0, 25800.0, 25600.0, 25300.0, 25100.0, 24900.0, 24700.0]
STABLE_GAS = [8.6, 8.7, 8.6, 8.5, 8.6, 8.7, 8.6, 8.6]


@pytest.mark.parametrize(("values", "label"), [
    (DECLINING_OIL, "decreasing"),
    (list(reversed(DECLINING_OIL)), "increasing"),
    (STABLE_GAS, "stable"),
    ([10.0, 30.0, 5.0, 40.0, 8.0, 35.0], "variable"),
    ([0.0, 0.0, 0.0], "no_production"),
    ([5.0, None], "insufficient_data"),
])
def test_trend_classification(values: list, label: str) -> None:
    assert classify(values).label == label


def test_trend_numbers_describe_the_fitted_line() -> None:
    trend = classify(DECLINING_OIL)
    assert trend.first == 26128.0 and trend.last == 24700.0
    assert -6.5 < trend.change_pct < -4.5
    assert trend.scatter_pct < 1


def test_only_field_like_mentions_are_used() -> None:
    mentions = [{"name": "La Luna", "kind": "formation"},
                {"name": "La Cira-Infantas", "kind": "field"},
                {"name": "VMM 53", "kind": "contract_area"},
                {"name": "Casabe", "kind": "unknown"},
                {"name": "Llanito", "kind": "field"}]
    assert field_mentions(mentions) == ["La Cira-Infantas", "VMM 53", "Casabe"]


@pytest.mark.anyio
async def test_tool_returns_evidence_and_chart_series() -> None:
    store = FakeProduction([CIRA], DECLINING_OIL, STABLE_GAS)
    found = await search_production_by_field(
        store, [{"name": "La Cira-Infantas", "kind": "field"}])

    series = found.series[0]
    assert series.name == "LA CIRA INFANTAS" and series.kind == "contract"
    assert series.oil_trend.label == "decreasing"
    assert series.gas_trend.label == "stable"
    text = found.chunks[0].text
    assert "contrato que agrupa los campos INFANTAS, LA CIRA" in text
    assert "Tendencia del crudo (BPDC)" in text and "DECRECIENTE" in text
    assert "Tendencia del gas (MPCPDC)" in text and "ESTABLE" in text
    assert found.chunks[0].citation == "ANH-Produccion-Fiscalizada-2026"
    assert ("field_series", {"field_keys": ["INFANTAS", "LACIRA"]}) in store.calls


@pytest.mark.anyio
async def test_weak_name_matches_are_ignored() -> None:
    weak = [{**CIRA, "score": 0.5}]
    found = await search_production_by_field(
        FakeProduction(weak, DECLINING_OIL, STABLE_GAS),
        [{"name": "Cirax", "kind": "field"}])
    assert found.series == () and found.chunks == ()


def state_with(**fields: object) -> dict:
    state = dict(initial_state("¿Cómo va la producción de La Cira?"))
    state.update(fields)
    return state


@pytest.mark.anyio
async def test_node_runs_only_for_production_questions() -> None:
    store = FakeProduction([CIRA], DECLINING_OIL, STABLE_GAS)
    deps = AgentDeps(llm=FakeLLM({}), store=FakeStore([]), production=store)
    places = [{"name": "La Cira-Infantas", "kind": "field"}]

    update, _ = await retrieve_production(state_with(intents=["history"], places=places), deps)
    assert update["channels"]["production"]["status"] == "skipped"

    update, summary = await retrieve_production(
        state_with(intents=["production"], places=places), deps)
    assert update["channels"]["production"]["status"] == "ok"
    assert update["production"][0]["units"] == {"oil": "BPDC", "gas": "MPCPDC"}
    assert len(update["production"][0]["points"]) == len(MONTHS)
    assert summary == {"series": 1, "kinds": ["contract"],
                       "oil_trends": ["decreasing"], "gas_trends": ["stable"]}


@pytest.mark.anyio
async def test_production_series_reach_the_answer() -> None:
    analysis = Analysis(language="es", mode="quick", intents=["production"],
                        corpus_scope="core", chunk_policy="numeric",
                        query_type="conceptual", variants=[],
                        places=[PlaceMention(name="La Cira-Infantas", kind="field")])
    draft = DraftAnswer(text="La producción de crudo de La Cira-Infantas es "
                             "decreciente [C1].", cited=["C1"])
    llm = FakeLLM({"analyze": [analysis],
                   "grade": [Grade(relevant=["C1"], sufficient=True, missing="", reason="ok")],
                   "synthesize": [draft], "verify": [Verification(claims=[])]})
    deps = AgentDeps(llm=llm, store=FakeStore([]),
                     production=FakeProduction([CIRA], DECLINING_OIL, STABLE_GAS))
    final = await build_graph(deps).ainvoke(initial_state("¿Producción de La Cira?"))

    answer = final["answer"]
    assert answer.production[0]["name"] == "LA CIRA INFANTAS"
    assert "(ANH-Produccion-Fiscalizada-2026)" in answer.text
    assert any("Producción fiscalizada ANH" in c for c in answer.caveats)


def test_store_validates_arguments() -> None:
    with pytest.raises(ValueError):
        checked("drop_table", {})
    with pytest.raises(ValueError):
        checked("field_series", {"field_keys": []})
    sql, params = checked("resolve_field", {"name": "x" * 300, "max_rows": 2})
    assert params == ("x" * 120, 2)


@pytest.mark.integration
def test_real_tables_sum_la_cira_infantas() -> None:
    dsn = get_settings().pg_dsn
    if dsn is None:
        pytest.skip("PG_DSN not set")
    try:
        conn = psycopg.connect(dsn.get_secret_value(), connect_timeout=2,
                               options="-c default_transaction_read_only=on")
    except psycopg.OperationalError:
        pytest.skip("vmm-postgis is not reachable")
    with conn:
        if conn.execute("SELECT to_regclass('core.oil_production')").fetchone()[0] is None:
            pytest.skip("production tables not loaded")
        best = conn.execute("SELECT kind, field_keys FROM prod.resolve_field('La Cira-Infantas', 1)").fetchone()
        assert best == ("contract", ["INFANTAS", "LACIRA"])
        series = conn.execute("SELECT count(*), sum(oil_bpdc) FROM prod.field_series(%s)", (best[1],)).fetchone()
        direct = conn.execute(
            "SELECT sum(value) FROM core.oil_production WHERE field_key = ANY(%s)", (best[1],)).fetchone()[0]
        assert series[0] == 20
        assert abs(series[1] - direct) < 1e-6


def test_final_event_carries_the_chart_series() -> None:
    from crocol.application.usecases.ask_questions import final_event
    from crocol.domains.models.answers import Answer
    series = {"name": "CASABE", "points": [{"month": "2025-01-31", "oil": 8056.4, "gas": 0.76}]}
    answer = Answer(text="t", status="answered", production=(series,))
    record = {"llm_calls": 4, "tokens_in": 10, "tokens_out": 5}
    event = final_event("trace-1", answer, record)
    assert event["production"] == [series]
