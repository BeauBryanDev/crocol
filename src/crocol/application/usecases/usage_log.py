import logging
from collections import defaultdict

LOGGER = logging.getLogger("crocol.usage")


def empty_totals() -> dict:

    return {
        "model": "",
        "calls": 0,
        "in": 0,
        "out": 0,
        "ms": 0,
    }


def by_role(usages: list[dict]) -> dict[str, dict]:
    """Calls, tokens and model time summed per role, in call order."""
    totals: dict[str, dict] = defaultdict(empty_totals)
    for usage in usages:
        role = totals[usage["role"]]
        role["model"] = usage["model"]
        role["calls"] += 1
        role["in"] += usage["input_tokens"]
        role["out"] += usage["output_tokens"]
        role["ms"] += usage.get("latency_ms", 0)
    return dict(totals)


def log_question(state: dict, status: str, latency_ms: int) -> None:
    """Per-question token and time spend; metrics only, no user text."""
    usages = state.get("llm_usage") or []
    roles = by_role(usages)
    tokens_in = sum(role["in"] for role in roles.values())
    tokens_out = sum(role["out"] for role in roles.values())
    llm_ms = sum(role["ms"] for role in roles.values())

    LOGGER.info("question mode=%s status=%s llm_calls=%d in=%d out=%d "
                "llm_ms=%d total_ms=%d", state.get("mode", "quick"), status,
                len(usages), tokens_in, tokens_out, llm_ms, latency_ms)

    for name, role in roles.items():
        LOGGER.info("question role=%s model=%s calls=%d in=%d out=%d ms=%d",
                    name, role["model"], role["calls"], role["in"],
                    role["out"], role["ms"])
