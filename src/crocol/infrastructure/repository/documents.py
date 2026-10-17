from psycopg_pool import AsyncConnectionPool

from crocol.domains.models.documents import Document

SELECT_DOCUMENTS = """
SELECT doc_id, citation, reference, title, doc_type, scope, year
FROM rag.documents
WHERE doc_id = ANY(%s)
"""


class PgDocumentStore:
    def __init__(self, pool: AsyncConnectionPool) -> None:

        self._pool = pool

    async def get_many(self, doc_ids: list[str]) -> dict[str, Document]:

        if not doc_ids:
            return {}

        async with self._pool.connection() as conn:
            cursor = await conn.execute(SELECT_DOCUMENTS, (list(doc_ids),))
            rows = await cursor.fetchall()

        documents = {}
        for doc_id, citation, reference, title, doc_type, scope, year in rows:
            documents[doc_id] = Document(
                doc_id=doc_id,
                citation=citation,
                reference=reference,
                title=title,
                doc_type=doc_type,
                scope=scope,
                year=year,
            )

        return documents
