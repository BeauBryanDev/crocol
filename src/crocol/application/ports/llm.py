from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel

Schema = TypeVar("Schema", bound=BaseModel)
Images = tuple[tuple[bytes, str], ...]


@dataclass(frozen=True)
class LLMResult:
    parsed: BaseModel | None
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cross_family: bool = True
    error: str = ""
    latency_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.parsed is not None


class LLM(Protocol):
    async def generate(
        self,
        role: str,
        system: str,
        user: str,
        schema: type[Schema],
        images: Images = (),
    ) -> LLMResult: ...
