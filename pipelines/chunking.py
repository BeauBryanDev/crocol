"""Chunk the Markdown corpus for retrieval (VMM_PLAN.md section 4).

Inputs:  markdown/*.md, markdown/manifest.csv, corpus_metadata.yaml (authoritative metadata)
Outputs: chunks/chunks.jsonl         one JSON object per chunk
         chunks/chunk_report.csv     per-document counts
         chunks/references/<doc>.md  excluded reference sections, kept for future CITES edges

Strategies by doc_type:
  legal (contract, agreement, decree, resolution, ...)  one clause/article per chunk
  glossary                                              one term per chunk
  presentation                                          one page per chunk
  everything else                                       section-based, ~600-900 tokens, overlap
Tables become their own chunks; numeric tables also yield one row card per row.

Usage:
    magdalena/bin/python pipelines/chunking.py [--only "<source_path>"] [--out chunks]
"""

import argparse
import csv
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from config.settings import CORPUS_VOLUMES, PIPELINE_VERSION
from crocol.domains.services.lexical import normalize_lexical

CHARS_PER_TOKEN = 3.8
TARGET_TOKENS = 750
MAX_TOKENS = 900
MIN_TOKENS = 220
OVERLAP_TOKENS = 100
TABLE_MAX_TOKENS = 1200
ROW_CARD_MAX_ROWS = 200
ROW_CARD_NUMERIC_SHARE = 0.3
TOC_PAGE_SHARE = 0.6

LEGAL_TYPES = {"contract", "agreement", "agreement_annex", "decree", "resolution", "technical_annex",
               "explanatory_memorandum", "notice"}
SKIP_SECTIONS = ["dedicatoria", "agradecimientos", "agradecimiento", "tabla de contenido", "contenido",
                 "indice", "lista de figuras", "lista de tablas", "lista de anexos", "acknowledgements",
                 "acknowledgments", "table of contents", "list of figures", "list of tables"]
EXTRA_REFERENCE_SECTIONS = ["referencias bibliograficas", "bibliografia", "literature cited",
                            "cited references", "referencias citadas"]

PAGE_RE = re.compile(r"^<!-- page (\d+)(?::[^>]*)? -->$")
TABLE_RE = re.compile(r"^<!-- table (\S.*?) \| pages (\d+)-(\d+) \| (\w+) -->$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
FRONT_RE = re.compile(r"\A---\n.*?\n---\n", re.S)
NUMBER_PREFIX_RE = re.compile(r"^(?:\d+|[IVXLC]+\.)(?:\.\d+)*\.?\s*")
TOC_ENTRY_RE = re.compile(r"(\s\d{1,3}|\.{3,}\s*\d{1,3})$")
ROW_CARD_MAX_TOKENS = 400
REFERENCE_TAIL_SHARE = 0.5
SYNTHETIC_LEVEL = 7
ABSTRACT_RE = re.compile(r"^\W*(resumen|abstract)\b(?!\W*\d{1,3}\b)")
NUMERIC_RE = re.compile(r"^[\d\s.,;:%°º'’”\"<>≤≥~±+\-–/()xX*]+$")
SENTENCE_RE = re.compile(r"(?<=[.;:!?])\s+")
ARTICLE_RE = re.compile(r"\b(?:ART[IÍ]CULO|Art[ií]culo)\s+(\d+(?:[.\s]\d+)*)", re.I)
CLAUSE_RE = re.compile(r"^(?:CL[AÁ]USULA\s+)?(\d{1,2}(?:\.\d{1,2})?)\.\s+\S")
PAGE_REF_RE = re.compile(r"^\d{1,3}$")
MARKER_RE = re.compile(r"<!--.*?-->", re.S)
BLANK_LINES_RE = re.compile(r"\n\s*\n+")


def tokens(text):
    return int(len(text) / CHARS_PER_TOKEN) + 1


def clean_body(text):
    """Chunk text for embedding and BM25: page and table markers removed."""
    return BLANK_LINES_RE.sub("\n\n", MARKER_RE.sub("", text)).strip()


def fold(text):
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower().strip()


def section_key(heading):
    return fold(NUMBER_PREFIX_RE.sub("", heading.strip("*_ :.")))


EXACT_ONLY = {"indice", "contenido"}


def matches(heading, names):
    key = section_key(heading)
    return any(key == n or (n not in EXACT_ONLY and key.startswith(n + " ")) for n in names)


def starts_with_section(text, names):
    key = section_key(text[:80])
    return any(key.startswith(n + " ") for n in names)


@dataclass
class Block:
    kind: str
    text: str
    page: int
    level: int = 0
    table: dict = field(default_factory=dict)


def parse_blocks(markdown):
    body = FRONT_RE.sub("", markdown, count=1)
    raw = [b.strip() for b in re.split(r"\n\s*\n", body) if b.strip()]
    blocks, page, index, title_skipped = [], 1, 0, False
    while index < len(raw):
        block = raw[index]
        index += 1
        page_match = PAGE_RE.match(block)
        if page_match:
            page = int(page_match.group(1))
            blocks.append(Block("page", "", page))
            continue
        table_match = TABLE_RE.match(block)
        if table_match:
            caption, grid, notes = "", "", ""
            if index < len(raw) and raw[index].startswith("**") and raw[index].endswith("**"):
                caption = raw[index].strip("*").strip()
                index += 1
            if index < len(raw) and raw[index].startswith("|"):
                grid = raw[index]
                index += 1
            if index < len(raw) and raw[index].startswith("*") and not raw[index].startswith("**"):
                notes = raw[index].strip("*").strip()
                index += 1
            if grid:
                blocks.append(Block("table", grid, page, table={
                    "id": table_match.group(1), "page_start": int(table_match.group(2)),
                    "page_end": int(table_match.group(3)), "method": table_match.group(4),
                    "caption": caption, "notes": notes}))
            continue
        if block.startswith("<!--"):
            continue
        heading = HEADING_RE.match(block.split("\n", 1)[0])
        if heading:
            level = len(heading.group(1))
            if level == 1 and not title_skipped:
                title_skipped = True
            else:
                blocks.append(Block("heading", heading.group(2).strip(), page, level=level))
            rest = block.split("\n", 1)[1].strip() if "\n" in block else ""
            if rest:
                blocks.append(Block("para", rest, page))
            continue
        blocks.append(Block("para", block, page))
    return blocks


def split_long(text, limit):
    if tokens(text) <= limit:
        return [text]
    pieces, current = [], ""
    for sentence in SENTENCE_RE.split(text):
        if current and tokens(current + " " + sentence) > limit:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    out = []
    for piece in pieces:
        while tokens(piece) > limit:
            cut = int(limit * CHARS_PER_TOKEN)
            out.append(piece[:cut])
            piece = piece[cut:]
        out.append(piece)
    return out


def parse_table(grid):
    lines = [ln for ln in grid.splitlines() if ln.startswith("|")]
    rows = [[c.strip() for c in ln.strip().strip("|").split(" | ")] for ln in lines]
    rows = [r for r in rows if not all(set(c) <= {"-", " ", ":"} for c in r)]
    return (rows[0], rows[1:]) if rows else ([], [])


def is_toc_table(header, rows):
    last = [r[-1] for r in rows if r and r[-1]]
    return bool(last) and sum(1 for v in last if PAGE_REF_RE.match(v)) >= TOC_PAGE_SHARE * len(last)


def numeric_share(rows):
    cells = [c for r in rows for c in r if c]
    return sum(1 for c in cells if NUMERIC_RE.match(c)) / len(cells) if cells else 0.0


class DocumentChunker:
    def __init__(self, meta, markdown):
        self.meta = meta
        self.blocks = parse_blocks(markdown)
        self.doc_type = meta.get("doc_type", "")
        if self.doc_type in LEGAL_TYPES:
            self.strategy = "legal"
        elif self.doc_type == "glossary":
            self.strategy = "glossary"
        elif self.doc_type == "presentation":
            self.strategy = "slides"
        else:
            self.strategy = "section"
        self.reference_names = [fold(n) for n in meta.get("exclude_sections", [])] + EXTRA_REFERENCE_SECTIONS
        self.chunks, self.references = [], []
        self.stats = Counter()
        self.stack = []
        self.buffer, self.buffer_pages, self.has_body = [], [], False
        self.buffer_path = ""

    def heading_path(self):
        return " > ".join(text for _, text in self.stack)

    def emit(self, text, chunk_type, pages, path, table=None):
        text = text.strip()
        if not text:
            return
        self.chunks.append({"text": text, "chunk_type": chunk_type, "page_start": min(pages),
                            "page_end": max(pages), "heading_path": path, "table": table or {}})
        self.stats[chunk_type] += 1

    def flush(self, carry_overlap=False):
        if not self.has_body:
            return
        text = "\n\n".join(self.buffer)
        self.emit(text, "text", self.buffer_pages or [1], self.buffer_path)
        overlap = []
        if carry_overlap and self.strategy == "section":
            tail = self.buffer[-1]
            if tokens(tail) <= OVERLAP_TOKENS:
                overlap = [tail]
            else:
                sentences = SENTENCE_RE.split(tail)
                kept = []
                while sentences and tokens(" ".join([sentences[-1]] + kept)) <= OVERLAP_TOKENS:
                    kept.insert(0, sentences.pop())
                overlap = [" ".join(kept)] if kept else []
        last_page = self.buffer_pages[-1] if self.buffer_pages else 1
        self.buffer = list(overlap)
        self.buffer_pages = [last_page] if overlap else []
        self.has_body = False
        self.buffer_path = self.heading_path()

    def add_paragraph(self, text, page):
        limit = MAX_TOKENS
        for piece in split_long(text, limit):
            if (self.buffer and self.has_body and self.buffer[-1][-1:] not in ".:;!?)]\""
                    and piece[:1].islower() and not self.buffer[-1].startswith("#")):
                self.buffer[-1] = f"{self.buffer[-1]} {piece}"
            else:
                if self.has_body and tokens("\n\n".join(self.buffer + [piece])) > MAX_TOKENS:
                    self.flush(carry_overlap=True)
                if not self.buffer:
                    self.buffer_path = self.heading_path()
                self.buffer.append(piece)
            self.buffer_pages.append(page)
            self.has_body = True
            if self.strategy == "section" and tokens("\n\n".join(self.buffer)) >= TARGET_TOKENS:
                self.flush(carry_overlap=True)

    def on_heading(self, block):
        while self.stack and self.stack[-1][0] >= block.level:
            self.stack.pop()
        if self.strategy == "legal" or self.strategy == "glossary":
            self.flush()
        elif self.strategy == "section" and tokens("\n\n".join(self.buffer)) >= MIN_TOKENS:
            self.flush()
        self.stack.append((block.level, block.text))
        if not self.buffer:
            self.buffer_path = self.heading_path()
        self.buffer.append(f"{'#' * min(block.level, 2 if block.level == SYNTHETIC_LEVEL else 6)} {block.text}")
        self.buffer_pages.append(block.page)

    def emit_table(self, block):
        header, rows = parse_table(block.text)
        info = block.table
        if not header or is_toc_table(header, rows):
            self.stats["toc_tables_dropped"] += 1
            return
        caption = info["caption"] or f"Table {info['id']}"
        pages = [info["page_start"], info["page_end"]]
        path = self.heading_path()
        head = [f"**{caption}**"] if info["caption"] else []
        notes = [f"*{info['notes']}*"] if info["notes"] else []
        header_lines = block.text.splitlines()[:2]
        body_lines = block.text.splitlines()[2:]
        if tokens(block.text) <= TABLE_MAX_TOKENS:
            self.emit("\n\n".join(head + [block.text] + notes), "table", pages, path, info)
        else:
            groups, group = [], []
            for line in body_lines:
                if group and tokens("\n".join(header_lines + group + [line])) > TABLE_MAX_TOKENS:
                    groups.append(group)
                    group = []
                group.append(line)
            if group:
                groups.append(group)
            part = 0
            for group in groups:
                text = "\n\n".join(head + ["\n".join(header_lines + group)] + notes)
                for piece in split_long(text, TABLE_MAX_TOKENS):
                    part += 1
                    self.emit(piece, "table", pages, path, {**info, "part": part})
        if rows and len(rows) <= ROW_CARD_MAX_ROWS and numeric_share(rows) >= ROW_CARD_NUMERIC_SHARE:
            for row in rows:
                pairs = []
                for name, value in zip(header, row):
                    if value:
                        pairs.append(value if name.startswith("col_") else f"{name}: {value}")
                card = f"{caption} | " + "; ".join(pairs)
                if pairs and tokens(card) <= ROW_CARD_MAX_TOKENS:
                    self.emit(card, "table_row", pages, path, info)

    def run(self):
        excluded_kind = None
        last_page = max((b.page for b in self.blocks), default=1)
        for block in self.blocks:
            if block.kind == "heading":
                toc_like = bool(TOC_ENTRY_RE.search(block.text))
                if excluded_kind and not toc_like and not matches(block.text, SKIP_SECTIONS):
                    excluded_kind = None
                if excluded_kind is None:
                    if matches(block.text, self.reference_names):
                        excluded_kind = "reference"
                    elif matches(block.text, SKIP_SECTIONS):
                        excluded_kind = "skip"
                    if excluded_kind:
                        self.flush()
                        self.stats[f"{excluded_kind}_sections"] += 1
                        if excluded_kind == "reference":
                            self.references.append(f"## {block.text} (p. {block.page})")
                        continue
            elif (block.kind == "para" and excluded_kind is None
                  and block.page >= REFERENCE_TAIL_SHARE * last_page
                  and (matches(block.text, self.reference_names) and len(block.text) <= 60
                       or starts_with_section(block.text, self.reference_names))):
                self.flush()
                excluded_kind = "reference"
                self.stats["reference_sections"] += 1
                self.references.append(f"## (p. {block.page})\n\n{block.text}")
                continue
            if excluded_kind == "skip" and block.kind == "para" and ABSTRACT_RE.match(fold(block.text)):
                excluded_kind = None
                label = "Abstract" if fold(block.text).lstrip(" *_#").startswith("abstract") else "Resumen"
                self.flush()
                self.stack = []
                self.on_heading(Block("heading", label, block.page, level=SYNTHETIC_LEVEL))
                self.add_paragraph(block.text, block.page)
                self.stats["abstracts_recovered"] += 1
                continue
            if excluded_kind is not None:
                if excluded_kind == "reference" and block.kind in ("para", "table"):
                    self.references.append(block.text)
                self.stats[f"{excluded_kind}_blocks"] += 1
                continue
            if block.kind == "page":
                if self.strategy == "slides":
                    self.flush()
                continue
            if block.kind == "heading":
                self.on_heading(block)
            elif block.kind == "table":
                self.emit_table(block)
            else:
                self.add_paragraph(block.text, block.page)
        self.flush()
        return self.chunks


def load_metadata(path):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    defaults = data.get("defaults", {})
    docs = {}
    for entry in data.get("documents", []):
        merged = {**defaults, **{k: v for k, v in entry.items() if v is not None}}
        docs[entry["source_path"]] = merged
    return docs


def load_volumes(volumes):
    metadata, manifest = {}, {}
    for markdown_dir, metadata_path in volumes:
        volume_meta = load_metadata(metadata_path)
        with (markdown_dir / "manifest.csv").open(encoding="utf-8") as handle:
            volume_rows = {r["source_path"]: {**r, "volume": markdown_dir} for r in csv.DictReader(handle)}
        clash = sorted((set(volume_meta) | set(volume_rows)) & (set(metadata) | set(manifest)))
        if clash:
            sys.exit(f"source_path in more than one volume: {clash}")
        missing = sorted(set(volume_rows) - set(volume_meta))
        if missing:
            sys.exit(f"documents missing from {metadata_path}: {missing}")
        metadata.update(volume_meta)
        manifest.update(volume_rows)
    return metadata, manifest


def short_citation(meta):
    authors = meta.get("authors") or []
    if authors:
        first = authors[0].split(",")[0].strip()
        who = first if len(authors) == 1 else (
            f"{first} & {authors[1].split(',')[0].strip()}" if len(authors) == 2 else f"{first} et al.")
    else:
        who = meta.get("institution") or "s.a."
    return f"{who}, {meta.get('year') or 's.f.'}"


def legal_ids(heading_path):
    article = ARTICLE_RE.search(heading_path)
    last = heading_path.split(" > ")[-1] if heading_path else ""
    clause = CLAUSE_RE.match(last)
    return (re.sub(r"\s+", ".", article.group(1)) if article else "",
            clause.group(1) if clause else "")


def build_records(source_path, meta, chunks):
    doc_id = hashlib.sha1(source_path.encode("utf-8")).hexdigest()[:12]
    title = meta.get("title", "")
    records, seen = [], Counter()
    base = {
        "doc_id": doc_id,
        "source_path": source_path,
        "collection": meta.get("collection", ""),
        "doc_type": meta.get("doc_type", ""),
        "language": meta.get("language", ""),
        "title": title,
        "authors": "; ".join(meta.get("authors") or []),
        "year": meta.get("year") or 0,
        "institution": meta.get("institution") or "",
        "citation": short_citation(meta),
        "venue": meta.get("venue") or "",
        "doi": meta.get("doi") or "",
        "degree": meta.get("degree") or "",
        "topics": ",".join(meta.get("topics") or []),
        "formations": ",".join(meta.get("formations") or []),
        "extraction_flags": ",".join(meta.get("extraction_flags") or []),
        "ocr_source": "ocr_text_layer" in (meta.get("extraction_flags") or []),
        "area": meta.get("area") or "",
        "basin": meta.get("basin") or "",
        "contractor": meta.get("contractor") or "",
        "regulation": meta.get("regulation") or "",
        "document_status": meta.get("document_status") or "",
    }
    for chunk in chunks:
        key = f"{source_path}|{chunk['heading_path']}|{chunk['chunk_type']}"
        seen[key] += 1
        chunk_id = hashlib.sha1(f"{key}|{seen[key]}|{PIPELINE_VERSION}".encode("utf-8")).hexdigest()[:16]
        article, clause = legal_ids(chunk["heading_path"]) if base["doc_type"] in LEGAL_TYPES else ("", "")
        pages = f"p. {chunk['page_start']}" if chunk["page_start"] == chunk["page_end"] else \
            f"p. {chunk['page_start']}-{chunk['page_end']}"
        prefix = f"[{title}] [{base['collection']}/{base['doc_type']}] {chunk['heading_path']} ({pages})".replace("  ", " ")
        body = clean_body(chunk["text"])
        embed_text = body if chunk["chunk_type"] == "text" else f"{chunk['heading_path']}\n{body}".strip()
        embed_text = embed_text or prefix
        lexical_source = f"{prefix}\n{body}"
        table = chunk["table"]
        records.append({
            "chunk_id": chunk_id,
            **base,
            "chunk_type": chunk["chunk_type"],
            "heading_path": chunk["heading_path"],
            "page_start": chunk["page_start"],
            "page_end": chunk["page_end"],
            "table_id": table.get("id", ""),
            "article": article,
            "clause": clause,
            "text": chunk["text"],
            "embed_text": embed_text,
            "lexical_text": normalize_lexical(lexical_source),
            "tokens": tokens(lexical_source),
            "pipeline_version": PIPELINE_VERSION,
            "authors_list": meta.get("authors") or [],
        })
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--markdown", type=Path, help="one volume only (default: all CORPUS_VOLUMES)")
    parser.add_argument("--metadata", type=Path, help="metadata for --markdown")
    parser.add_argument("--out", type=Path, default=Path("chunks"))
    parser.add_argument("--only", help="chunk a single source_path")
    args = parser.parse_args()

    if args.markdown:
        volumes = [(args.markdown, args.metadata or Path("corpus_metadata.yaml"))]
    else:
        volumes = list(CORPUS_VOLUMES)
    metadata, manifest = load_volumes(volumes)
    (args.out / "references").mkdir(parents=True, exist_ok=True)

    targets = [args.only] if args.only else sorted(manifest)
    report, total = [], Counter()
    output = args.out / ("chunks.jsonl" if not args.only else "chunks_only.jsonl")
    with output.open("w", encoding="utf-8") as sink:
        for source_path in targets:
            meta = metadata[source_path]
            row = {"source_path": source_path, 
                   "collection": meta.get("collection"),
                   "doc_type": meta.get("doc_type")
                   }
            if meta.get("scope") == "excluded":
                row["status"] = "excluded"
                report.append(row)
                total["docs_excluded"] += 1
                continue
            md_path = manifest[source_path]["volume"] / manifest[source_path]["markdown"]
            chunker = DocumentChunker(meta, md_path.read_text(encoding="utf-8"))
            records = build_records(source_path, meta, chunker.run())
            for record in records:
                sink.write(json.dumps(record, ensure_ascii=False) + "\n")
            if chunker.references:
                (args.out / "references" / md_path.name).write_text(
                    f"# References: {meta.get('title', '')}\n\nsource_path: {source_path}\n\n"
                    + "\n\n".join(chunker.references) + "\n", encoding="utf-8")
            sizes = [r["tokens"] for r in records if r["chunk_type"] == "text"]
            
            row.update({
                "status": "ok", "strategy": chunker.strategy, "chunks": len(records),
                "text": chunker.stats["text"], "table": chunker.stats["table"],
                "table_row": chunker.stats["table_row"],
                "reference_sections": chunker.stats["reference_sections"],
                "reference_blocks": chunker.stats["reference_blocks"],
                "skipped_blocks": chunker.stats["skip_blocks"],
                "toc_tables_dropped": chunker.stats["toc_tables_dropped"],
                "text_tokens_median": sorted(sizes)[len(sizes) // 2] if sizes else 0,
                "text_tokens_max": max(sizes) if sizes else 0,
            })
            report.append(row)
            total["docs"] += 1
            total["chunks"] += len(records)
            for key in ("text", "table", "table_row"):
                total[key] += chunker.stats[key]
            total["references_docs"] += bool(chunker.references)

    fields = []
    for row in report:
        for key in row:
            if key not in fields:
                fields.append(key)
    with (args.out / "chunk_report.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(report)
    print(f"{total['docs']} documents chunked, {total['docs_excluded']} excluded")
    print(f"{total['chunks']} chunks: text={total['text']} table={total['table']} table_row={total['table_row']}")
    print(f"reference sections saved for {total['references_docs']} documents")
    print(f"written: {output}, {args.out / 'chunk_report.csv'}")


if __name__ == "__main__":
    main()
