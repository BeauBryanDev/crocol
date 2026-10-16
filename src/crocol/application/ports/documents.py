from typing import Protocol

from crocol.domains.models.documents import Document


class DocumentStore(Protocol):
    async def get_many(self, doc_ids: list[str]) -> dict[str, Document]: ...
