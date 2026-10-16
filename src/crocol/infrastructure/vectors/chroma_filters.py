from typing import Any

from chromadb import K

from crocol.domains.policy.filter_spec import FilterSpec


def clauses_of(spec: FilterSpec) -> list[Any]:
    clauses = []
    if spec.collections:
        clauses.append(K("collection").is_in(list(spec.collections)))
        
    if spec.exclude_doc_ids:
        clauses.append(K("doc_id").not_in(list(spec.exclude_doc_ids)))
        
    if spec.chunk_types:
        clauses.append(K("chunk_type").is_in(list(spec.chunk_types)))
        
    for key, value in spec.equals.items():
        clauses.append(K(key) == value)
        
    return clauses


def to_where(spec: FilterSpec | None) -> Any:
    """Chroma where-expression for a FilterSpec, or None when unfiltered."""
    if spec is None:
        return None

    where = None
    for clause in clauses_of(spec):
        where = clause if where is None else where & clause
    return where
