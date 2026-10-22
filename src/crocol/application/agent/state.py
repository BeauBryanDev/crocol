import hashlib
import operator
from dataclasses import dataclass
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel

from crocol.application.agent.schemas import Prompt, load_prompt
from crocol.application.ports.documents import DocumentStore
from crocol.application.ports.graph import GraphSearch
from crocol.application.ports.llm import LLM, Images, LLMResult
from crocol.application.ports.production import ProductionSearch
from crocol.application.ports.reranker import Reranker
from crocol.application.ports.spatial import SpatialSearch
from crocol.application.ports.vector_search import VectorSearch
from crocol.application.ports.vision import CrackAnalyzer
from crocol.application.tools.well_simulation import SimulationRunner
from crocol.domains.models.answers import Answer
from crocol.domains.models.chunks import Chunk
from crocol.domains.models.claims import Claim
from crocol.domains.models.cracks import CrackReport
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
    user_question: str
    history: list[dict]
    ui_context: dict[str, str] | None
    follows_up: bool
    prior_coverage: str
    language: str
    mode: Literal["quick", "research"]
    intents: list[str]
    corpus_scope: Literal["core", "all"]
    chunk_policy: Literal["prose_tables", "numeric"]
    query_type: Literal["exact", "conceptual", "cross_language"]
    query_variants: list[str]
    bm25_query: str | None
    places: list[dict]
    well_query: dict[str, Any] | None
    production: list[dict]
    entities: list[dict]
    channels: Annotated[dict[str, ChannelResult], merge_channels]
    chunks: list[Chunk]
    evidence: list[Chunk]
    grade: dict[str, Any] | None
    attempts: int
    strategies: list[str]
    repeated: bool
    partial_evidence: bool
    draft: dict[str, Any] | None
    claims: list[Claim]
    verified: bool
    revised: bool
    conflicts: list[dict]
    sub_questions: list[dict]
    sub_results: Annotated[list[dict], operator.add]
    image: bytes | None
    well_params: dict[str, Any] | None
    simulation: dict[str, Any] | None
    vision_report: CrackReport | None
    overlay: bytes
    mask: bytes
    vision_interpretation: dict[str, Any] | None
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
    vision: CrackAnalyzer | None = None
    reranker: Reranker | None = None
    production: ProductionSearch | None = None
    simulation: SimulationRunner | None = None


def initial_state(question: str,
                  image: bytes | None = None,
                  well: dict[str, Any] | None = None,
                  history: list[dict] | None = None,
                  ui_context: dict[str, str] | None = None) -> AgentState:
    return {
        "question": question,
        "user_question": question,
        "history": list(history or []),
        "ui_context": ui_context,
        "follows_up": False,
        "prior_coverage": "",
        "language": "es",
        "mode": "quick",
        "corpus_scope": "core",
        "chunk_policy": "prose_tables",
        "query_type": "conceptual",
        "query_variants": [question],
        "bm25_query": None,
        "places": [],
        "well_query": None,
        "production": [],
        "entities": [],
        "channels": {},
        "chunks": [],
        "evidence": [],
        "grade": None,
        "attempts": 0,
        "strategies": [],
        "repeated": False,
        "partial_evidence": False,
        "draft": None,
        "claims": [],
        "verified": False,
        "revised": False,
        "conflicts": [],
        "sub_questions": [],
        "sub_results": [],
        "image": image,
        "well_params": well,
        "simulation": None,
        "vision_report": None,
        "overlay": b"",
        "mask": b"",
        "vision_interpretation": None,
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
    key = "|".join([*normalized,
                    corpus_scope, 
                    chunk_policy,
                    query_type])
    
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def usage_of(role: str, 
             prompt: Prompt,
             result: LLMResult
             ) -> dict:
    # TODO: add a "cost" field to LLMResult
    return {
        "role": role,
        "prompt": f"{prompt.name}@{prompt.version}",
        "model": result.model,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "latency_ms": result.latency_ms,
        "cross_family": result.cross_family,
        "ok": result.ok,
    }


async def ask(
    deps: AgentDeps,
    role: str,
    prompt_name: str,
    user: str,
    schema: type[BaseModel],
    images: Images = (),
) -> tuple[BaseModel | None, dict]:
    """Call one model role; returns the parsed output (or None) and usage."""
    prompt = load_prompt(prompt_name)
    result = await deps.llm.generate(role,
                                     prompt.text,
                                     user,
                                     schema,
                                     images)
    
    return result.parsed, usage_of(role, prompt, result)


def verify_failed(state: AgentState) -> bool:
    """The claim checker crashed or timed out (its draft stands unchecked)."""
    return any(e.startswith("verify:") for e in state.get("errors") or [])


def graph_mentions(state: AgentState) -> list[dict]:
    """Analyzer entities first, then places, one per name."""
    mentions, seen = [], set()
    
    for item in [*(state.get("entities") or []), *(state.get("places") or [])]:
        
        key = item["name"].strip().casefold()
        if key and key not in seen:
            seen.add(key)
            mentions.append(item)
            
    return mentions
