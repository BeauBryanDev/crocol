from config.roles import RERANK_ENABLED
from crocol.application.agent.state import AgentDeps, AgentState


async def rerank(state: AgentState, deps: AgentDeps) -> tuple[dict, dict]:
    if not RERANK_ENABLED:
        return {}, {"status": "skipped", "reason": "RERANK_ENABLED=false"}
    return {}, {"status": "skipped", "reason": "no reranker configured"}
