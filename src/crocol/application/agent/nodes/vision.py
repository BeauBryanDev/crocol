import asyncio

from crocol.application.agent.nodes.retrieve import skipped
from crocol.application.agent.schemas import VisualDiagnosis
from crocol.application.agent.state import (
    AgentDeps,
    AgentState,
    ChannelResult,
    ask,
)
from crocol.application.tools.image_analysis import (
    crack_chunk,
    interpretation_chunk,
    outputs_text,
)

LANGUAGES = {
    "es": "Spanish",
    "en": "English",
}


def vision_request(state: AgentState, outputs: str) -> str:

    language = LANGUAGES.get(state.get("language", "es"), "Spanish")
    return (
        f"ANSWER LANGUAGE: {language}\n\n"
        f"USER QUESTION ABOUT THE IMAGE:\n{state['question']}\n\n"
        f"OUTPUTS OF THE CUSTOM CRACK DETECTION MODEL:\n{outputs}"
    )


def interpretation_of(parsed: object) -> dict | None:
    """Gemini's reading of the photo, shown to the user, never persisted."""
    if not isinstance(parsed, VisualDiagnosis):
        return None
    return {
        "is_rock": parsed.is_rock,
        "rock_description": parsed.rock_description,
        "diagnosis": parsed.diagnosis,
        "fluid_flow": parsed.fluid_flow,
        "confidence": parsed.confidence,
    }


def failed(state: AgentState, reason: str) -> tuple[dict, dict]:

    channel = ChannelResult(attempt=state.get("attempts", 0),
                            status="error", lists=[], detail=reason)
    
    return {"channels": {"vision": channel}}, {"status": "error",
                                                "error": reason}


async def retrieve_vision(state: AgentState,
                          deps: AgentDeps
                          ) -> tuple[dict, dict]:
    """CNN crack segmentation, then a multimodal reading of the photo."""
    image = state.get("image")
    if not image:
        return skipped(state, "vision", "no image attached")
    if deps.vision is None:
        return skipped(state, "vision", "no vision model configured")

    try:
        analysis = await asyncio.to_thread(deps.vision.analyze, image)
    except ValueError:
        return failed(state, "invalid_image")

    report = analysis.report
    chunks = [crack_chunk(report)]
    parsed, usage = await ask(
        deps, "vision", "vision_describer",
        vision_request(state, outputs_text(report)), 
        VisualDiagnosis,
        images=((analysis.preview_jpeg, "image/jpeg"),))
    if isinstance(parsed, VisualDiagnosis):
        chunks.append(interpretation_chunk(
            parsed.rock_description, parsed.diagnosis, parsed.fluid_flow,
            usage["model"]))

    channel = ChannelResult(attempt=state.get("attempts", 0), status="ok",
                            lists=[chunks], detail="")
    update = {
        "channels": {"vision": channel},
        "vision_report": report,
        "overlay": analysis.overlay_webp,
        "mask": analysis.mask_webp,
        "vision_interpretation": interpretation_of(parsed),
        "llm_calls": 1,
        "llm_usage": [usage],
    }
    summary = {
        "model": report.model,
        "tiles": report.tiles,
        "cnn_ms": report.elapsed_ms,
        "interpreted": isinstance(parsed, VisualDiagnosis),
        "cross_family": usage["cross_family"],
    }
    return update, summary
