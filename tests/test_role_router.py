from dataclasses import dataclass, field

import pytest
from pydantic import BaseModel

from config.roles import FALLBACKS, MODELS
from crocol.application.ports.llm import LLMResult
from crocol.infrastructure.llm.role_router import RoleRouter


class Out(BaseModel):
    value: str


@dataclass
class ScriptedProvider:
    outcomes: list[object]
    models: list[str] = field(default_factory=list)

    async def complete(self,
                       model: str,
                       system: str,
                       user: str,
                       schema: type[BaseModel],
                       max_tokens: int,
                       images: tuple = ()
                       ) -> LLMResult:

        self.models.append(model)
        outcome = self.outcomes.pop(0) if self.outcomes else None
        if isinstance(outcome, Exception):
            raise outcome
        return LLMResult(parsed=outcome, model=model, error="" if outcome
                         else "invalid")


@pytest.mark.anyio
async def test_claude_role_goes_to_anthropic() -> None:
    claude = ScriptedProvider([Out(value="ok")])
    gemini = ScriptedProvider([])
    result = await RoleRouter(claude, gemini).generate(
        "synthesize", "s", "u", Out)
    assert result.ok
    assert claude.models == [MODELS["synthesize"]]
    assert gemini.models == []


@pytest.mark.anyio
async def test_judge_on_gemini_is_cross_family() -> None:
    gemini = ScriptedProvider([Out(value="ok")])
    result = await RoleRouter(ScriptedProvider([]), gemini).generate(
        "grade", "s", "u", Out)
    assert result.ok
    assert result.cross_family is True


@pytest.mark.anyio
async def test_parse_failure_is_retried_once() -> None:
    claude = ScriptedProvider([None, Out(value="ok")])
    result = await RoleRouter(claude).generate("analyze", "s", "u", Out)
    assert result.ok
    assert len(claude.models) == 2


@pytest.mark.anyio
async def test_gemini_outage_falls_back_to_haiku() -> None:
    gemini = ScriptedProvider([RuntimeError("down"), RuntimeError("down")])
    claude = ScriptedProvider([Out(value="ok")])
    result = await RoleRouter(claude, gemini).generate(
        "verify", "s", "u", Out)
    assert result.ok
    assert result.cross_family is False
    assert claude.models == [FALLBACKS["verify"]]


@pytest.mark.anyio
async def test_missing_gemini_key_uses_fallback() -> None:
    claude = ScriptedProvider([Out(value="ok")])
    result = await RoleRouter(claude, None).generate("grade", "s", "u", Out)
    assert result.ok
    assert result.cross_family is False


@pytest.mark.anyio
async def test_total_failure_returns_result_not_exception() -> None:
    claude = ScriptedProvider([RuntimeError("x"), RuntimeError("x")])
    result = await RoleRouter(claude).generate("analyze", "s", "u", Out)
    assert result.ok is False
    assert result.error == "RuntimeError"
