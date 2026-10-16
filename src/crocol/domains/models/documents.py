from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    doc_id: str
    citation: str
    reference: str
    title: str = ""
    doc_type: str = ""
    scope: str = "core"
    year: int | None = None
