import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from config.exceptions import CrocolError, RateLimitedError
from config.settings import APP_VERSION, PURGE_EVERY_S, get_settings
from crocol.app.api.middleware import request_context
from crocol.app.api.routers import chat, health, stream
from crocol.app.api.routers import map as map_routes
from crocol.app.deps import AppContainer, build_container, seed_spend
from crocol.infrastructure.repository.pool import build_pool

LOGGER = logging.getLogger("crocol.api")
INVALID = "the request is not valid"


def request_id(request: Request) -> str:

    return getattr(request.state, "request_id", "")


def error_response(request: Request,
                   status: int,
                   message: str,
                   headers: dict | None = None
                   ) -> JSONResponse:

    return JSONResponse(status_code=status
                        , headers=headers, 
                        content={
                                "error": message,
                                "request_id": request_id(request)
                        })


async def crocol_error(request: Request, 
                       exc: CrocolError) -> JSONResponse:

    headers = None
    if isinstance(exc, RateLimitedError):
        headers = {"Retry-After": str(exc.retry_after)}
        
    return error_response(request, exc.status_code, exc.public_message,
                          headers)


async def invalid_request(request: Request,
                          exc: RequestValidationError) -> JSONResponse:
    """422 without echoing the input back (it may be the user's text)."""
    fields = sorted({str(error["loc"][-1]) for error in exc.errors()})
    message = f"{INVALID}: {', '.join(fields)}" if fields else INVALID
    
    return error_response(request, 422, message)


async def http_error(request: Request,
                     exc: HTTPException) -> JSONResponse:

    return error_response(request, 
                          exc.status_code, str(exc.detail),
                          getattr(exc, "headers", None))


async def unexpected(request: Request, exc: Exception) -> JSONResponse:

    LOGGER.error("unhandled %s rid=%s", type(exc).__name__,
                 request_id(request))
    
    return error_response(request, 500, CrocolError.public_message)


async def housekeeping(state: AppContainer) -> None:
    """Purge images older than 72 h and idle rate-limit entries, hourly."""
    while True:
        try:
            removed = await asyncio.to_thread(state.images.purge)
            if removed:
                LOGGER.info("purged %d stored images", removed)
        except Exception as exc:
            LOGGER.warning("image purge failed: %s", type(exc).__name__)
        state.question_limiter.forget_idle()
        state.other_limiter.forget_idle()
        await asyncio.sleep(PURGE_EVERY_S)


async def warm_vision(state: AppContainer) -> None:

    if state.vision is None:
        return
    try:
        await asyncio.to_thread(getattr, state.vision, "session")
    except Exception as exc:
        LOGGER.warning("vision model not loaded: %s", type(exc).__name__)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Pool, container, today's spend, ONNX warm-up and the purge task."""
    async with contextlib.AsyncExitStack() as stack:
        state = getattr(app.state, "container", None)
        if state is None:
            pool = build_pool()
            if pool is not None:
                await stack.enter_async_context(pool)
            state = build_container(pool)
            app.state.container = state
            await seed_spend(state)
            await warm_vision(state)

        task = asyncio.create_task(housekeeping(state))
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


def create_app() -> FastAPI:

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s "
                               "%(message)s")
    
    for noisy in ("httpx", "httpx2", "google_genai"):
        
        logging.getLogger(noisy).setLevel(logging.WARNING)
        
    settings = get_settings()
    
    docs = None if settings.production else "/api/docs"
    app = FastAPI(title="Crocol API", 
                  version=APP_VERSION,
                  lifespan=lifespan, 
                  docs_url=docs, 
                  redoc_url=None,
                  openapi_url=None if settings.production
                  else "/api/openapi.json")

    app.add_exception_handler(CrocolError, crocol_error)
    app.add_exception_handler(RequestValidationError, invalid_request)
    app.add_exception_handler(HTTPException, http_error)
    app.add_exception_handler(Exception, unexpected)

    app.middleware("http")(request_context)
    app.add_middleware(CORSMiddleware,
                       allow_origins=settings.cors_origins,
                       allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type", "X-Request-ID"],
                       expose_headers=["X-Request-ID", "Retry-After"],
                       allow_credentials=False,
                       max_age=600)

    for module in (chat, stream, 
                   health, map_routes):
        app.include_router(module.router)
        
    return app


app = create_app()
