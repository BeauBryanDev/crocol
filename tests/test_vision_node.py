import base64

import pytest
from fakes import FakeLLM, FakeStore
from test_graph import ANALYSIS, PASSED, ROWS

from crocol.application.agent.graph import build_graph
from crocol.application.agent.nodes.vision import retrieve_vision
from crocol.application.agent.schemas import (
    DraftAnswer,
    Grade,
    VisualDiagnosis,
)
from crocol.application.agent.state import AgentDeps, initial_state
from crocol.application.tools.image_analysis import outputs_text
from crocol.domains.models.cracks import CrackAnalysis, CrackReport

REPORT = CrackReport(
    model="MobileNetV2-UNet v2.0.0", threshold=0.5, width_px=612,
    height_px=459, tiles=12, density_pct=4.54, fractal_dimension=1.417,
    fractal_r2=0.998, crack_count=3, total_length_px=812.0,
    mean_width_px=6.0, max_width_px=11.0, severity="high",
    mean_confidence=0.92, ambiguous_pct=3.9, elapsed_ms=1028,
    dominant_angles=((17.0, 0.79), (30.0, 0.15)), rose=(0.0,) * 18)
DIAGNOSIS = VisualDiagnosis(
    is_rock=True, rock_description="Arenisca gris de grano fino.",
    diagnosis="Fracturamiento moderado a alto en dos familias.",
    fluid_flow="El flujo está dominado por fracturas orientadas a 17°.",
    confidence="medium")


class FakeAnalyzer:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def analyze(self, image_bytes: bytes) -> CrackAnalysis:
        if self.fail:
            raise ValueError("not a readable image")
        return CrackAnalysis(report=REPORT, overlay_webp=b"RIFF-overlay",
                             mask_webp=b"RIFF-mask",
                             preview_jpeg=b"jpeg-preview")


def deps(llm: FakeLLM, analyzer: FakeAnalyzer | None) -> AgentDeps:
    return AgentDeps(llm=llm, store=FakeStore(ROWS), vision=analyzer)


def test_outputs_text_quotes_every_measurement() -> None:
    text = outputs_text(REPORT)
    for value in ("4.54 %", "1.417", "high", "17.0° (79 %)", "6.0 px"):
        assert value in text


@pytest.mark.anyio
async def test_no_image_skips_without_calls() -> None:
    llm = FakeLLM({})
    update, summary = await retrieve_vision(initial_state("q"),
                                            deps(llm, FakeAnalyzer()))
    assert summary == {"status": "skipped"}
    assert llm.calls == []


@pytest.mark.anyio
async def test_unreadable_image_is_an_error_channel() -> None:
    state = initial_state("q", image=b"garbage")
    update, summary = await retrieve_vision(
        state, deps(FakeLLM({}), FakeAnalyzer(fail=True)))
    assert summary["status"] == "error"
    assert update["channels"]["vision"]["status"] == "error"


@pytest.mark.anyio
async def test_image_question_runs_cnn_then_gemini_then_claude() -> None:
    grade = Grade(relevant=["C1", "C2", "C3", "C4"], sufficient=True,
                  missing="", reason="ok")
    draft = DraftAnswer(
        text="Arenisca gris; densidad 4.54 % y dimensión fractal 1.417, "
             "severidad high [C1, C2, C3, C4].",
        cited=["C1", "C2", "C3", "C4"])
    llm = FakeLLM({"analyze": [ANALYSIS], "vision": [DIAGNOSIS],
                   "grade": [grade], "synthesize": [draft],
                   "verify": [PASSED]})
    final = await build_graph(deps(llm, FakeAnalyzer())).ainvoke(
        initial_state("Describe esta roca", image=b"photo-bytes"))

    roles = llm.roles()
    assert roles.count("vision") == 1
    assert llm.images[roles.index("vision")] == 1
    assert final["llm_calls"] == 5
    assert "synthesize" in roles and "verify" in roles

    evidence_types = [c.doc_type for c in final["evidence"]]
    assert evidence_types[:2] == ["crack_model", "visual_interpretation"]

    answer = final["answer"]
    assert answer.overlay_webp == b"RIFF-overlay"
    assert "MobileNetV2-UNet" in answer.text
    assert any("píxeles" in c for c in answer.caveats)
    assert any("interpretación visual" in c for c in answer.caveats)

    summary = [e.summary for e in final["trace"]
               if e.node == "retrieve_vision"][0]
    assert set(summary) == {"model", "tiles", "cnn_ms", "interpreted",
                            "cross_family"}


@pytest.mark.anyio
async def test_saved_log_holds_no_image_or_vision_text() -> None:
    import json

    from test_usecases import MemoryTraces

    from crocol.application.usecases.ask_questions import AskQuestion

    grade = Grade(relevant=["C1"], sufficient=True, missing="", reason="ok")
    llm = FakeLLM({"analyze": [ANALYSIS], "vision": [DIAGNOSIS],
                   "grade": [grade], "verify": [PASSED]})
    traces = MemoryTraces()
    use_case = AskQuestion(build_graph(deps(llm, FakeAnalyzer())), traces)
    final = await use_case.ask("Describe esta roca", image=b"photo-bytes")

    dumped = json.dumps(traces.saved[0], default=str)
    assert "photo-bytes" not in dumped
    assert "Arenisca" not in dumped
    assert "4.54" not in dumped
    assert final["overlay_webp_b64"]

    vision = final["vision"]
    mask_b64 = base64.b64encode(b"RIFF-mask").decode()
    assert vision["report"]["density_pct"] == 4.54
    assert list(vision["report"]["rose"]) == [0.0] * 18
    assert vision["mask_webp_b64"] == mask_b64
    assert vision["interpretation"]["rock_description"].startswith("Arenisca")
    assert mask_b64 not in dumped


@pytest.mark.anyio
async def test_mask_kept_and_no_interpretation_when_gemini_fails() -> None:
    llm = FakeLLM({"vision": [None]})
    state = initial_state("Describe esta roca", image=b"photo-bytes")
    update, summary = await retrieve_vision(state, deps(llm, FakeAnalyzer()))
    assert update["mask"] == b"RIFF-mask"
    assert update["vision_interpretation"] is None
    assert summary["interpreted"] is False
