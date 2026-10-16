import csv
import hashlib
import json
from collections import Counter
from datetime import date
from typing import Any

from psycopg.types.json import Jsonb

from chunking import PIPELINE_VERSION, load_metadata, short_citation
from config.settings import ROOT
from embeddings import content_hash

METADATA = ROOT / "corpus_metadata.yaml"
MANIFEST = ROOT / "markdown" / "manifest.csv"
CHUNKS = ROOT / "chunks" / "chunks.jsonl"
EMBED_INDEX = ROOT / "chunks" / "embeddings_index.json"
REFERENCES = ROOT / "chunks" / "references"
LEGAL_FIELDS = (
    "contract_type",
    "area",
    "basin",
    "contractor",
    "signing_date",
    "issue_date",
    "regulation",
    "document_status",
)
DEGREES = {
    "bachelor": "Bachelor's thesis",
    "master": "Master's thesis",
    "phd": "Doctoral thesis",
    "doctoral": "Doctoral thesis",
}
MAX_ERRORS = 50


def doc_id_of(source_path: str) -> str:
    return hashlib.sha1(source_path.encode("utf-8")).hexdigest()[:12]


def apa_author(name: str) -> str:
    surname, _, given = name.partition(",")
    parts = given.replace("-", " ").split()
    if not parts:
        return surname.strip()
    initials = " ".join(f"{part[0]}." for part in parts)
    return f"{surname.strip()}, {initials}"


def author_line(meta: dict) -> tuple[str, bool]:
    authors = [apa_author(a) for a in meta.get("authors") or []]
    if not authors:
        return meta.get("institution") or "s.a.", False
    if len(authors) == 1:
        return authors[0], True
    return ", ".join(authors[:-1]) + " & " + authors[-1], True


def reference_of(meta: dict) -> str:
    """APA-like reference line built only from corpus_metadata.yaml."""
    who, has_authors = author_line(meta)
    year = meta.get("year") or "s.f."
    parts = [f"{who} ({year}).", f"{meta['title'].rstrip('.')}."]
    degree = DEGREES.get((meta.get("degree") or "").lower())
    if degree:
        parts.append(f"{degree}, {meta.get('institution')}.")
    elif meta.get("venue"):
        parts.append(f"{meta['venue']}.")
    elif has_authors and meta.get("institution"):
        parts.append(f"{meta['institution']}.")
    if meta.get("doi"):
        parts.append(f"https://doi.org/{meta['doi']}")
    return " ".join(parts)


def legal_of(meta: dict) -> Jsonb:
    legal = {}
    for key in LEGAL_FIELDS:
        value = meta.get(key)
        if value in (None, ""):
            continue
        legal[key] = value.isoformat() if isinstance(value, date) else value
    return Jsonb(legal)


def document_row(source_path: str, meta: dict, entry: dict) -> dict:
    pages = entry.get("pages")
    return {
        "doc_id": doc_id_of(source_path),
        "source_path": source_path,
        "collection": meta.get("collection"),
        "scope": meta.get("scope", "core"),
        "doc_type": meta.get("doc_type"),
        "language": meta.get("language"),
        "title": meta.get("title"),
        "authors": list(meta.get("authors") or []),
        "year": meta.get("year"),
        "institution": meta.get("institution"),
        "venue": meta.get("venue"),
        "doi": meta.get("doi"),
        "degree": meta.get("degree"),
        "topics": list(meta.get("topics") or []),
        "formations": list(meta.get("formations") or []),
        "extraction_flags": list(meta.get("extraction_flags") or []),
        "legal": legal_of(meta),
        "citation": short_citation(meta),
        "reference": reference_of(meta),
        "markdown_path": f"markdown/{entry['markdown']}",
        "sha256": entry["sha256"],
        "pages": int(pages) if pages else None,
    }


def build_documents(metadata: dict, manifest: dict) -> list[dict]:
    rows = []
    for source_path, meta in metadata.items():
        rows.append(document_row(source_path, meta, manifest[source_path]))
    return rows


def build_chunks(records: list[dict], embed_index: dict) -> list[tuple]:
    seq: Counter = Counter()
    rows = []
    for record in records:
        seq[record["doc_id"]] += 1
        rows.append((
            record["chunk_id"],
            record["doc_id"],
            seq[record["doc_id"]],
            record["chunk_type"],
            record["heading_path"],
            record["page_start"],
            record["page_end"],
            record["table_id"] or None,
            record["article"] or None,
            record["clause"] or None,
            record["text"],
            record["embed_text"],
            record["lexical_text"],
            record["tokens"],
            embed_index[record["chunk_id"]]["hash"],
            record["pipeline_version"],
        ))
    return rows


def chunk_errors(record: dict, scopes: dict, embed_index: dict) -> list[str]:
    errors = []
    source_path = record["source_path"]
    if record["doc_id"] != doc_id_of(source_path):
        errors.append(f"doc_id mismatch for {source_path}")
    elif record["doc_id"] not in scopes:
        errors.append(f"chunk of unknown document {source_path}")
    elif scopes[record["doc_id"]] == "excluded":
        errors.append(f"chunk of excluded document {source_path}")

    cached = embed_index.get(record["chunk_id"])
    if not cached or cached["hash"] != content_hash(record["embed_text"]):
        errors.append(f"no matching embedding for {record['chunk_id']}")
    return errors


def corpus_errors(metadata: dict, manifest: dict, records: list[dict],
                  references: dict) -> list[str]:
    errors = []
    if set(metadata) != set(manifest):
        errors.append("corpus_metadata.yaml and manifest.csv differ")
    for source_path, row in manifest.items():
        if row["status"] != "ok":
            errors.append(f"manifest status {row['status']}: {source_path}")

    ids = [r["chunk_id"] for r in records]
    if len(ids) != len(set(ids)):
        errors.append("duplicate chunk_id values")
    versions = {r["pipeline_version"] for r in records}
    if versions != {PIPELINE_VERSION}:
        errors.append(f"pipeline versions {sorted(versions)}")

    for name, doc_id in references.items():
        if doc_id is None:
            errors.append(f"reference file without document: {name}")

    chunked = {r["doc_id"] for r in records}
    for source_path, meta in metadata.items():
        indexed = meta.get("scope", "core") != "excluded"
        if indexed and doc_id_of(source_path) not in chunked:
            errors.append(f"indexed document without chunks: {source_path}")
    return errors


def validate(metadata: dict, manifest: dict, records: list[dict],
             embed_index: dict, references: dict) -> list[str]:
    """All problems found in the inputs; empty when the load may proceed."""
    errors = corpus_errors(metadata, manifest, records, references)
    scopes = {}
    for source_path, meta in metadata.items():
        scopes[doc_id_of(source_path)] = meta.get("scope", "core")
    for record in records:
        errors.extend(chunk_errors(record, scopes, embed_index))
    return errors[:MAX_ERRORS]


def read_inputs() -> tuple[dict, dict, list[dict], dict, dict[str, Any]]:
    metadata = load_metadata(METADATA)
    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        manifest = {row["source_path"]: row for row in csv.DictReader(handle)}
    with CHUNKS.open(encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle]
    embed_index = json.loads(EMBED_INDEX.read_text(encoding="utf-8"))

    by_markdown = {}
    for source_path, row in manifest.items():
        by_markdown[row["markdown"]] = doc_id_of(source_path)
    references = {}
    for path in sorted(REFERENCES.glob("*.md")):
        references[path.name] = by_markdown.get(path.name)
    return metadata, manifest, records, embed_index, references
