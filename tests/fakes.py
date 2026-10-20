from dataclasses import dataclass, field

from pydantic import BaseModel

from crocol.application.ports.llm import LLMResult
from crocol.domains.models.documents import Document
from crocol.domains.models.graphs import GraphResult

FAMILY = {
    "grade": False,
    "verify": False,
    "conflict": False,
}


@dataclass
class FakeLLM:
    script: dict[str, list[BaseModel | None]]
    calls: list[tuple[str, str]] = field(default_factory=list)
    images: list[int] = field(default_factory=list)

    async def generate(self, role: str, system: str, user: str,
                       schema: type[BaseModel],
                       images: tuple = ()) -> LLMResult:
        self.calls.append((role, user))
        self.images.append(len(images))
        queue = self.script.get(role) or [None]
        parsed = queue.pop(0) if len(queue) > 1 else queue[0]
        return LLMResult(
            parsed=parsed,
            model=f"fake-{role}",
            input_tokens=len(user) // 4,
            output_tokens=50,
            cross_family=FAMILY.get(role, True),
        )

    def roles(self) -> list[str]:
        return [role for role, _ in self.calls]


def row(chunk_id: str, doc_id: str, text: str, citation: str,
        page: int = 1, chunk_type: str = "text",
        doc_type: str = "thesis") -> dict:
    return {
        "id": chunk_id,
        "document": text,
        "score": 0.0,
        "metadata": {
            "doc_id": doc_id,
            "citation": citation,
            "title": f"Title {doc_id}",
            "source_path": f"{doc_id}.pdf",
            "collection": "VMM_Basin",
            "doc_type": doc_type,
            "chunk_type": chunk_type,
            "heading_path": "1. Section",
            "page_start": page,
            "page_end": page,
        },
    }


@dataclass
class FakeStore:
    rows: list[dict]
    queries: list[tuple[str, object]] = field(default_factory=list)

    def search(self, query: str, query_type: str = "conceptual",
               bm25_query: str | None = None, spec: object = None,
               limit: int = 10) -> list[dict]:
        self.queries.append((query, spec))
        return list(self.rows[:limit])


@dataclass
class FakeDocuments:
    documents: dict[str, Document]

    async def get_many(self, doc_ids: list[str]) -> dict[str, Document]:
        found = {}
        for doc_id in doc_ids:
            if doc_id in self.documents:
                found[doc_id] = self.documents[doc_id]
        return found


@dataclass
class FakeGraph:
    """Answers each allowlisted kg function from a script of rows."""
    script: dict[str, list[dict]]
    calls: list[tuple[str, dict]] = field(default_factory=list)
    fail: bool = False

    async def run(self, function: str, arguments: dict) -> GraphResult:
        self.calls.append((function, dict(arguments)))
        if self.fail:
            raise RuntimeError("graph down")
        rows = self.script.get(function, [])
        if function == "chunk_texts":
            wanted = set(arguments["chunk_ids"])
            rows = [r for r in rows if r["chunk_id"] in wanted]
        return GraphResult(function, tuple(rows), "Crocol-KG-2026")


def graph_rows() -> dict[str, list[dict]]:
    """A La Luna entity with members, documents and one linked chunk."""
    return {
        "resolve": [{"entity_id": 12, "kind": "formation", "name": "La Luna",
                     "score": 1.0, "mentions": 464,
                     "props": {"age": "Turoniano–Santoniano"}}],
        "facts": [
            {"direction": "in", "rel": "PART_OF", "other_kind": "member",
             "total": 3, "names": ["Galembo", "Pujamana", "Salada"]},
            {"direction": "out", "rel": "OVERLIES", "other_kind": "formation",
             "total": 1, "names": ["Simití"]},
            {"direction": "out", "rel": "CO_MENTIONED", "other_kind": "field",
             "total": 24, "names": ["LA CIRA INFANTAS"]},
        ],
        "entity_documents": [{"doc_id": "d2", "citation": "Rueda Acevedo, 2016",
                              "title": "T", "collection": "VMM_Basin",
                              "scope": "core", "chunks": 11,
                              "described": True}],
        "evidence_chunks": [{"chunk_id": "g1", "entities_hit": 1,
                             "score": 5.0}],
        "chunk_texts": [{"chunk_id": "g1", "doc_id": "d3",
                         "text": "La Formación La Luna es la roca generadora.",
                         "chunk_type": "text", "heading_path": "2. Geología",
                         "page_start": 9, "page_end": 9,
                         "citation": "Autor, 2019", "title": "Title d3",
                         "source_path": "d3.pdf", "collection": "VMM_Basin",
                         "doc_type": "thesis"}],
        "path": [],
    }
