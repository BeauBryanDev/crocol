from typing import Protocol


class GraphSearch(Protocol):
    async def evidence_chunks(
        self,
        entity_ids: list[int],
        limit: int,
    ) -> list[str]: ...
