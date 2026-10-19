from typing import Protocol

from crocol.domains.models.productions import ProductionResult


class ProductionSearch(Protocol):
    async def run(self, function: str,
                  arguments: dict) -> ProductionResult: ...
