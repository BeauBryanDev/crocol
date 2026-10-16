from typing import Protocol

from crocol.domains.policy.filter_spec import FilterSpec


class VectorSearch(Protocol):
    def search(
        self,
        query: str,
        query_type: str = "conceptual",
        bm25_query: str | None = None,
        spec: FilterSpec | None = None,
        limit: int = 10,
    ) -> list[dict]: ...
