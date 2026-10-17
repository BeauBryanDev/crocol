from crocol.application.agent.schemas import Verification, render_evidence
from crocol.application.agent.state import AgentDeps, AgentState, ask
from crocol.domains.models.claims import Claim
from crocol.domains.services.citations import normalize_labels
from crocol.domains.services.verification import (
    unknown_labels,
    unsupported_numbers,
)


def verification_request(state: AgentState, text: str) -> str:
    return (
        f"QUESTION:\n{state['question']}\n\n"
        f"ANSWER TO CHECK:\n{text}\n\n"
        f"EVIDENCE:\n{render_evidence(state.get('evidence') or [])}"
    )


def deterministic_claims(text: str, state: AgentState) -> list[Claim]:
    evidence = state.get("evidence") or []
    claims = []
    for label in unknown_labels(text, [c.label for c in evidence]):
        claims.append(Claim(f"cites unknown source [{label}]", (label,),
                            "unsupported", numeric=True))
    for token in unsupported_numbers(text, [c.text for c in evidence]):
        claims.append(Claim(token, (), "unsupported", numeric=True))
    return claims


def judged_claims(parsed: Verification | None) -> list[Claim]:
    if parsed is None:
        return [Claim("verifier unavailable", (), "unsupported", numeric=True)]
    claims = []
    for item in parsed.claims:
        labels = tuple(normalize_labels(item.labels))
        claims.append(Claim(item.claim, labels, item.verdict,
                            numeric=item.numeric))
    return claims


async def verify(state: AgentState, deps: AgentDeps) -> tuple[dict, dict]:
    """Deterministic checks first, then the cross-family claim judge."""
    draft = state.get("draft")
    if not draft or draft.get("insufficient"):
        update = {"verified": False, "claims": []}
        return update, {"skipped": True}

    text = draft["text"]
    hard = deterministic_claims(text, state)
    parsed, usage = await ask(
        deps, "verify", "checker", verification_request(state, text),
        Verification)
    judged = judged_claims(parsed if isinstance(parsed, Verification)
                           else None)
    claims = hard + judged
    failing = [c for c in claims if c.failing]

    update = {
        "claims": claims,
        "verified": not failing,
        "llm_calls": 1,
        "llm_usage": [usage],
    }
    summary = {
        "claims": len(judged),
        "supported": sum(1 for c in judged if c.verdict == "supported"),
        "failing": len(failing),
        "unsupported_numbers": sum(1 for c in hard if not c.labels),
        "cross_family": usage["cross_family"],
    }
    return update, summary
