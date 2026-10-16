from anthropic import AsyncAnthropic
from pydantic import BaseModel

from crocol.application.ports.llm import LLMResult

FAILED_STOPS = ("max_tokens", "refusal", "model_context_window_exceeded")


class AnthropicLLM:
    def __init__(self,
                 api_key: str,
                 timeout_s: float
                 ) -> None:

        self._client = AsyncAnthropic(
            api_key=api_key,
            max_retries=1,
            timeout=timeout_s,
        )

    async def complete(self,
                       model: str,
                       system: str,
                       user: str,
                       schema: type[BaseModel],
                       max_tokens: int
                       ) -> LLMResult:
        """One structured call; a truncated or refused output parses to None."""
        response = await self._client.messages.parse(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=schema,
        )

        parsed = response.parsed_output
        error = ""
        if response.stop_reason in FAILED_STOPS:
            parsed = None
            error = str(response.stop_reason)

        return LLMResult(
            parsed=parsed,
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            error=error,
        )
