import logging
import time
from dataclasses import replace

import httpx

from config.logging import elapsed_ms
from crocol.domains.models.chunks import Chunk

LOGGER = logging.getLogger("crocol.rerank")
COHERE_RERANK_URL = "https://api.cohere.com/v2/rerank"


def document_of(chunk: Chunk, max_chars: int) -> str:
    """The passage as the reranker sees it: heading context, then text."""
    head = f"{chunk.heading_path}\n" if chunk.heading_path else ""
    
    return f"{head}{chunk.text}"[:max_chars]


class CohereReranker:
    """Cohere Rerank over HTTP;
    returns the chunks best first, with scores."""

    def __init__(self, 
                 api_key: str,
                 model: str, 
                 timeout_s: float,
                 max_chars: int) -> None:

        self._headers = {"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"}
        self._model = model
        self._timeout = httpx.Timeout(timeout_s)
        self._max_chars = max_chars

    async def rerank(self, query: str,
                     chunks: list[Chunk]
                     ) -> list[Chunk]:

        if not chunks:
            return []
        
        body = {
            "model": self._model,
            "query": query,
            "documents": [document_of(c, self._max_chars) for c in chunks],
            "top_n": len(chunks),
        }
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(COHERE_RERANK_URL,
                                         json=body,
                                         headers=self._headers)
            LOGGER.info("rerank model=%s docs=%d http=%d ms=%d",
                        self._model, len(chunks), response.status_code,
                        elapsed_ms(started))
            response.raise_for_status()

        ranked = []
        
        for item in response.json()["results"]:
            chunk = chunks[item["index"]]
            ranked.append(replace(chunk, score=float(item["relevance_score"])))
            
        return ranked
