import asyncio
import json
from dataclasses import dataclass, field

import pytest
from fakes import FakeLLM, FakeStore
from pydantic import BaseModel
from test_graph import ANALYSIS, DRAFT, PASSED, ROWS, SUFFICIENT

from crocol.application.agent.graph import build_graph
from crocol.application.agent.state import AgentDeps
from crocol.application.ports.llm import LLMResult
from crocol.application.usecases import ask_questions
from crocol.application.usecases.ask_questions import AskQuestion
from crocol.application.usecases.get_trace import GetTrace

QUESTION = "PREGUNTA_SECRETA sobre el ambiente de la Formación Mugrosa"


@dataclass
class MemoryTraces:
    saved: list[dict] = field(default_factory=list)
    fail: bool = False

    async def save(self, record: dict) -> None:
        if self.fail:
            raise ConnectionError("database down")
        self.saved.append(record)

    async def get(self, trace_id: str) -> dict | None:
        return None


class SlowLLM(FakeLLM):
    async def generate(self,
                       role: str,
                       system: str,
                       user: str,
                       schema: type[BaseModel],
                       images: tuple = ()
                       ) -> LLMResult:
        await asyncio.sleep(0.2)
        return await super().generate(role, system, user, schema, images)


def use_case(traces: MemoryTraces, llm: FakeLLM | None = None) -> AskQuestion:
    llm = llm or FakeLLM({"analyze": [ANALYSIS], "grade": [SUFFICIENT],
                          "synthesize": [DRAFT], "verify": [PASSED]})
    graph = build_graph(AgentDeps(llm=llm, store=FakeStore(ROWS)))
    return AskQuestion(graph, traces)


@pytest.mark.anyio
async def test_stream_emits_node_events_then_final() -> None:
    traces = MemoryTraces()
    events = [e async for e in use_case(traces).stream(QUESTION)]
    assert all(e["event"] == "node" for e in events[:-1])
    assert events[0]["node"] == "analyze"
    final = events[-1]
    assert final["event"] == "final"
    assert final["status"] == "answered"
    assert final["citations"]
    assert len(traces.saved) == 1
    assert traces.saved[0]["trace_id"] == final["trace_id"]


@pytest.mark.anyio
async def test_saved_record_contains_no_user_text() -> None:
    traces = MemoryTraces()
    final = await use_case(traces).ask(QUESTION)
    dumped = json.dumps(traces.saved[0], default=str)
    assert "PREGUNTA_SECRETA" not in dumped
    assert "ambiente Mugrosa" not in dumped
    assert "fluvial meándrica" not in dumped
    assert final["answer"] not in dumped
    stages = {row["stage"] for row in traces.saved[0]["chunks"]}
    assert stages == {"retrieved", "graded", "cited"}


@pytest.mark.anyio
async def test_failed_save_still_returns_the_answer() -> None:
    final = await use_case(MemoryTraces(fail=True)).ask(QUESTION)
    assert final["status"] == "answered"


@pytest.mark.anyio
async def test_total_timeout_returns_partial_and_is_logged(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ask_questions, "TOTAL_TIMEOUT_S",
                        {"quick": 0.3, "research": 0.3})
    traces = MemoryTraces()
    llm = SlowLLM({"analyze": [ANALYSIS], "grade": [SUFFICIENT],
                   "synthesize": [DRAFT], "verify": [PASSED]})
    final = await use_case(traces, llm).ask(QUESTION)
    assert final["status"] == "partial"
    assert traces.saved[0]["status"] == "partial"


@pytest.mark.anyio
async def test_get_trace_rejects_invalid_ids() -> None:
    assert await GetTrace(MemoryTraces()).run("not-a-uuid") is None
    assert await GetTrace(None).run(
        "1b4e28ba-2fa1-11d2-883f-0016d3cca427") is None
