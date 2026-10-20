import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from fastapi.sse import ServerSentEvent

from config.exceptions import BusyError
from crocol.app.deps import AppContainer

LOGGER = logging.getLogger("crocol.api")
FAILED = "Crocol could not finish this answer; please try again"


@dataclass(frozen=True)
class Admitted:
    """A question that passed validation, limits and memory checks."""

    question: str
    image: bytes | None = None
    well: dict | None = None
    history: list[dict] = field(default_factory=list)
    ui_context: dict | None = None

    def args(self) -> tuple:

        return (self.question, self.image, 
                self.well, self.history,
                self.ui_context)


async def keep_image(state: AppContainer, trace_id: str,
                     image: bytes | None) -> None:
    """Store the sanitized image (72 h); a failure never breaks an answer."""
    if not image:
        return
    try:
        await asyncio.to_thread(state.images.save, trace_id, image)
    except Exception as exc:
        LOGGER.warning("image not stored: %s", type(exc).__name__)


async def settle(state: AppContainer, final: dict,
                 image: bytes | None) -> None:

    usage = final.get("usage") or {}
    state.spend.add_tokens(usage.get("tokens", 0))
    await keep_image(state, final["trace_id"], image)


async def answer_json(state: AppContainer, admitted: Admitted) -> dict:
    """One full answer; the run slot is held for the whole run."""
    try:
        async with state.slots.slot():
            final = await state.ask.ask(*admitted.args())
    except BusyError:
        state.spend.release()
        raise
    await settle(state, final, admitted.image)
    return final


def without_event(event: dict) -> dict:

    return {key: value for key, value in event.items() if key != "event"}


async def answer_events(state: AppContainer, admitted: Admitted,
                        request_id: str
                        ) -> AsyncIterator[ServerSentEvent]:
    """SSE: one `node` event per agent step, then `final` (or `error`)."""
    try:
        async with state.slots.slot():
            async for event in state.ask.stream(*admitted.args()):

                if event["event"] == "final":
                    await settle(state, event, admitted.image)
                    
                yield ServerSentEvent(event=event["event"],
                                      data=without_event(event))
                
    except BusyError as exc:
        state.spend.release()
        yield ServerSentEvent(event="error", data={
            "error": exc.public_message,
            "request_id": request_id})
        
    except Exception as exc:
        LOGGER.error("stream failed: %s", type(exc).__name__)
        
        yield ServerSentEvent(event="error", data={
            "error": FAILED, 
            "request_id": request_id}
                              )
