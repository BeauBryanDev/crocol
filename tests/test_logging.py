import logging

import pytest
from test_role_router import Out, ScriptedProvider
from test_usecases import QUESTION, MemoryTraces, use_case

from config.logging import ContextFilter, setup_logging
from crocol.application.agent.graph import brief
from crocol.infrastructure.llm.role_router import RoleRouter


@pytest.fixture
def records(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    caplog.handler.addFilter(ContextFilter())
    caplog.set_level(logging.INFO, logger="crocol")
    return caplog


@pytest.mark.anyio
async def test_question_logs_carry_trace_id_and_no_user_text(
        records: pytest.LogCaptureFixture) -> None:
    events = [e async for e in use_case(MemoryTraces()).stream(QUESTION)]
    trace_id = events[-1]["trace_id"]

    assert records.records
    for record in records.records:
        assert "PREGUNTA_SECRETA" not in record.getMessage()
        assert record.tid == trace_id

    messages = [r.getMessage() for r in records.records]
    assert any(m.startswith("node analyze status=ok") for m in messages)
    assert any(m.startswith("question mode=quick") for m in messages)
    assert any(m.startswith("question role=synthesize") for m in messages)


@pytest.mark.anyio
async def test_router_logs_each_attempt_with_tokens_and_time(
        records: pytest.LogCaptureFixture) -> None:
    claude = ScriptedProvider([None, Out(value="ok")])
    result = await RoleRouter(claude).generate("analyze", "s", "u", Out)

    lines = [r for r in records.records if r.name == "crocol.llm"]
    assert result.ok
    assert result.latency_ms >= 0
    assert [r.levelname for r in lines] == ["WARNING", "INFO"]
    assert "status=invalid" in lines[0].getMessage()
    assert "status=ok in=0 out=0" in lines[1].getMessage()
    assert lines[1].getMessage().endswith("try=2")


def test_brief_keeps_scalars_and_skips_long_lists() -> None:
    summary = {"kept": 12, "hits": [25, 25], "chunk_ids": list("abcdefghij"),
               "policy": "prose_tables", "nested": {"a": 1}}

    assert brief(summary) == "kept=12 hits=25,25 policy=prose_tables"


def test_setup_logging_is_idempotent() -> None:
    root = logging.getLogger()
    saved = root.handlers[:], root.level
    try:
        setup_logging("debug")
        setup_logging("info")
        assert len(root.handlers) == 1
        assert root.level == logging.INFO
    finally:
        root.handlers[:] = saved[0]
        root.setLevel(saved[1])
