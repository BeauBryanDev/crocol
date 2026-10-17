from dataclasses import replace
from typing import Protocol

from pydantic import BaseModel

from config.roles import FALLBACKS, MAX_OUTPUT_TOKENS, MODELS
from crocol.application.ports.llm import Images, LLMResult

TRIES_PER_MODEL = 2
JUDGE_ROLES = ("grade", "verify", "conflict")


class Provider(Protocol):
    async def complete(self,
                       model: str,
                       system: str,
                       user: str,
                       schema: type[BaseModel],
                       max_tokens: int,
                       images: Images = ()
                       ) -> LLMResult: ...


def is_gemini(model: str) -> bool:

    return model.startswith("gemini")


class RoleRouter:
    """The LLM port: maps a role to its model, retries once, falls back."""

    def __init__(self,
                 anthropic: Provider,
                 gemini: Provider | None = None
                 ) -> None:

        self._anthropic = anthropic
        self._gemini = gemini

    def provider(self, model: str) -> Provider | None:

        return self._gemini if is_gemini(model) else self._anthropic

    async def attempt(self,
                      model: str,
                      role: str,
                      system: str,
                      user: str,
                      schema: type[BaseModel],
                      images: Images = ()
                      ) -> LLMResult:

        provider = self.provider(model)
        if provider is None:
            return LLMResult(parsed=None, model=model, error="no_provider")

        result = LLMResult(parsed=None, model=model, error="not_called")
        for _ in range(TRIES_PER_MODEL):
            try:
                result = await provider.complete(
                    model, system, user, schema, MAX_OUTPUT_TOKENS[role],
                    images)
            except Exception as exc:
                result = LLMResult(parsed=None, model=model,
                                   error=type(exc).__name__)

            if result.ok or result.error == "refusal":
                return result

        return result

    async def generate(self,
                       role: str,
                       system: str,
                       user: str,
                       schema: type[BaseModel],
                       images: Images = ()
                       ) -> LLMResult:

        model = MODELS[role]
        result = await self.attempt(model, role, system, user, schema,
                                    images)
        judged_by_other_family = role in JUDGE_ROLES and is_gemini(model)
        if result.ok:
            return replace(result, cross_family=judged_by_other_family)

        fallback = FALLBACKS.get(role)
        if fallback is None or fallback == model:
            return replace(result, cross_family=judged_by_other_family)

        backup = await self.attempt(fallback, role, system, user, schema,
                                    images)
        return replace(backup, cross_family=False)
