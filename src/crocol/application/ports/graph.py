from typing import Protocol

from crocol.domains.models.graphs import GraphResult


class GraphSearch(Protocol):
    async def run(self, function: str,
                  arguments: dict) -> GraphResult: ...
