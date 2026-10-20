from typing import Annotated

from fastapi import APIRouter, Depends

from config.exceptions import NotFoundError
from config.settings import API_PREFIX
from crocol.app.api.answers import answer_json
from crocol.app.api.deps import (
    admit_other,
    chat_admission,
    container,
    image_admission,
)
from crocol.app.deps import AppContainer
from crocol.app.schemas import ChatResponse, ErrorResponse, TraceResponse

router = APIRouter(prefix=API_PREFIX, tags=["chat"])
ERRORS = {code: {"model": ErrorResponse}
          for code in (400, 413, 415, 422, 429, 503)}
State = Annotated[AppContainer, Depends(container)]


@router.post("/chat", response_model=ChatResponse, responses=ERRORS)
async def chat(admitted: Annotated[tuple[str, dict | None],
                                   Depends(chat_admission)],
               state: State
               ) -> dict:
    """Ask Crocol a question (optionally with a well) as one JSON answer."""
    question, well = admitted
    return await answer_json(state, question, None, well)


@router.post("/image", response_model=ChatResponse, responses=ERRORS)
async def image(admitted: Annotated[tuple[str, bytes],
                                    Depends(image_admission)],
                state: State
                ) -> dict:
    """Question plus a rock image (multipart): crack analysis and answer."""
    question, picture = admitted
    return await answer_json(state, question, picture)


@router.get("/traces/{trace_id}", response_model=TraceResponse,
            responses={404: {"model": ErrorResponse}},
            dependencies=[Depends(admit_other)])
async def trace(trace_id: str, state: State) -> dict:
    """The saved app log of one answer (no question or answer text)."""
    record = await state.get_trace.run(trace_id)
    if record is None:
        raise NotFoundError("trace not found")
    return record
