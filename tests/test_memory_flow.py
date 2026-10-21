import io
import time
import json

import pytest
from fakes import FakeLLM, FakeStore
from PIL import Image
from test_api_routes import client_for, make_state
from test_graph import ANALYSIS, DRAFT, PASSED, ROWS, SUFFICIENT
from test_usecases import MemoryTraces

from config.exceptions import BudgetExceededError
from crocol.app.api.guards import SpendCounter
from crocol.application.agent.graph import build_graph
from crocol.application.agent.nodes.analyze import analyze
from crocol.application.agent.state import AgentDeps, initial_state
from crocol.application.usecases.ask_questions import AskQuestion
from crocol.domains.services.memory import MemorySigner

pytestmark = pytest.mark.anyio
KEY = b"m" * 32
FOLLOW_UP = "¿Y su porosidad?"
STANDALONE = "¿Cuál es la porosidad de la Formación Mugrosa?"


def follow_up_analysis(**extra):
    fields = {"follows_up": True, "standalone_question": STANDALONE,
              "prior_coverage": "Edad oligocena y ambiente fluvial.",
              **extra}
    return ANALYSIS.model_copy(update=fields)


def turn(ts: int, question: str = "¿Qué es Mugrosa?") -> dict:
    return {"v": 1, "ts": ts, "kind": "text", "language": "es",
            "question": question, "standalone": question,
            "summary": "Mugrosa es fluvial.", "entities": ["Mugrosa"],
            "facts": {}}


def signer() -> MemorySigner:
    return MemorySigner(KEY, 24 * 3600)


async def test_analyze_rewrites_a_follow_up_with_memory() -> None:
    llm = FakeLLM({"analyze": [follow_up_analysis()]})
    state = initial_state(FOLLOW_UP, history=[turn(1)])
    update, summary = await analyze(state, AgentDeps(llm=llm,
                                                     store=FakeStore([])))
    assert update["question"] == STANDALONE
    assert update["query_variants"][0] == STANDALONE
    assert update["follows_up"] is True and summary["history"] == 1
    assert "CONVERSATION" in llm.calls[0][1]


async def test_analyze_ignores_follow_up_flag_without_memory() -> None:
    llm = FakeLLM({"analyze": [follow_up_analysis()]})
    update, _ = await analyze(initial_state(FOLLOW_UP),
                              AgentDeps(llm=llm, store=FakeStore([])))
    assert update["question"] == FOLLOW_UP
    assert update["follows_up"] is False and update["prior_coverage"] == ""


async def test_writer_gets_digest_but_never_the_records() -> None:
    llm = FakeLLM({"analyze": [follow_up_analysis()],
                   "grade": [SUFFICIENT], "synthesize": [DRAFT],
                   "verify": [PASSED]})
    graph = build_graph(AgentDeps(llm=llm, store=FakeStore(ROWS)))
    use_case = AskQuestion(graph, MemoryTraces(), signer())
    final = await use_case.ask(FOLLOW_UP, history=[turn(1)])
    writer = [user for role, user in llm.calls if role == "synthesize"][0]
    assert "CONVERSATION DIGEST" in writer
    assert f"QUESTION:\n{STANDALONE}" in writer
    assert "Mugrosa es fluvial." not in writer
    memory = final["memory"]
    assert memory["question"] == FOLLOW_UP
    assert memory["standalone"] == STANDALONE
    assert signer().verified([memory], memory["ts"], 3)


async def test_memory_is_not_issued_without_a_key() -> None:
    llm = FakeLLM({"analyze": [ANALYSIS], "grade": [SUFFICIENT],
                   "synthesize": [DRAFT], "verify": [PASSED]})
    graph = build_graph(AgentDeps(llm=llm, store=FakeStore(ROWS)))
    final = await AskQuestion(graph, MemoryTraces()).ask("¿Qué es Mugrosa?")
    assert final["memory"] is None


async def test_saved_trace_has_no_memory_text() -> None:
    llm = FakeLLM({"analyze": [follow_up_analysis()],
                   "grade": [SUFFICIENT], "synthesize": [DRAFT],
                   "verify": [PASSED]})
    traces = MemoryTraces()
    graph = build_graph(AgentDeps(llm=llm, store=FakeStore(ROWS)))
    await AskQuestion(graph, traces, signer()).ask(
        FOLLOW_UP, history=[turn(1, "PREGUNTA_PREVIA_SECRETA")])
    dumped = json.dumps(traces.saved[0], default=str)
    assert "PREGUNTA_PREVIA_SECRETA" not in dumped
    assert "porosidad" not in dumped


async def test_api_keeps_signed_turns_drops_forged(tmp_path) -> None:
    state = make_state(tmp_path)
    state.memory = signer()
    now = int(time.time())
    good = signer().sign(turn(now))
    forged = {**signer().sign(turn(now - 5)), "summary": "forged"}
    body = {"question": FOLLOW_UP, "history": [forged, good],
            "ui_context": {"formation": "Mugrosa"}}
    async with client_for(state) as client:
        response = await client.post("/api/chat", json=body)
    assert response.status_code == 200
    history, ui = state.ask.histories[0]
    assert [r["ts"] for r in history] == [now]
    assert "sig" not in history[0]
    assert ui == {"formation": "Mugrosa"}


async def test_api_refuses_more_than_three_turns(tmp_path) -> None:
    state = make_state(tmp_path)
    turns = [signer().sign(turn(i)) for i in range(4)]
    async with client_for(state) as client:
        response = await client.post("/api/chat", json={
            "question": FOLLOW_UP, "history": turns})
    assert response.status_code == 422
    assert state.ask.calls == []


async def test_image_form_history_is_verified(tmp_path) -> None:
    state = make_state(tmp_path)
    state.memory = signer()
    now = int(time.time())
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), (120, 110, 100)).save(buffer, "PNG")
    history = json.dumps([signer().sign(turn(now)), {"bad": 1}])
    async with client_for(state) as client:
        response = await client.post(
            "/api/image", data={"question": "¿y esta roca?",
                                "history": history},
            files={"image": ("r.png", buffer.getvalue(), "image/png")})
    assert response.status_code == 200
    assert state.ask.histories[0][0] == []


async def test_spend_refuses_a_run_that_would_pass_the_cap() -> None:
    spend = SpendCounter(30, 1_000_000, run_estimate=40_000)
    spend.add_tokens(950_000)
    spend.reserve()
    spend.add_tokens(15_000)
    with pytest.raises(BudgetExceededError):
        spend.reserve()
