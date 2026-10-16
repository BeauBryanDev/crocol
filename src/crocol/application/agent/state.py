import hashlib
import operator
from dataclasses import dataclass
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel

from crocol.application.agent.schemas import Prompt, load_prompt
from crocol.application.ports.documents import DocumentStore
from crocol.application.ports.graph import GraphSearch
from crocol.application.ports.llm import LLM, LLMResult
from crocol.application.ports.spatial import SpatialSearch
from crocol.application.ports.vector_search import VectorSearch
from crocol.domains.models.answers import Answer
from crocol.domains.models.chunks import Chunk
from crocol.domains.models.claims import Claim
from crocol.domains.models.traces import TraceEvent


class ChannelResult(TypedDict):
    attempt: int
    status: str
    lists: list[list[Chunk]]
    detail: str


def merge_channels(
    old: dict[str, ChannelResult] | None,
    new: dict[str, ChannelResult] | None,
) -> dict[str, ChannelResult]:
    return {**(old or {}), **(new or {})}


class AgentState(TypedDict, total=False):
    question: str
    language: str
    mode: Literal["quick", "research"]
    intents: list[str]
    corpus_scope: Literal["core", "all"]
    chunk_policy: Literal["prose_tables", "numeric"]
    query_type: Literal["exact", "conceptual", "cross_language"]
    query_variants: list[str]
    bm25_query: str | None
    channels: Annotated[dict[str, ChannelResult], merge_channels]
    chunks: list[Chunk]
    evidence: list[Chunk]
    grade: dict[str, Any] | None
    attempts: int
    strategies: list[str]
    repeated: bool
    draft: dict[str, Any] | None
    claims: list[Claim]
    verified: bool
    revised: bool
    conflicts: list[dict]
    answer: Answer | None
    partial: bool
    llm_calls: Annotated[int, operator.add]
    llm_usage: Annotated[list[dict], operator.add]
    errors: Annotated[list[str], operator.add]
    trace: Annotated[list[TraceEvent], operator.add]


@dataclass(frozen=True)
class AgentDeps:
    llm: LLM
    store: VectorSearch
    documents: DocumentStore | None = None
    spatial: SpatialSearch | None = None
    graph: GraphSearch | None = None


def initial_state(question: str) -> AgentState:
    return {
        "question": question,
        "language": "es",
        "mode": "quick",
        "corpus_scope": "core",
        "chunk_policy": "prose_tables",
        "query_type": "conceptual",
        "query_variants": [question],
        "bm25_query": None,
        "channels": {},
        "chunks": [],
        "evidence": [],
        "grade": None,
        "attempts": 0,
        "strategies": [],
        "repeated": False,
        "draft": None,
        "claims": [],
        "verified": False,
        "revised": False,
        "conflicts": [],
        "answer": None,
        "partial": False,
        "llm_calls": 0,
        "llm_usage": [],
        "errors": [],
        "trace": [],
    }


def strategy_of(
    variants: list[str],
    corpus_scope: str,
    chunk_policy: str,
    query_type: str,
) -> str:
    """Fingerprint of one retrieval attempt; a retry must change it."""
    normalized = sorted(v.strip().casefold() for v in variants)
    key = "|".join([*normalized, corpus_scope, chunk_policy, query_type])
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def usage_of(role: str, prompt: Prompt, result: LLMResult) -> dict:
    return {
        "role": role,
        "prompt": f"{prompt.name}@{prompt.version}",
        "model": result.model,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cross_family": result.cross_family,
        "ok": result.ok,
    }


async def ask(
    deps: AgentDeps,
    role: str,
    prompt_name: str,
    user: str,
    schema: type[BaseModel],
) -> tuple[BaseModel | None, dict]:
    """Call one model role; returns the parsed output (or None) and usage."""
    prompt = load_prompt(prompt_name)
    result = await deps.llm.generate(role, prompt.text, user, schema)
    return result.parsed, usage_of(role, prompt, result)
