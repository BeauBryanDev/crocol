from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from crocol.application.ports.llm import Images, LLMResult

THINKING_HEADROOM = 2048


class GeminiLLM:
    def __init__(self,
                 api_key: str,
                 timeout_s: float
                 ) -> None:

        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout_s * 1000)),
        )

    def config(self,
               system: str,
               schema: type[BaseModel],
               max_tokens: int
               ) -> types.GenerateContentConfig:

        return types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_json_schema=schema.model_json_schema(),
            max_output_tokens=max_tokens + THINKING_HEADROOM,
            thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.LOW),
        )

    async def complete(self,
                       model: str,
                       system: str,
                       user: str,
                       schema: type[BaseModel],
                       max_tokens: int,
                       images: Images = ()
                       ) -> LLMResult:
        """One JSON-schema call, validated locally with the same schema."""
        contents: list = []
        for data, mime in images:
            contents.append(types.Part.from_bytes(data=data, mime_type=mime))
        contents.append(user)
        response = await self._client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=self.config(system, schema, max_tokens),
        )

        parsed, error = None, ""
        try:
            parsed = schema.model_validate_json(response.text or "")
        except ValidationError:
            error = "invalid_json"

        usage = response.usage_metadata
        prompt_tokens = (usage.prompt_token_count or 0) if usage else 0
        answer_tokens = (usage.candidates_token_count or 0) if usage else 0
        thought_tokens = (usage.thoughts_token_count or 0) if usage else 0

        return LLMResult(
            parsed=parsed,
            model=model,
            input_tokens=prompt_tokens,
            output_tokens=answer_tokens + thought_tokens,
            error=error,
        )
