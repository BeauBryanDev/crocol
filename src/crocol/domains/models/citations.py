from dataclasses import dataclass


@dataclass(frozen=True)
class Citation:
    label: str
    chunk_id: str
    doc_id: str
    rendered: str
