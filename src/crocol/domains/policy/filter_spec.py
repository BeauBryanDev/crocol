import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from crocol.domains.policy.corpus_scope import CORPUS_SCOPES, CorpusScope

Equals = Mapping[str, str | int]


def doc_id_of(source_path: str) -> str:
    return hashlib.sha1(source_path.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class FilterSpec:
    collections: tuple[str, ...] = ()
    exclude_doc_ids: tuple[str, ...] = ()
    chunk_types: tuple[str, ...] = ()
    equals: Equals = field(default_factory=dict)


def build_filter_spec(
    scope: CorpusScope,
    chunk_types: Iterable[str],
    core_collections: Iterable[str],
    excluded_sources: Iterable[str] = (),
    equals: Equals | None = None,
) -> FilterSpec:
    if scope not in CORPUS_SCOPES:
        raise ValueError(f"unknown corpus scope: {scope}")

    collections: tuple[str, ...] = ()
    exclude_doc_ids: tuple[str, ...] = ()
    if scope == "core":
        collections = tuple(core_collections)
        exclude_doc_ids = tuple(doc_id_of(p) for p in excluded_sources)

    return FilterSpec(
        collections=collections,
        exclude_doc_ids=exclude_doc_ids,
        chunk_types=tuple(chunk_types),
        equals=dict(equals or {}),
    )
