from typing import Any

import pytest
from fakes import FakeLLM, FakeStore

from config.exceptions import SimulatorBusyError
from config.roles import RECURSION_LIMIT
from config.settings import WELLSIM_LABEL
from crocol.application.agent import routing
from crocol.application.agent.graph import build_graph
from crocol.application.agent.schemas import SimulationAnswer
from crocol.application.agent.state import AgentDeps, initial_state
from crocol.application.tools.well_simulation import SimulationRunner
from crocol.infrastructure.simulation.adapter import NumericWellSimulator

QUESTION = "What rate should this well produce at?"
WELL = {"Nr": 12, "Nz": 4, "Nt": 40, "rw": 0.354, "re": 1000.0, "h": 50.0,
        "kh": 100.0, "phi": 0.2, "cf": 4e-6, "pi": 4000.0, "pb": 2000.0,
        "mu": 1.5, "Bo": 1.2, "co": 1e-5, "rho": 50.0}
ANSWER = SimulationAnswer(
    language="en",
    text="## Recommended operating point\nProduce at the recommended rate "
         "[C1]. Keep the flowing bottomhole pressure above pb [C1].")


class BusySimulator:
    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        raise SimulatorBusyError()

    def sweep(self, params: dict[str, Any],
              options: dict[str, Any]) -> dict[str, Any]:
        raise SimulatorBusyError()


async def run(script: dict, simulator: Any = None,
              well: dict | None = WELL) -> tuple[dict, FakeLLM]:
    llm = FakeLLM(script)
    sim = SimulationRunner(simulator or NumericWellSimulator())
    deps = AgentDeps(llm=llm, store=FakeStore([]), simulation=sim)
    graph = build_graph(deps)
    final = await graph.ainvoke(initial_state(QUESTION, None, well),
                                config={"recursion_limit": RECURSION_LIMIT})
    return final, llm


def nodes(final: dict) -> list[str]:
    return [event.node for event in final["trace"]]


def test_entry_routes_on_the_attached_well() -> None:
    assert routing.entry(initial_state(QUESTION, None, WELL)) == "simulate"
    assert routing.entry(initial_state(QUESTION)) == "analyze"


@pytest.mark.anyio
async def test_well_skips_the_research_chain_and_uses_one_haiku_call(
        ) -> None:
    final, llm = await run({"interpret": [ANSWER]})
    answer = final["answer"]
    assert nodes(final) == ["simulate", "interpret", "finalize"]
    assert llm.roles() == ["interpret"]
    assert final["llm_calls"] == 1
    assert answer.status == "answered"
    assert f"({WELLSIM_LABEL})" in answer.text
    assert answer.simulation["recommended_rate"] is not None
    assert any("single-phase" in c for c in answer.caveats)


@pytest.mark.anyio
async def test_haiku_gets_the_question_and_the_labelled_passage() -> None:
    _, llm = await run({"interpret": [ANSWER]})
    prompt = llm.calls[0][1]
    assert QUESTION in prompt
    assert f"[C1] ({WELLSIM_LABEL})" in prompt
    assert "Tasa recomendada" in prompt


@pytest.mark.anyio
async def test_answer_language_follows_the_model() -> None:
    spanish = SimulationAnswer(language="es", text="Tasa recomendada [C1].")
    final, _ = await run({"interpret": [spanish]})
    assert final["language"] == "es"
    assert any("monofásico" in c for c in final["answer"].caveats)


@pytest.mark.anyio
async def test_busy_simulator_gives_a_partial_answer_without_llm() -> None:
    final, llm = await run({}, simulator=BusySimulator())
    answer = final["answer"]
    assert nodes(final) == ["simulate", "finalize"]
    assert llm.calls == []
    assert answer.status == "partial"
    assert answer.simulation is None
    assert any("simulator is busy" in c for c in answer.caveats)
    assert not answer.text.rstrip().endswith(":")


@pytest.mark.anyio
async def test_failed_interpretation_is_partial() -> None:
    final, _ = await run({"interpret": [None]})
    assert final["answer"].status == "partial"
    assert final["answer"].simulation is not None


@pytest.mark.anyio
async def test_trace_keeps_no_question_text_or_parameters() -> None:
    final, _ = await run({"interpret": [ANSWER]})
    for event in final["trace"]:
        dumped = str(event.to_dict())
        assert QUESTION not in dumped
        assert "4000.0" not in dumped
