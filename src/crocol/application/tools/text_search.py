from config.settings import (
    CHUNK_POLICY_TYPES,
    CORE_COLLECTIONS,
    ROW_CARD_WEIGHT,
    default_excluded_sources,
)
from crocol.application.ports.vector_search import VectorSearch
from crocol.domains.policy.chunk_policy import ChunkPolicy, ChunkTypes
from crocol.domains.policy.corpus_scope import CorpusScope
from crocol.domains.policy.filter_spec import (
    Equals,
    FilterSpec,
    build_filter_spec,
)
from crocol.domains.services.fusion import rrf_merge


def spec_for(
    corpus_scope: CorpusScope,
    chunk_types: ChunkTypes,
    equals: Equals | None = None,
) -> FilterSpec:
    "" "Build a FilterSpec for a corpus scope and chunk types."""
    return build_filter_spec(
        corpus_scope,
        CHUNK_POLICY_TYPES[chunk_types],
        CORE_COLLECTIONS,
        default_excluded_sources(),
        equals,
    )


def text_search(
    store: VectorSearch,
    query: str,
    query_type: str = "conceptual",
    bm25_query: str | None = None,
    corpus_scope: CorpusScope = "core",
    chunk_policy: ChunkPolicy = "prose_tables",
    equals: Equals | None = None,
    limit: int = 10,
) -> list[dict]:
    """Prose and tables by default; numeric adds fused table-row cards."""
    prose_spec = spec_for(corpus_scope, "prose_tables", equals)
    prose = store.search(query, query_type,
                         bm25_query, prose_spec, limit)
    
    if chunk_policy == "prose_tables":
        return prose
    
    if chunk_policy != "numeric":
        raise ValueError(f"unknown chunk_policy: {chunk_policy}")

    rows_spec = spec_for(corpus_scope, "rows", equals)
    rows = store.search(query,
                        query_type,
                        bm25_query, 
                        rows_spec,
                        limit)
    
    return rrf_merge([prose, rows],
                     [1.0, ROW_CARD_WEIGHT],
                     limit=limit)
