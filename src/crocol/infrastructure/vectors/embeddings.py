import random
import time
from operator import attrgetter

import numpy as np
from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

from config.settings import (
    EMBED_BATCH,
    EMBED_DIMS,
    EMBED_MAX_CHARS,
    EMBED_MODEL,
    get_settings,
)

RETRYABLE = (
    RateLimitError,
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
)
ATTEMPTS = 8


def client() -> OpenAI:
    key = get_settings().openai_api_key.get_secret_value()
    
    return OpenAI(api_key=key,
                  max_retries=0,
                  timeout=60)


def embed_batch(openai_client: OpenAI,
                batch: list[str]
                ) -> list[list[float]]:
    
    for attempt in range(ATTEMPTS):
        try:
            response = openai_client.embeddings.create(
                model=EMBED_MODEL,
                input=batch,
                dimensions=EMBED_DIMS,
            )
            ordered = sorted(response.data, key=attrgetter("index"))
            return [item.embedding for item in ordered]
        
        except RETRYABLE:
            if attempt == ATTEMPTS - 1:
                raise
            time.sleep(min(60, 2 ** attempt + random.random()))
            
    return []


def embed_texts(
    texts: list[str],
    openai_client: OpenAI | None = None,
) -> np.ndarray:
    """L2-normalized embeddings, batched, with retries on transient errors."""
    openai_client = openai_client or client()
    vectors: list[list[float]] = []
    
    for start in range(0, len(texts), EMBED_BATCH):
        batch = [t[:EMBED_MAX_CHARS] for t in texts[start:start + EMBED_BATCH]]
        vectors.extend(embed_batch(openai_client, batch))

    matrix = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    
    return matrix / np.where(norms == 0, 1, norms)


def embed_query(text: str) -> np.ndarray:
    
    return embed_texts([text])[0]
