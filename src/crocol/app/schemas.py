from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class Usage(BaseModel):
    llm_calls: int
    tokens: int


class ChatResponse(BaseModel):
    trace_id: str
    status: str
    answer: str
    citations: list[str] = []
    references: list[str] = []
    caveats: list[str] = []
    conflicts: list[dict[str, Any]] = []
    overlay_webp_b64: str | None = None
    usage: Usage | None = None


class ErrorResponse(BaseModel):
    error: str
    request_id: str


class TraceResponse(BaseModel):
    trace_id: str
    created_at: str
    status: str
    language: str | None = None
    mode: str | None = None
    attempts: int | None = None
    llm_calls: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    latency_ms: int | None = None
    verification: dict[str, Any] | None = None
    conflicts: list[dict[str, Any]] | None = None
    trace: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    app_version: str | None = None


class CheckResult(BaseModel):
    ok: bool
    detail: str = ""


class ReadyResponse(BaseModel):
    ready: bool
    checks: dict[str, CheckResult]


class MetaResponse(BaseModel):
    app: str
    version: str
    models: dict[str, str]
    limits: dict[str, Any]
    usage_today: dict[str, int]
    citation_labels: dict[str, str]


class LocateResponse(BaseModel):
    kind: str
    name: str
    geojson: dict[str, Any] | None
    source: str
