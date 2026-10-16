from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    citation: str
    title: str = ""
    source_path: str = ""
    collection: str = ""
    doc_type: str = ""
    chunk_type: str = "text"
    heading_path: str = ""
    page_start: int = 0
    page_end: int = 0
    score: float = 0.0
    label: str = ""
