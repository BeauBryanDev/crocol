import asyncio
import time
from collections.abc import Awaitable, Callable

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from config.roles import NODE_TIMEOUT_S, NODE_TIMEOUTS, OPTIONAL_NODES
from crocol.application.agent import routing
from crocol.application.agent.nodes.analyze import analyze
from crocol.application.agent.nodes.evaluate import conflict_check
from crocol.application.agent.nodes.fuse import fuse
from crocol.application.agent.nodes.grade import grade
from crocol.application.agent.nodes.rerank import rerank
from crocol.application.agent.nodes.response import abstain, finalize
from crocol.application.agent.nodes.retrieve import (
    retrieve_graph,
    retrieve_production,
    retrieve_spatial,
    retrieve_text,
)
from crocol.application.agent.nodes.rewrite import rewrite
from crocol.application.agent.nodes.synthesize import revise, synthesize
from crocol.application.agent.nodes.verify import verify
from crocol.application.agent.nodes.vision import retrieve_vision
from crocol.application.agent.research import investigate, merge, plan
from crocol.application.agent.state import AgentDeps, AgentState
from crocol.domains.models.traces import TraceEvent

# State, Deps -> Update, Summary
NodeFn = Callable[[AgentState, AgentDeps], Awaitable[tuple[dict, dict]]]
Runner = Callable[[AgentState], Awaitable[dict]]

NODES: dict[str, NodeFn] = {
    "analyze": analyze,
    "retrieve_text": retrieve_text,
    "retrieve_spatial": retrieve_spatial,
    "retrieve_graph": retrieve_graph,
    "retrieve_production": retrieve_production,
    "retrieve_vision": retrieve_vision,
    "fuse": fuse,
    "rerank": rerank,
    "grade": grade,
    "rewrite": rewrite,
    "synthesize": synthesize,
    "verify": verify,
    "revise": revise,
    "abstain": abstain,
    "finalize": finalize,
    "plan": plan,
    "investigate": investigate,
    "merge": merge,
    "conflict_check": conflict_check,
}


def elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def failed(name: str, reason: str) -> tuple[dict, dict, str]:
    """A crashed or timed-out node; optional ones never make it partial."""
    update: dict = {"errors": [f"{name}: {reason}"]}
    if name not in OPTIONAL_NODES:
        update["partial"] = True
    status = "timeout" if reason == "timeout" else "error"
    return update, {}, status


def bind(name: str, node: NodeFn, deps: AgentDeps) -> Runner:
    """Wrap a node with timing, a timeout and a trace event."""

    async def run(state: AgentState) -> dict:
        
        started = time.perf_counter()
        try:
            update, summary = await asyncio.wait_for(
                node(state, deps),
                timeout=NODE_TIMEOUTS.get(name, NODE_TIMEOUT_S))
            status = summary.pop("status", "ok")
            
        except TimeoutError:
            update, summary, status = failed(name, "timeout")
        except Exception as exc:
            update, summary, status = failed(name, type(exc).__name__)

        event = TraceEvent(name, status,
                           elapsed_ms(started),
                           summary)
        
        return {**update, "trace": [event]}

    return run


def build_graph(deps: AgentDeps) -> CompiledStateGraph:
    """Quick loop plus the research fan-out (plan, investigate, merge)."""
    graph = StateGraph(AgentState)
    
    for name, node in NODES.items():
        graph.add_node(name, bind(name, node, deps))

    retrievers = list(routing.RETRIEVERS)
    graph.add_edge(START, "analyze")
    graph.add_conditional_edges("analyze",
                                routing.after_analyze,
                                [*retrievers, "plan"])
    graph.add_conditional_edges("plan", routing.after_plan, ["investigate"])
    graph.add_edge("investigate", "merge")
    graph.add_conditional_edges(
        "merge",
        routing.after_merge,
        ["conflict_check", "synthesize", "abstain", "finalize"],
    )
    graph.add_edge("conflict_check", "synthesize")
    graph.add_edge(retrievers, "fuse")
    graph.add_edge("fuse", "rerank")
    graph.add_edge("rerank", "grade")
    graph.add_conditional_edges(
        "grade",
        routing.after_grade,
        ["synthesize", "rewrite", "abstain", "finalize"],
    )
    graph.add_conditional_edges(
        "rewrite", routing.after_rewrite,
        [*retrievers, "synthesize", "abstain"]
        )
    graph.add_edge("synthesize", "verify")
    graph.add_conditional_edges(
        "verify",
        routing.after_verify,
        ["finalize", "revise", "abstain"],
    )
    graph.add_edge("revise", "verify")
    graph.add_edge("abstain", "finalize")
    graph.add_edge("finalize", END)
    
    return graph.compile()
