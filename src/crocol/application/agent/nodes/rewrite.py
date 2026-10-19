from crocol.application.agent.nodes.analyze import unique_variants
from crocol.application.agent.schemas import RewritePlan
from crocol.application.agent.state import (
    AgentDeps,
    AgentState,
    ask,
    strategy_of,
)


def rewrite_request(state: AgentState) -> str:
    
    grade = state.get("grade") or {}
    
    return (
        f"QUESTION:\n{state['question']}\n\n"
        f"PREVIOUS STRATEGY:\n"
        f"variants={state.get('query_variants')}\n"
        f"corpus_scope={state.get('corpus_scope')}\n"
        f"chunk_policy={state.get('chunk_policy')}\n"
        f"query_type={state.get('query_type')}\n\n"
        f"WHAT THE GRADER FOUND MISSING:\n{grade.get('missing', '')}\n"
    )


def widened(state: AgentState) -> RewritePlan:
    """Deterministic fallback: widen the scope, then switch the query type."""
    scope = state.get("corpus_scope", "core")
    query_type = state.get("query_type", "conceptual")
    
    if scope == "core":
        scope = "all"
        
    elif query_type != "exact":
        query_type = "exact"
        
    else:
        query_type = "conceptual"
        
    return RewritePlan(
        variants=list(state.get("query_variants") or []),
        corpus_scope=scope,
        chunk_policy=state.get("chunk_policy", "prose_tables"),
        query_type=query_type,
        bm25_query=state.get("bm25_query"),
        reason="fallback widening",
    )


async def rewrite(state: AgentState, deps: AgentDeps) -> tuple[dict, dict]:
    
    parsed, usage = await ask(
        deps, 
        "rewrite",
        "rewriter",
        rewrite_request(state),
        RewritePlan)
    
    plan = parsed if isinstance(parsed, RewritePlan) else widened(state)

    variants = unique_variants(state["question"], plan.variants)
    
    strategy = strategy_of(
        variants,
        plan.corpus_scope, 
        plan.chunk_policy,
        plan.query_type)
    
    previous = state.get("strategies") or []
    repeated = strategy in previous

    update = {
        "attempts": state.get("attempts", 0) + 1,
        "query_variants": variants,
        "corpus_scope": plan.corpus_scope,
        "chunk_policy": plan.chunk_policy,
        "query_type": plan.query_type,
        "bm25_query": plan.bm25_query,
        "strategies": [*previous, strategy],
        "repeated": repeated,
        "llm_calls": 1,
        "llm_usage": [usage],
    }
    summary = {
        "attempt": update["attempts"],
        "corpus_scope": plan.corpus_scope,
        "chunk_policy": plan.chunk_policy,
        "query_type": plan.query_type,
        "variants": len(variants),
        "repeated": repeated,
        "fallback": parsed is None,
    }
    
    return update, summary
