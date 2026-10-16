from functools import lru_cache

from chromadb.base_types import SparseVector
from chromadb.utils.embedding_functions import ChromaBm25EmbeddingFunction

from crocol.domains.services.lexical import STOPWORDS, normalize_lexical


@lru_cache
def bm25_encoder() -> ChromaBm25EmbeddingFunction:
    return ChromaBm25EmbeddingFunction(stopwords=STOPWORDS)


def encode_query(text: str) -> SparseVector:
    """Tokenized exactly like the indexed lexical_text."""
    return bm25_encoder().embed_query([normalize_lexical(text)])[0]
