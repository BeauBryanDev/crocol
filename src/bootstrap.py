import os

os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

from langgraph.graph.state import CompiledStateGraph  # noqa: E402

from config.roles import NODE_TIMEOUT_S  # noqa: E402
from config.settings import get_settings  # noqa: E402
from crocol.application.agent.graph import build_graph  # noqa: E402
from crocol.application.agent.state import AgentDeps  # noqa: E402
from crocol.infrastructure.llm.anthropic_client import AnthropicLLM  # noqa
from crocol.infrastructure.llm.gemini_client import GeminiLLM  # noqa: E402
from crocol.infrastructure.llm.role_router import RoleRouter  # noqa: E402
from crocol.infrastructure.vectors.chroma_store import (  # noqa: E402
    ChromaVectorStore,
)


def build_llm() -> RoleRouter:
    """Role router over Claude and, when a key exists, Gemini."""
    settings = get_settings()
    if settings.anthropic_api_key is None:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in .env")

    anthropic = AnthropicLLM(
        settings.anthropic_api_key.get_secret_value(), NODE_TIMEOUT_S)

    gemini = None
    if settings.google_api_key is not None:
        gemini = GeminiLLM(
            settings.google_api_key.get_secret_value(), NODE_TIMEOUT_S)

    return RoleRouter(anthropic, gemini)


def build_deps() -> AgentDeps:

    return AgentDeps(llm=build_llm(), store=ChromaVectorStore())


def build_agent() -> CompiledStateGraph:

    return build_graph(build_deps())
