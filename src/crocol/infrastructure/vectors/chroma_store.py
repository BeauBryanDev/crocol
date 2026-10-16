from functools import lru_cache
from typing import Any

import chromadb
from chromadb import K, Knn, Rrf, Search

from config.settings import (
    BM25_KEY,
    BM25_WEIGHTS,
    CANDIDATES,
    RRF_K,
    get_settings,
)
from crocol.domains.policy.filter_spec import FilterSpec
from crocol.infrastructure.vectors.bm25 import encode_query
from crocol.infrastructure.vectors.chroma_filters import to_where
from crocol.infrastructure.vectors.embeddings import embed_query

RESULT_FIELDS = [
    "doc_id",
    "source_path",
    "citation",
    "title",
    "collection",
    "doc_type",
    "chunk_type",
    "heading_path",
    "page_start",
    "page_end",
    "table_id",
    "article",
    "clause",
    "area",
]


def chroma_client() -> Any:
    settings = get_settings()
    return chromadb.CloudClient(
        tenant=settings.chroma_tenant,
        database=settings.chroma_database,
        api_key=settings.chroma_api_key.get_secret_value(),
        cloud_host=settings.chroma_host,
    )


@lru_cache(maxsize=256)
def dense_query(query: str) -> tuple[float, ...]:
    return tuple(embed_query(query).tolist())


def hybrid_rank(query: str, 
                query_type: str, 
                bm25_query: str | None
                ) -> Rrf:
    """Dense + BM25 fused server-side; bm25_query in corpus language."""
    dense = Knn(
        query=list(dense_query(query)),
        return_rank=True,
        limit=CANDIDATES,
    )
    sparse = Knn(
        query=encode_query(bm25_query or query),
        key=BM25_KEY,
        return_rank=True,
        limit=CANDIDATES,
    )
    return Rrf(
        ranks=[dense, sparse],
        weights=[1.0, BM25_WEIGHTS[query_type]],
        k=RRF_K,
    )


class ChromaVectorStore:
    def __init__(self, collection: Any = None) -> None:
        self._collection = collection

    @property
    def collection(self) -> Any:
        
        if self._collection is None:
            name = get_settings().collection_name
            self._collection = chroma_client().get_collection(name)
            
        return self._collection


    def search(
        self,
        query: str,
        query_type: str = "conceptual",
        bm25_query: str | None = None,
        spec: FilterSpec | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Dense + BM25 fused server-side; bm25_query in corpus language."""
        search = (
            Search()
            .rank(hybrid_rank(query, query_type, bm25_query))
            .limit(limit)
            .select(K.DOCUMENT, K.SCORE, *RESULT_FIELDS)
        )
        where = to_where(spec)
        if where is not None:
            search = search.where(where)
            
        return self.collection.search(search).rows()[0]
