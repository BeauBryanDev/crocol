import re

from config.roles import MAX_VARIANTS, RESEARCH_MODE_ENABLED
from crocol.application.agent.schemas import Analysis
from crocol.application.agent.state import (
    AgentDeps,
    AgentState,
    ask,
    strategy_of,
)

SPANISH_HINT_RE = re.compile(
    r"[¿¡áéíóúñ]|\b(qué|cuál|cómo|dónde|los|las|del|para|formación)\b",
    re.I,
)


def guess_language(question: str) -> str:
    return "es" if SPANISH_HINT_RE.search(question) else "en"


def fallback_analysis(question: str) -> Analysis:
    language = guess_language(question)
    return Analysis(
        language=language,
        mode="quick",
        intents=["other"],
        corpus_scope="core",
        chunk_policy="prose_tables",
        query_type="conceptual" if language == "es" else "cross_language",
        variants=[],
        bm25_query=None,
    )


def unique_variants(question: str, extra: list[str]) -> list[str]:
    variants: list[str] = []
    seen: set[str] = set()
    for text in [question, *extra]:
        key = text.strip().casefold()
        if key and key not in seen:
            seen.add(key)
            variants.append(text.strip())
    return variants[:MAX_VARIANTS]


async def analyze(state: AgentState, deps: AgentDeps) -> tuple[dict, dict]:
    question = state["question"]
    parsed, usage = await ask(deps, "analyze", "analyst", question, Analysis)
    analysis = parsed if isinstance(parsed, Analysis) else None
    fallback = analysis is None
    if analysis is None:
        analysis = fallback_analysis(question)

    requested_mode = analysis.mode
    mode = requested_mode if RESEARCH_MODE_ENABLED else "quick"
    if state.get("image"):
        mode = "quick"
    variants = unique_variants(question, analysis.variants)
    strategy = strategy_of(
        variants,
        analysis.corpus_scope,
        analysis.chunk_policy,
        analysis.query_type,
    )
    update = {
        "language": analysis.language,
        "mode": mode,
        "intents": analysis.intents,
        "corpus_scope": analysis.corpus_scope,
        "chunk_policy": analysis.chunk_policy,
        "query_type": analysis.query_type,
        "query_variants": variants,
        "bm25_query": analysis.bm25_query,
        "places": [place.model_dump() for place in analysis.places[:3]],
        "strategies": [strategy],
        "llm_calls": 1,
        "llm_usage": [usage],
    }
    summary = {
        "mode": mode,
        "requested_mode": requested_mode,
        "intents": analysis.intents,
        "corpus_scope": analysis.corpus_scope,
        "chunk_policy": analysis.chunk_policy,
        "query_type": analysis.query_type,
        "variants": len(variants),
        "places": len(analysis.places),
        "fallback": fallback,
    }
    return update, summary
