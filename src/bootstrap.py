import os

os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
# The simulator's banded solves are too small to gain from BLAS threads.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

from langgraph.graph.state import CompiledStateGraph  
from psycopg_pool import AsyncConnectionPool  

from config.roles import ( : E402
    LLM_HTTP_TIMEOUT_S,
    RERANK_ENABLED,
    RERANK_MAX_CHARS,
    RERANK_MODEL,
    RERANK_TIMEOUT_S,
)
from config.settings import get_settings   
from crocol.application.agent.graph import build_graph  
from crocol.application.agent.state import AgentDeps  
from crocol.application.usecases.ask_questions import (  
    AskQuestion,
)
from crocol.application.tools.well_simulation import (  
    SimulationRunner,
)
from crocol.application.usecases.get_trace import GetTrace 
from crocol.infrastructure.llm.anthropic_client import AnthropicLLM 
from crocol.infrastructure.llm.gemini_client import GeminiLLM  
from crocol.infrastructure.llm.role_router import RoleRouter  
from crocol.infrastructure.repository.documents import (  
    PgDocumentStore,
)
from crocol.infrastructure.reranker import CohereReranker  
from crocol.infrastructure.repository.graphs import (  
    PgGraphStore,
)
from crocol.infrastructure.repository.pool import build_pool 
from crocol.infrastructure.repository.productions import (  
    PgProductionStore,
)
from crocol.infrastructure.repository.spatials import (  
    PgSpatialStore,
)
from crocol.infrastructure.repository.traces import (  
    PgTraceStore,
)
from crocol.infrastructure.simulation.adapter import (  
    NumericWellSimulator,
)
from crocol.infrastructure.vectors.chroma_store import (  
    ChromaVectorStore,
)
from crocol.infrastructure.vision.onnx_segmenter import (  
    OnnxCrackAnalyzer,
)


def build_llm() -> RoleRouter:
    """Role router over Claude and, when a key exists, Gemini."""
    settings = get_settings()
    if settings.anthropic_api_key is None:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in .env")

    anthropic = AnthropicLLM(
        settings.anthropic_api_key.get_secret_value(), LLM_HTTP_TIMEOUT_S)

    gemini = None
    if settings.google_api_key is not None:
        gemini = GeminiLLM(
            settings.google_api_key.get_secret_value(), LLM_HTTP_TIMEOUT_S)

    return RoleRouter(anthropic, gemini)


def build_reranker() -> CohereReranker | None:
    """Cohere rerank when enabled and keyed; None keeps the fused order."""
    key = get_settings().cohere_api_key
    if not RERANK_ENABLED or key is None:
        return None
    return CohereReranker(key.get_secret_value(),
                          RERANK_MODEL,
                          RERANK_TIMEOUT_S, 
                          RERANK_MAX_CHARS)


def build_deps(pool: AsyncConnectionPool | None = None) -> AgentDeps:

    documents = PgDocumentStore(pool) if pool is not None else None
    spatial = PgSpatialStore(pool) if pool is not None else None
    graph = PgGraphStore(pool) if pool is not None else None
    production = PgProductionStore(pool) if pool is not None else None
    
    return AgentDeps(llm=build_llm(), 
                     store=ChromaVectorStore(),
                     documents=documents, 
                     spatial=spatial, 
                     graph=graph,
                     vision=OnnxCrackAnalyzer(),
                     reranker=build_reranker(),
                     production=production,
                     simulation=SimulationRunner(NumericWellSimulator()))


def build_agent(pool: AsyncConnectionPool | None = None) -> CompiledStateGraph:

    return build_graph(build_deps(pool))


def build_ask(pool: AsyncConnectionPool | None,
              deps: AgentDeps | None = None
              ) -> AskQuestion:
    """The ask use case; the caller opens and closes the pool."""
    traces = PgTraceStore(pool) if pool is not None else None
    graph = build_graph(deps or build_deps(pool))
    
    return AskQuestion(graph, traces)


def build_get_trace(pool: AsyncConnectionPool | None) -> GetTrace:

    return GetTrace(PgTraceStore(pool) if pool is not None else None)
