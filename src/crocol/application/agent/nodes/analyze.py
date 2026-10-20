import re

from config.roles import MAX_VARIANTS, RESEARCH_MODE_ENABLED
from config.settings import KG_MAX_ENTITIES, QUESTION_MAX_CHARS
from crocol.application.agent.context import analysis_request
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


def resolved_question(state: AgentState, analysis: Analysis) -> str:
    """The follow-up rewritten as a full question, when there is memory."""
    question = state["question"]
    standalone = " ".join((analysis.standalone_question or "").split())
    if not state.get("history") or not analysis.follows_up:
        return question
    if not standalone or len(standalone) > QUESTION_MAX_CHARS:
        return question

    return standalone


def unique_variants(question: str,
                    extra: list[str]
                    ) -> list[str]:
    
    variants: list[str] = []
    seen: set[str] = set()
    
    for text in [question, *extra]:
        
        key = text.strip().casefold()
        if key and key not in seen:
            seen.add(key)
            variants.append(text.strip())
            
    return variants[:MAX_VARIANTS]


async def analyze(state: AgentState, 
                  deps: AgentDeps) -> tuple[dict, dict]:
    
    parsed, usage = await ask(deps,
                              "analyze",
                              "analyst",
                              analysis_request(state), Analysis)
    analysis = parsed if isinstance(parsed, Analysis) else None
    fallback = analysis is None

    if analysis is None:
        analysis = fallback_analysis(state["question"])

    question = resolved_question(state, analysis)
    follows_up = question != state["question"]

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
        "question": question,
        "follows_up": follows_up,
        "prior_coverage": analysis.prior_coverage if follows_up else "",
        "language": analysis.language,
        "mode": mode,
        "intents": analysis.intents,
        "corpus_scope": analysis.corpus_scope,
        "chunk_policy": analysis.chunk_policy,
        "query_type": analysis.query_type,
        "query_variants": variants,
        "bm25_query": analysis.bm25_query,
        "places": [place.model_dump() for place in analysis.places[:3]],
        "entities": [e.model_dump()
                     for e in analysis.entities[:KG_MAX_ENTITIES]],
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
        "entities": len(analysis.entities),
        "fallback": fallback,
        "history": len(state.get("history") or []),
        "follows_up": follows_up,
    }
    
    return update, summary
