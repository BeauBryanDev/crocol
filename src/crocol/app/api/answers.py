import asyncio
import logging
from collections.abc import AsyncIterator

from fastapi.sse import ServerSentEvent

from config.exceptions import BusyError
from crocol.app.deps import AppContainer

LOGGER = logging.getLogger("crocol.api")
FAILED = "Crocol could not finish this answer; please try again"


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


async def answer_json(state: AppContainer,
                      question: str,
                      image: bytes | None,
                      well: dict | None = None) -> dict:
    """One full answer; the run slot is held for the whole run."""
    try:
        async with state.slots.slot():
            final = await state.ask.ask(question, image, well)
    except BusyError:
        state.spend.release()
        raise
    await settle(state, final, image)
    return final


def without_event(event: dict) -> dict:

    return {key: value for key, value in event.items() if key != "event"}


async def answer_events(state: AppContainer, question: str,
                        image: bytes | None,
                        request_id: str,
                        well: dict | None = None
                        ) -> AsyncIterator[ServerSentEvent]:
    """SSE: one `node` event per agent step, then `final` (or `error`)."""
    try:
        async with state.slots.slot():
            async for event in state.ask.stream(question, image, well):
                
                if event["event"] == "final":
                    await settle(state, event, image)
                    
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
