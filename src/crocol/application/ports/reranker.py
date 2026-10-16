from typing import Protocol

from crocol.domains.models.chunks import Chunk


class Reranker(Protocol):
    async def rerank(self, query: str,
                     chunks: list[Chunk]) -> list[Chunk]: ...
