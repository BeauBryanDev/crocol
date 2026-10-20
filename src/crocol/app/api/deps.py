import asyncio
from typing import Annotated

from fastapi import Form, Request, UploadFile

from config.exceptions import (
    ImageTooLargeError,
    QuestionError,
    RateLimitedError,
    UnavailableError,
)
from config.settings import (
    QUESTION_MAX_CHARS,
    QUESTION_MIN_CHARS,
    VISION_MAX_BYTES,
    get_settings,
)
from crocol.app.api.guards import RateLimiter
from crocol.app.deps import AppContainer
from crocol.app.schemas import ChatRequest, WellParams, WellSweepRequest
from crocol.infrastructure.simulation.adapter import web_input, web_options
from crocol.infrastructure.vision.onnx_segmenter import sanitize

RUN_LIMIT_MESSAGE = "too many simulations; please wait a minute"
SWEEP_LIMIT_MESSAGE = "the daily sweep limit for this address is used up"


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


def chat_admission(body: ChatRequest,
                   request: Request) -> tuple[str, dict | None]:
    """Validated question and optional well, admitted only after both pass."""
    question = clean_question(body.question)
    well = None
    if body.well is not None:
        require_simulator(request)
        well = well_dict(body.well)
        web_input(well, for_sweep=True)
    admit_question(request)
    return question, well


async def image_admission(request: Request,
                          question: Annotated[str, Form()],
                          image: UploadFile
                          ) -> tuple[str, bytes]:
    """Validated question and sanitized image (EXIF removed), admitted."""
    text = clean_question(question)
    raw = await read_image(image)
    clean = await asyncio.to_thread(sanitize, raw)
    admit_question(request)
    return text, clean


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
