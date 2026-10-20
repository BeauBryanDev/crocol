import asyncio
import json
import time
from typing import Annotated

from fastapi import Form, Request, UploadFile
from pydantic import TypeAdapter, ValidationError

from config.exceptions import (
    ImageTooLargeError,
    QuestionError,
    RateLimitedError,
    UnavailableError,
)
from config.roles import MEMORY_TURNS
from config.settings import (
    QUESTION_MAX_CHARS,
    QUESTION_MIN_CHARS,
    VISION_MAX_BYTES,
    get_settings,
)
from crocol.app.api.answers import Admitted
from crocol.app.api.guards import RateLimiter
from crocol.app.deps import AppContainer
from crocol.app.schemas import (
    ChatRequest,
    MemoryRecord,
    WellParams,
    WellSweepRequest,
)
from crocol.infrastructure.simulation.adapter import web_input, web_options
from crocol.infrastructure.vision.onnx_segmenter import sanitize

RUN_LIMIT_MESSAGE = "too many simulations; please wait a minute"
SWEEP_LIMIT_MESSAGE = "the daily sweep limit for this address is used up"
MAX_HISTORY_FORM_CHARS = 16_000
HISTORY = TypeAdapter(list[MemoryRecord])


def container(request: Request) -> AppContainer:

    return request.app.state.container


def client_ip(request: Request) -> str:
    """Socket address, or the proxy's X-Forwarded-For entry when trusted."""
    host = request.client.host if request.client else "unknown"
    trusted = get_settings().crocol_trusted_proxy
    forwarded = request.headers.get("x-forwarded-for")
    if trusted and host == trusted and forwarded:
        return forwarded.split(",")[-1].strip()
    return host


def admit_question(request: Request) -> None:
    """Per-IP rate limit, then a reserved slot in the daily budget."""
    state = container(request)
    state.question_limiter.check(client_ip(request))
    state.spend.reserve()


def admit_other(request: Request) -> None:

    container(request).other_limiter.check(client_ip(request))


def clean_question(question: str) -> str:

    text = " ".join(question.split())
    if not QUESTION_MIN_CHARS <= len(text) <= QUESTION_MAX_CHARS:
        raise QuestionError()
    return text


async def read_image(image: UploadFile) -> bytes:
    """Upload bytes, read with a hard cap so a huge file is never loaded."""
    data = await image.read(VISION_MAX_BYTES + 1)
    if len(data) > VISION_MAX_BYTES:
        raise ImageTooLargeError()
    return data


def well_dict(well: WellParams) -> dict:
    """Form fields left empty are dropped, so the simulator defaults apply."""
    return well.model_dump(exclude_none=True)


def check_limit(limiter: RateLimiter, request: Request,
                message: str) -> None:

    try:
        limiter.check(client_ip(request))
    except RateLimitedError as exc:
        raise RateLimitedError(exc.retry_after, message) from exc


def require_simulator(request: Request) -> None:

    if container(request).simulation is None:
        raise UnavailableError()


def recall(request: Request, records: list[MemoryRecord]) -> list[dict]:
    """Only records this server signed and that are still fresh survive."""
    signer = container(request).memory
    if signer is None or not records:
        return []
    raw = [record.model_dump() for record in records]
    return signer.verified(raw, int(time.time()), MEMORY_TURNS)


def form_history(text: str) -> list[MemoryRecord]:
    """Multipart history (JSON text); malformed memory is just forgotten."""
    if not text or len(text) > MAX_HISTORY_FORM_CHARS:
        return []
    try:
        records = HISTORY.validate_python(json.loads(text))
    except (ValueError, ValidationError):
        return []
    return records[-MEMORY_TURNS:]


def chat_admission(body: ChatRequest, request: Request) -> Admitted:
    """Validated question, optional well and memory, admitted last."""
    question = clean_question(body.question)
    well = None
    if body.well is not None:
        require_simulator(request)
        well = well_dict(body.well)
        web_input(well, for_sweep=True)
    ui = None
    if body.ui_context is not None:
        ui = body.ui_context.model_dump(exclude_none=True) or None
    history = recall(request, body.history)
    admit_question(request)
    return Admitted(question=question, well=well, history=history,
                    ui_context=ui)


async def image_admission(request: Request,
                          question: Annotated[str, Form()],
                          image: UploadFile,
                          history: Annotated[str, Form()] = ""
                          ) -> Admitted:
    """Validated question and sanitized image (EXIF removed), admitted."""
    text = clean_question(question)
    raw = await read_image(image)
    clean = await asyncio.to_thread(sanitize, raw)
    remembered = recall(request, form_history(history))
    admit_question(request)

    return Admitted(question=text, 
                    image=clean, 
                    history=remembered)


def run_admission(body: WellParams, request: Request) -> dict:
    """Physics checked before the rate limit, so a typo costs no run."""
    require_simulator(request)
    params = well_dict(body)
    web_input(params)
    check_limit(container(request).run_limiter, request,
                RUN_LIMIT_MESSAGE)
    return params


def sweep_admission(body: WellSweepRequest,
                    request: Request) -> tuple[dict, dict]:

    require_simulator(request)
    params = well_dict(body.well)
    options = body.options.model_dump(exclude_none=True)
    web_input(params, for_sweep=True)
    web_options(options)
    check_limit(container(request).sweep_limiter, request,
                SWEEP_LIMIT_MESSAGE)
    return params, options
