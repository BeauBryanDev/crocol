from collections.abc import AsyncIterable
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

from config.settings import API_PREFIX
from crocol.app.api.answers import Admitted, answer_events
from crocol.app.api.deps import chat_admission, container, image_admission
from crocol.app.api.routers.chat import ERRORS
from crocol.app.deps import AppContainer

router = APIRouter(prefix=API_PREFIX, tags=["stream"])
State = Annotated[AppContainer, Depends(container)]


@router.post("/chat/stream", response_class=EventSourceResponse,
             responses=ERRORS)
async def chat_stream(admitted: Annotated[Admitted,
                                          Depends(chat_admission)],
                      request: Request,
                      state: State
                      ) -> AsyncIterable[ServerSentEvent]:
    """SSE: `node` events while the agent works, then `final` or `error`."""
    async for event in answer_events(state, admitted,
                                     request.state.request_id):
        yield event


@router.post("/image/stream", response_class=EventSourceResponse,
             responses=ERRORS)
async def image_stream(admitted: Annotated[Admitted,
                                           Depends(image_admission)],
                       request: Request,
                       state: State
                       ) -> AsyncIterable[ServerSentEvent]:
    """SSE version of /image; the overlay arrives in the `final` event."""
    async for event in answer_events(state, admitted,
                                     request.state.request_id):
        yield event
