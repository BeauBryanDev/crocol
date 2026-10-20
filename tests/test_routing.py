import pytest

from config.roles import LLM_CALL_BUDGET, MAX_ATTEMPTS
from crocol.application.agent import routing
from crocol.application.agent.state import initial_state
from crocol.domains.models.chunks import Chunk

EVIDENCE = [Chunk("c1", "d1", "texto", "A, 2010", label="C1")]


def state_with(**fields: object) -> dict:
    state = dict(initial_state("pregunta"))
    state.update(fields)
    return state


def test_after_analyze_runs_every_retriever() -> None:
    assert routing.after_analyze(state_with()) == routing.RETRIEVERS


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"grade": {"sufficient": True}, "evidence": EVIDENCE},
         "synthesize"),
        ({"grade": {"sufficient": True}, "evidence": []}, "rewrite"),
        ({"grade": {"sufficient": False}, "attempts": 0}, "rewrite"),
        ({"grade": {"sufficient": False}, "attempts": MAX_ATTEMPTS},
         "abstain"),
        ({"grade": None, "attempts": 1}, "rewrite"),
        ({"grade": {"sufficient": True}, "evidence": EVIDENCE,
          "llm_calls": LLM_CALL_BUDGET["quick"] - 1}, "finalize"),
        ({"grade": {"sufficient": False},
          "llm_calls": LLM_CALL_BUDGET["quick"] - 3}, "abstain"),
        ({"grade": {"sufficient": False}, "evidence": EVIDENCE,
          "llm_calls": LLM_CALL_BUDGET["quick"] - 2}, "synthesize"),
        ({"grade": {"sufficient": False}, "evidence": EVIDENCE,
          "attempts": MAX_ATTEMPTS}, "synthesize"),
        ({"grade": {"sufficient": False}, "evidence": EVIDENCE,
          "llm_calls": LLM_CALL_BUDGET["quick"] - 1}, "abstain"),
    ],
)
@pytest.mark.usefixtures("corpus_only")
def test_after_grade(fields: dict, expected: str) -> None:
    assert routing.after_grade(state_with(**fields)) == expected


@pytest.mark.usefixtures("corpus_only")
def test_after_rewrite_rejects_repeated_strategy() -> None:
    assert routing.after_rewrite(state_with(repeated=True)) == "abstain"
    assert routing.after_rewrite(state_with()) == routing.RETRIEVERS


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"draft": None}, "finalize"),
        ({"draft": {"text": "x", "insufficient": True}}, "abstain"),
        ({"draft": {"text": "x"}, "verified": True}, "finalize"),
        ({"draft": {"text": "x"}, "verified": False}, "revise"),
        ({"draft": {"text": "x"}, "verified": False, "revised": True},
         "finalize"),
        ({"draft": {"text": "x"}, "verified": False,
          "llm_calls": LLM_CALL_BUDGET["quick"] - 1}, "finalize"),
    ],
)
def test_after_verify(fields: dict, expected: str) -> None:
    assert routing.after_verify(state_with(**fields)) == expected
