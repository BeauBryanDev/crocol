import asyncio
from typing import Annotated

from fastapi import Form, Request, UploadFile

from config.exceptions import ImageTooLargeError, QuestionError
from config.settings import (
    QUESTION_MAX_CHARS,
    QUESTION_MIN_CHARS,
    VISION_MAX_BYTES,
    get_settings,
)
from crocol.app.deps import AppContainer
from crocol.app.schemas import ChatRequest
from crocol.infrastructure.vision.onnx_segmenter import sanitize


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


def chat_admission(body: ChatRequest, request: Request) -> str:
    """Validated question, admitted only after validation passes."""
    question = clean_question(body.question)
    admit_question(request)
    return question


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
