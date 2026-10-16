from typing import Protocol

from crocol.domains.models.spatials import SpatialResult


class SpatialSearch(Protocol):
    async def run(self, function: str,
                  arguments: dict) -> SpatialResult: ...
