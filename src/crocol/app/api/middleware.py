import hashlib
import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from config.exceptions import CrocolError
from config.settings import MAX_REQUEST_BYTES
from crocol.app.api.deps import client_ip

LOGGER = logging.getLogger("crocol.access")
REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}
IP_SALT = uuid.uuid4().hex

# FastAPI  http middleware file

def request_id_of(request: Request) -> str:

    incoming = request.headers.get("x-request-id", "")
    if REQUEST_ID.match(incoming):
        return incoming
    return uuid.uuid4().hex


def ip_hash(ip: str) -> str:
    """Salted per process, so logs can group clients without storing IPs."""
    return hashlib.sha256(f"{IP_SALT}{ip}".encode()).hexdigest()[:12]


def too_large(request: Request) -> bool:

    length = request.headers.get("content-length", "")
    return length.isdigit() and int(length) > MAX_REQUEST_BYTES


def error_body(error: CrocolError, request_id: str) -> JSONResponse:

    return JSONResponse(status_code=error.status_code, content={
        "error": error.public_message, "request_id": request_id})


async def request_context(request: Request,
                          call_next: Callable[[Request],
                          Awaitable[Response]]
                          ) -> Response:
    """Request id, size guard, security headers and a text-free access log."""
    started = time.perf_counter()
    request_id = request_id_of(request)
    request.state.request_id = request_id

    if too_large(request):
        error = CrocolError("the request is too large")
        error.status_code = 413
        response = error_body(error, request_id)
    else:
        response = await call_next(request)

    response.headers["X-Request-ID"] = request_id
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)

    LOGGER.info("%s %s %s %dms client=%s rid=%s",
                request.method,
                request.url.path, 
                response.status_code,
                (time.perf_counter() - started) * 1000,
                ip_hash(client_ip(request)),
                request_id)
    
    return response
