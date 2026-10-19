import asyncio

from config.settings import KG_LABEL
from crocol.application.ports.graph import GraphSearch

MIN_SCORE = 0.5
CANDIDATES = 5
RELATION_ROWS = 30
DOCUMENT_ROWS = 10


class GetEntity:
    """Entity card: best match, its relations and the documents about it."""

    def __init__(self, graph: GraphSearch | None) -> None:

        self._graph = graph

    async def run(self, name: str, kind: str | None = None) -> dict | None:

        if self._graph is None:
            return None
        found = await self._graph.run("resolve", {
            "name": name, "kinds": [kind] if kind else None,
            "max_rows": CANDIDATES})
        matches = [r for r in found.rows if r["score"] >= MIN_SCORE]
        if not matches:
            return None

        best = matches[0]
        facts, documents = await asyncio.gather(
            self._graph.run("facts", {"entity_id": best["entity_id"],
                                      "max_rows": RELATION_ROWS}),
            self._graph.run("entity_documents", {
                "entity_id": best["entity_id"], "max_rows": DOCUMENT_ROWS}))
        props = dict(best["props"] or {})
        props.pop("strict", None)
        return {
            "entity": {"kind": best["kind"], "name": best["name"],
                       "score": round(float(best["score"]), 3),
                       "mentions": int(best["mentions"]), "props": props},
            "candidates": [{"kind": r["kind"], "name": r["name"],
                            "score": round(float(r["score"]), 3)}
                           for r in matches[1:]],
            "relations": [{"direction": r["direction"], "rel": r["rel"],
                           "kind": r["other_kind"], "total": int(r["total"]),
                           "names": list(r["names"])} for r in facts.rows],
            "documents": [{"doc_id": d["doc_id"], "citation": d["citation"],
                           "title": d["title"],
                           "collection": d["collection"],
                           "scope": d["scope"], "chunks": int(d["chunks"]),
                           "described": bool(d["described"])}
                          for d in documents.rows],
            "source": KG_LABEL,
        }
