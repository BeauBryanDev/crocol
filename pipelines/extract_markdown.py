"""Convert every PDF (and .txt) in a directory to one Markdown file per document.

Body text is kept in reading order (two-column aware), running headers/footers
are removed, legend text inside figures is dropped, figure captions are kept,
headings are inferred from font size, and tables from tables_handling are
inserted in place as Markdown tables. Page boundaries are kept as
<!-- page N --> comments for citation.

Legal mode (--legal) is for ANH contracts and acuerdos: headings come from
ANEXO / CAPITULO / CLAUSULA / ARTICULO / numbered-clause patterns instead of
font sizes (these PDFs carry a scanner OCR layer), repeated logo text is
dropped, uncaptioned layout tables (e.g. area coordinates) are extracted, and
contract metadata (type, area, basin, contractor, signing date) goes into the
front matter.

Usage:
    magdalena/bin/python pipelines/extract_markdown.py [input_dir] [--out markdown] [--collection NAME] [--legal]

Writes markdown/<document>.md and merges rows into markdown/manifest.csv.
"""

import argparse
import csv
import hashlib
import re
import sys
from collections import Counter
from pathlib import Path

import pymupdf

from audit_pdf import figure_regions
from clean import join_lines, normalize_text
from contract_metadata import (DOC_TYPE_NAMES, LEGAL_MARGIN_RE, TOC_PAGE_RE, legal_heading,
                               legal_metadata, parse_date, split_inline_heading, wrapped_article)
from tables_handling import extract_tables, is_two_column, to_markdown

MARGIN_ZONE = 0.08
REPEAT_MIN_PAGES = 3
REPEAT_MIN_RATIO = 0.03
TABLE_OVERLAP = 0.5
LEGEND_OVERLAP = 0.5
FULL_WIDTH_RATIO = 0.55
HEADING_MIN_DELTA = 1.0
HEADING_MAX_CHARS = 150
HEADING_MAX_LINES = 3
MAX_HEADING_LEVELS = 3
SINGLE_LINE_DOC_RATIO = 0.6
PARAGRAPH_GAP_FACTOR = 1.4
INDENT_BREAK = 8.0
LEGAL_SIZE_TOLERANCE = 2.0
REPEATED_SHORT_CHARS = 40
REPEATED_SHORT_MIN_PAGES = 3
DEFAULT_COLLECTION = "VMM_Basin"
TOC_MIN_PAGE_REFS = 5

FIGURE_CAPTION_RE = re.compile(r"^\s*(figura|figure|fig\.|foto|photo|plate|lámina|mapa)\s*\d+", re.I)
TABLE_CAPTION_RE = re.compile(r"^\s*(tabla|table)\s*\d+", re.I)
NUMBERED_HEADING_RE = re.compile(r"^\d+(\.\d+){0,3}\.?\s+\S")
PAGE_NUMBER_RE = re.compile(r"^(p[aá]g(ina)?\.?\s*)?\d{1,4}(\s*(de|of|/)\s*\d+)?$", re.I)
BAD_TITLES_RE = re.compile(
    r"^(microsoft word|presentaci[oó]n de powerpoint|untitled|documento\d*|tema de investigaci[oó]n)", re.I
)
INSTITUTIONS = {"UIS": "Universidad Industrial de Santander"}
THESIS_NAME_RE = re.compile(r"^(?P<authors>.+?)_(?P<inst>[A-Z]{2,10})_(?P<year>(19|20)\d{2})$")


def sha256(path, block=1 << 20):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(block):
            digest.update(chunk)
    return digest.hexdigest()


def overlap(rect, other):
    area = abs(rect)
    return abs(rect & other) / area if area else 0.0


def margin_key(text):
    return re.sub(r"\d+", "#", text.lower()).strip()


def read_blocks(page):
    blocks = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        lines, rects, sizes, bold = [], [], Counter(), Counter()
        for line in block["lines"]:
            text = normalize_text("".join(span["text"] for span in line["spans"]))
            if text:
                lines.append(text)
                rects.append(pymupdf.Rect(line["bbox"]))
            for span in line["spans"]:
                chars = len(span["text"].strip())
                sizes[round(span["size"], 1)] += chars
                bold[bool(span["flags"] & 16)] += chars
        if not lines:
            continue
        blocks.append({
            "rect": pymupdf.Rect(block["bbox"]),
            "lines": lines,
            "line_rects": rects,
            "size": sizes.most_common(1)[0][0] if sizes else 0.0,
            "bold": bold[True] > bold[False],
        })
    return blocks


def without_lines(block, regions, threshold):
    kept = [(t, r) for t, r in zip(block["lines"], block["line_rects"])
            if not any(overlap(r, region) >= threshold for region in regions)]
    if len(kept) == len(block["lines"]):
        return block, 0
    if not kept:
        return None, len(block["lines"])
    rect = pymupdf.Rect(kept[0][1])
    for _, r in kept[1:]:
        rect |= r
    trimmed = dict(block, lines=[t for t, _ in kept], line_rects=[r for _, r in kept], rect=rect)
    return trimmed, len(block["lines"]) - len(kept)


def paragraph_style(doc, body_size):
    gaps, single, total = [], 0, 0
    for page in doc:
        previous = None
        for block in sorted(read_blocks(page), key=lambda b: (b["rect"].y0, b["rect"].x0)):
            if abs(block["size"] - body_size) > 0.5:
                previous = None
                continue
            total += 1
            single += len(block["lines"]) == 1
            if previous is not None and len(block["lines"]) == 1:
                gap = block["rect"].y0 - previous["rect"].y1
                if 0 <= gap < 3 * (block["rect"].height or 1):
                    gaps.append(round(gap, 1))
            previous = block if len(block["lines"]) == 1 else None
    if not total or single / total < SINGLE_LINE_DOC_RATIO or not gaps:
        return None
    return Counter(gaps).most_common(1)[0][0]


def starts_section(block, legal):
    first = block["lines"][0]
    if not legal:
        return False
    return bool(legal_heading(join_lines(block["lines"]), len(block["lines"]))
                or legal_heading(first, 1) or split_inline_heading(first + " x"))


def join_wrapped_articles(items):
    joined = []
    for item in items:
        previous = joined[-1].get("block") if joined else None
        block = item.get("block")
        if previous and block and wrapped_article(join_lines(previous["lines"])):
            combined = dict(previous)
            combined["lines"] = previous["lines"] + block["lines"]
            combined["line_rects"] = previous["line_rects"] + block["line_rects"]
            combined["rect"] = previous["rect"] | block["rect"]
            joined[-1] = {"rect": combined["rect"], "block": combined}
        else:
            joined.append(item)
    return joined


def merge_paragraphs(items, line_gap, body_size, legal=False, toc_page=False):
    if legal and not toc_page:
        items = join_wrapped_articles(items)
    if line_gap is None:
        return items
    tolerance = LEGAL_SIZE_TOLERANCE if legal else 0.5
    merged = []
    for item in items:
        block = item.get("block")
        previous = merged[-1].get("block") if merged else None
        if (block and previous
                and not toc_page
                and abs(block["size"] - body_size) <= tolerance
                and abs(previous["size"] - body_size) <= tolerance
                and not starts_section(block, legal)
                and not starts_section(previous, legal)
                and 0 <= block["rect"].y0 - previous["rect"].y1 <= PARAGRAPH_GAP_FACTOR * line_gap + 1
                and block["rect"].x0 <= previous["line_rects"][-1].x0 + INDENT_BREAK
                and min(block["rect"].x1, previous["rect"].x1) > max(block["rect"].x0, previous["rect"].x0)
                and not FIGURE_CAPTION_RE.match(block["lines"][0])
                and not TABLE_CAPTION_RE.match(block["lines"][0])
                and not block["lines"][0].startswith("- ")):
            combined = dict(previous)
            combined["lines"] = previous["lines"] + block["lines"]
            combined["line_rects"] = previous["line_rects"] + block["line_rects"]
            combined["rect"] = previous["rect"] | block["rect"]
            merged[-1] = {"rect": combined["rect"], "block": combined}
        else:
            merged.append(item)
    return merged


def repeated_margins(doc):
    counts = Counter()
    for page in doc:
        height = page.rect.height
        seen = set()
        for block in read_blocks(page):
            rect = block["rect"]
            if rect.y1 <= height * MARGIN_ZONE or rect.y0 >= height * (1 - MARGIN_ZONE):
                for line in block["lines"]:
                    seen.add(margin_key(line))
        counts.update(seen)
    threshold = max(REPEAT_MIN_PAGES, REPEAT_MIN_RATIO * len(doc))
    return {key for key, count in counts.items() if count >= threshold}


def repeated_short_lines(doc):
    counts = Counter()
    for page in doc:
        seen = set()
        for block in read_blocks(page):
            for line in block["lines"]:
                if len(line) <= REPEATED_SHORT_CHARS:
                    seen.add(margin_key(line))
        counts.update(seen)
    return {key for key, count in counts.items() if count >= REPEATED_SHORT_MIN_PAGES}


def drop_lines(block, keys):
    kept = [(t, r) for t, r in zip(block["lines"], block["line_rects"])
            if margin_key(t) not in keys]
    if len(kept) == len(block["lines"]):
        return block
    if not kept:
        return None
    rect = pymupdf.Rect(kept[0][1])
    for _, r in kept[1:]:
        rect |= r
    return dict(block, lines=[t for t, _ in kept],
                line_rects=[r for _, r in kept], 
                rect=rect)


def drop_margin_lines(block, height):
    kept = [(t, r) for t, r in zip(block["lines"], block["line_rects"])
            if not ((r.y1 <= height * MARGIN_ZONE or r.y0 >= height * (1 - MARGIN_ZONE))
                    and LEGAL_MARGIN_RE.match(t))]
    if len(kept) == len(block["lines"]):
        return block
    if not kept:
        return None
    rect = pymupdf.Rect(kept[0][1])
    for _, r in kept[1:]:
        rect |= r
    return dict(block, lines=[t for t, _ in kept], line_rects=[r for _, r in kept], rect=rect)


def body_font_size(doc):
    sizes = Counter()
    for page in doc:
        for block in read_blocks(page):
            sizes[block["size"]] += sum(len(line) for line in block["lines"])
    return sizes.most_common(1)[0][0] if sizes else 10.0


def heading_levels(doc, body_size):
    sizes = Counter()
    for page in doc:
        for block in read_blocks(page):
            text = " ".join(block["lines"])
            if (block["size"] >= body_size + HEADING_MIN_DELTA
                    and len(text) <= HEADING_MAX_CHARS
                    and len(block["lines"]) <= HEADING_MAX_LINES):
                sizes[block["size"]] += 1
    ranked = sorted(sizes, reverse=True)[:MAX_HEADING_LEVELS]
    return {size: level for level, size in enumerate(ranked, 2)}


def heading_level(block, text, body_size, levels):
    if len(text) > HEADING_MAX_CHARS or len(block["lines"]) > HEADING_MAX_LINES:
        return None
    if FIGURE_CAPTION_RE.match(text) or TABLE_CAPTION_RE.match(text):
        return None
    if block["size"] in levels:
        return levels[block["size"]]
    if block["bold"] and block["size"] >= body_size - 0.5 and not text.endswith((".", ",", ";")):
        match = NUMBERED_HEADING_RE.match(text)
        if match:
            depth = text.split()[0].rstrip(".").count(".")
            return min(2 + depth, 2 + MAX_HEADING_LEVELS - 1)
        if text.isupper() and len(text) > 3:
            return 2 + MAX_HEADING_LEVELS - 1
    return None


def reading_order(items, page, two_column):
    if not two_column:
        return sorted(items, key=lambda item: (round(item["rect"].y0), item["rect"].x0))
    mid = page.rect.x0 + page.rect.width / 2
    ordered, left, right = [], [], []

    def flush():
        ordered.extend(sorted(left, key=lambda item: item["rect"].y0))
        ordered.extend(sorted(right, key=lambda item: item["rect"].y0))
        left.clear()
        right.clear()

    for item in sorted(items, key=lambda item: (item["rect"].y0, item["rect"].x0)):
        rect = item["rect"]
        if rect.width >= FULL_WIDTH_RATIO * page.rect.width:
            flush()
            ordered.append(item)
        elif (rect.x0 + rect.x1) / 2 < mid:
            left.append(item)
        else:
            right.append(item)
    flush()
    return ordered


def render_table(table):
    parts = [f"<!-- table {table.table_id} | pages {table.page_start}-{table.page_end} "
             f"| {table.method} -->"]
    if table.caption:
        parts.append(f"**{table.caption}**")
    parts.append(to_markdown(table))
    if table.notes:
        parts.append(f"*{normalize_text(table.notes)}*")
    return "\n\n".join(parts)


def render_block(block, body_size, levels, legal=False, toc_page=False):
    text = join_lines(block["lines"])
    if not text:
        return ""
    if FIGURE_CAPTION_RE.match(text):
        return f"*{text}*"
    if legal:
        level = legal_heading(text, len(block["lines"]))
        text = re.sub(r"^ANEXO\s*([A-Z])\b", r"ANEXO \1", text) if level == 2 else text
        if toc_page:
            if level == 2:
                return f"## {text.rstrip('.')}"
            return "\n".join(block["lines"])
        if level:
            return f"{'#' * level} {text.rstrip('.')}"
        inline = split_inline_heading(text)
        if inline:
            return f"#### {inline[0]}\n\n{inline[1]}".rstrip()
        if all(line.startswith("- ") for line in block["lines"]):
            return "\n".join(block["lines"])
        return text
    level = heading_level(block, text, body_size, levels)
    if level:
        return f"{'#' * level} {text}"
    if all(line.startswith("- ") for line in block["lines"]):
        return "\n".join(block["lines"])
    return text


def legal_title(meta, fallback):
    if meta.get("doc_type") == "contrato":
        parts = [meta.get("contract_type_name", "Contrato"), meta.get("area", ""),
                 meta.get("contractor", "")]
        return " - ".join(p for p in parts if p)
    if meta.get("regulation"):
        prefix = "Anexos del " if meta.get("doc_type") == "anexo_acuerdo" else ""
        return f"{prefix}{meta['regulation']}"
    name = DOC_TYPE_NAMES.get(meta.get("doc_type", ""))
    if name:
        draft = "Proyecto de " if meta.get("document_status") == "proyecto" and meta["doc_type"] in (
            "acuerdo", "resolucion") else ""
        label = f"{draft}{name}" if draft else name
        subject = meta.get("subject") or (fallback if fallback != name else "")
        date = f" ({meta['issue_date']})" if meta.get("issue_date") else ""
        return f"{label}{date}: {subject[:160]}" if subject else f"{label}{date}"
    return fallback


def document_title(doc, path, body_size):
    title = (doc.metadata or {}).get("title", "").strip()
    if title and not BAD_TITLES_RE.match(title) and len(title) > 8:
        return normalize_text(title)
    if not len(doc):
        return path.stem
    blocks = [b for b in read_blocks(doc[0]) if len(join_lines(b["lines"])) > 3]
    if not blocks:
        return path.stem
    top = max(b["size"] for b in blocks)
    parts, previous = [], None
    for block in sorted(blocks, key=lambda b: b["rect"].y0):
        if block["size"] < top - 0.5:
            if parts:
                break
            continue
        line_height = block["rect"].height / len(block["lines"])
        if previous is not None and block["rect"].y0 - previous.y1 > 1.5 * line_height:
            break
        parts.append(join_lines(block["lines"]))
        previous = block["rect"]
    title = " ".join(parts)[:250]
    return title if len(title) > 8 else path.stem


def thesis_metadata(path):
    match = THESIS_NAME_RE.match(path.stem)
    if not match:
        return {"doc_type": "tesis"}
    words = [w for w in match.group("authors").split("_") if w]
    et_al = bool(words) and words[-1].lower() in {"et", "all", "al"}
    while words and words[-1].lower() in {"et", "all", "al"}:
        words.pop()
    authors = " ".join(w[:1].upper() + w[1:].lower() for w in words) + (" et al." if et_al else "")
    inst = match.group("inst")
    return {
        "doc_type": "tesis",
        "authors": authors,
        "institution": INSTITUTIONS.get(inst, inst),
        "institution_code": inst,
        "year": match.group("year"),
    }


def convert_pdf(path, collection, legal=False, thesis=False):
    tables, unresolved, image_tables, _ = extract_tables(path, uncaptioned=legal)
    by_page_start, regions_by_page = {}, {}
    for table in tables:
        by_page_start.setdefault(table.page_start, []).append(table)
        for page_number, x0, y0, x1, y1 in table.regions:
            regions_by_page.setdefault(page_number, []).append(pymupdf.Rect(x0, y0, x1, y1))

    doc = pymupdf.open(path)
    with doc:
        margins = repeated_margins(doc)
        body_size = body_font_size(doc)
        levels = {} if legal else heading_levels(doc, body_size)
        line_gap = paragraph_style(doc, body_size)
        title = document_title(doc, path, body_size)
        meta = {}
        logos = set()
        if legal:
            meta = legal_metadata("\n".join(doc[i].get_text() for i in range(min(2, len(doc)))),
                                  path.name)
            title = legal_title(meta, title)
            logos = repeated_short_lines(doc)
        if thesis:
            meta = thesis_metadata(path)
        stats = Counter()
        out = []
        for page in doc:
            number = page.number + 1
            out.append(f"<!-- page {number} -->")
            height = page.rect.height
            table_rects = regions_by_page.get(number, [])
            captions = [t.caption for t in by_page_start.get(number, []) if t.caption]
            try:
                figures, _ = figure_regions(page)
            except Exception:
                figures = []
            page_blocks = read_blocks(page)
            toc_page = bool(legal and (
                TOC_PAGE_RE.search(page.get_text())
                or sum(1 for b in page_blocks for ln in b["lines"]
                       if re.fullmatch(r"\d{1,3}", ln)) >= TOC_MIN_PAGE_REFS
            ))
            items = []
            for block in page_blocks:
                if logos:
                    block = drop_lines(block, logos)
                    if block is None:
                        stats["repeated_lines"] += 1
                        continue
                rect = block["rect"]
                text = join_lines(block["lines"])
                in_margin = rect.y1 <= height * MARGIN_ZONE or rect.y0 >= height * (1 - MARGIN_ZONE)
                if in_margin and (
                    all(margin_key(line) in margins for line in block["lines"])
                    or PAGE_NUMBER_RE.match(text)
                ):
                    stats["margin_blocks"] += 1
                    continue
                if legal:
                    block = drop_margin_lines(block, height)
                    if block is None:
                        stats["margin_blocks"] += 1
                        continue
                block, dropped = without_lines(block, table_rects, TABLE_OVERLAP)
                stats["table_lines"] += dropped
                if block is None:
                    continue
                text = join_lines(block["lines"])
                if captions and len(text) > 3 and any(text in c for c in captions):
                    continue
                if not FIGURE_CAPTION_RE.match(text):
                    block, dropped = without_lines(block, figures, LEGEND_OVERLAP)
                    stats["legend_lines"] += dropped
                    if block is None:
                        continue
                items.append({"rect": block["rect"], "block": block})
            for table in by_page_start.get(number, []):
                page_number, x0, y0, x1, y1 = table.regions[0]
                items.append({"rect": pymupdf.Rect(x0, y0, x1, y1), "table": table})
            ordered = merge_paragraphs(reading_order(items, page, is_two_column(page)),
                                       line_gap, body_size, legal, toc_page)
            rendered = []
            for item in ordered:
                if "table" in item:
                    rendered.append(render_table(item["table"]))
                    stats["tables"] += 1
                else:
                    chunk = render_block(item["block"], body_size, levels, legal, toc_page)
                    if chunk:
                        rendered.append(chunk)
                        stats["chars"] += len(chunk)
                        stats["headings"] += sum(1 for ln in chunk.split("\n") if ln.startswith("#"))
            if not rendered:
                out.append(f"<!-- page {number}: no extractable text -->")
                stats["empty_pages"] += 1
            out.extend(rendered)
        pages = len(doc)
        producer = (doc.metadata or {}).get("producer", "")

    front = [
        "---",
        f"title: {yaml_quote(title)}",
        f"source: {yaml_quote(path.name)}",
        f"source_path: {yaml_quote(path.as_posix())}",
        f"collection: {yaml_quote(collection)}",
        *[f"{key}: {yaml_quote(value)}" for key, value in meta.items()],
        f"pages: {pages}",
        f"tables: {stats['tables']}",
        f"image_only_tables: {len(image_tables)}",
        f"producer: {yaml_quote(producer)}",
        "---",
        "",
        f"# {title}",
        "",
    ]
    body = "\n\n".join(out)
    body = re.sub(r"\n{3,}", "\n\n", body)
    stats["pages"] = pages
    stats["unresolved_table_captions"] = len(unresolved)
    stats["image_only_tables"] = len(image_tables)
    return "\n".join(front) + body + "\n", title, stats, meta


GLOSSARY_NAME_RE = re.compile(r"glosario|glossary", re.I)
GLOSSARY_LETTER_RE = re.compile(r"^(letra|letter)\s*:?\s*([A-ZÑ])\s*$", re.I)
GLOSSARY_TERM_MAX = 90


def convert_glossary(path, collection):
    lines = [normalize_text(line) for line in path.read_text(encoding="utf-8", errors="replace").splitlines()]
    out, terms, definition = [], 0, []

    def flush():
        if definition:
            out.append(join_lines(definition))
            definition.clear()

    title = lines[0] if lines and lines[0] else path.stem
    following = [i for i, line in enumerate(lines) if line]
    for position, index in enumerate(following[1:], 1):
        line = lines[index]
        letter = GLOSSARY_LETTER_RE.match(line)
        if letter:
            flush()
            out.append(f"## {letter.group(2).upper()}")
            continue
        next_index = following[position + 1] if position + 1 < len(following) else None
        next_line = lines[next_index] if next_index is not None else ""
        is_term = (len(line) <= GLOSSARY_TERM_MAX
                   and not line.endswith((".", ";", ","))
                   and not GLOSSARY_LETTER_RE.match(next_line)
                   and (len(next_line) > len(line) or next_line.endswith(".")))
        if is_term and not definition and out and out[-1].startswith("### "):
            is_term = False
        if is_term:
            flush()
            out.append(f"### {line.rstrip(':').strip()}")
            terms += 1
        else:
            definition.append(line)
    flush()
    front = ["---", f"title: {yaml_quote(title)}", f"source: {yaml_quote(path.name)}",
             f"source_path: {yaml_quote(path.as_posix())}",
             f"collection: {yaml_quote(collection)}", 'doc_type: "glosario"',
             f'issuer: "Agencia Nacional de Hidrocarburos (ANH)"', f"terms: {terms}",
             "pages: 0", "tables: 0", "---", "", f"# {title}", ""]
    body = "\n\n".join(out)
    return ("\n".join(front) + body + "\n", title, Counter(chars=len(body), headings=terms),
            {"doc_type": "glosario", "terms": terms})


def convert_txt(path, collection):
    if GLOSSARY_NAME_RE.search(path.name):
        return convert_glossary(path, collection)
    raw = path.read_text(encoding="utf-8", errors="replace")
    paragraphs = []
    for chunk in re.split(r"\n\s*\n", raw):
        lines = [normalize_text(line) for line in chunk.splitlines()]
        text = join_lines(lines)
        if text:
            paragraphs.append(text)
    title = paragraphs[0][:200] if paragraphs else path.stem
    front = ["---", f"title: {yaml_quote(title)}", f"source: {yaml_quote(path.name)}",
             f"source_path: {yaml_quote(path.as_posix())}",
             f"collection: {yaml_quote(collection)}", "pages: 0", "tables: 0", "---", "",
             f"# {title}", ""]
    body = "\n\n".join(paragraphs[1:])
    return "\n".join(front) + body + "\n", title, Counter(chars=len(body)), {}


def yaml_quote(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def output_name(path):
    stem = re.sub(r"[^\w.\-]+", "_", path.stem, flags=re.UNICODE).strip("_")
    return f"{stem}.md"


def known_digests(path):
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["sha256"]: row.get("source_path") or row["source"]
                for row in csv.DictReader(handle) if row.get("sha256")}


def write_manifest(path, rows):
    existing = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as handle:
            existing = list(csv.DictReader(handle))
    replaced_paths = {row.get("source_path") for row in rows}
    replaced_names = {row["source"] for row in rows}
    merged = [row for row in existing
              if row.get("source_path") not in replaced_paths
              and not (not row.get("source_path") and row.get("source") in replaced_names)] + rows
    for row in merged:
        if not row.get("collection"):
            row["collection"] = DEFAULT_COLLECTION
    fields = []
    for row in merged:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(merged)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", nargs="?", default=".", type=Path)
    parser.add_argument("--out", default="markdown", type=Path)
    parser.add_argument("--only", help="convert a single file name from input_dir")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION,
                        help=f"collection label written to front matter (default {DEFAULT_COLLECTION})")
    parser.add_argument("--legal", action="store_true",
                        help="legal-document mode for ANH contracts and acuerdos")
    parser.add_argument("--thesis", action="store_true",
                        help="academic theses named Author_Names_INST_YEAR.pdf")
    args = parser.parse_args()

    if not args.input_dir.is_dir():
        sys.exit(f"not a directory: {args.input_dir}")
    args.out.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in args.input_dir.iterdir()
                   if p.is_file() and p.suffix.lower() in {".pdf", ".txt"})
    if args.only:
        files = [p for p in files if p.name == args.only]
    seen, manifest = known_digests(args.out / "manifest.csv"), []
    for index, path in enumerate(files, 1):
        print(f"[{index}/{len(files)}] {path.name}", file=sys.stderr)
        digest = sha256(path)
        if digest in seen and seen[digest] != path.as_posix():
            print(f"  skipped: duplicate of {seen[digest]}", file=sys.stderr)
            continue
        seen[digest] = path.as_posix()
        try:
            if path.suffix.lower() == ".pdf":
                markdown, title, stats, meta = convert_pdf(path, args.collection, args.legal,
                                                           args.thesis)
            else:
                markdown, title, stats, meta = convert_txt(path, args.collection)
        except Exception as exc:
            print(f"  failed: {exc}", file=sys.stderr)
            manifest.append({"source": path.name, "source_path": path.as_posix(),
                             "collection": args.collection,
                             "markdown": "", "status": f"error: {exc}"})
            continue
        target = args.out / output_name(path)
        target.write_text(markdown, encoding="utf-8")
        manifest.append({
            "source": path.name,
            "source_path": path.as_posix(),
            "collection": args.collection,
            "markdown": target.name,
            "status": "ok",
            "title": title,
            "sha256": digest,
            "pages": stats.get("pages", 0),
            "chars": stats.get("chars", 0),
            "headings": stats.get("headings", 0),
            "tables": stats.get("tables", 0),
            "image_only_tables": stats.get("image_only_tables", 0),
            "unresolved_table_captions": stats.get("unresolved_table_captions", 0),
            "empty_pages": stats.get("empty_pages", 0),
            "margin_blocks_removed": stats.get("margin_blocks", 0),
            "table_lines_removed": stats.get("table_lines", 0),
            "legend_lines_removed": stats.get("legend_lines", 0),
            **meta,
        })

    write_manifest(args.out / "manifest.csv", manifest)

    for row in manifest:
        print(f"{row['source'][:50]:52} {row.get('pages', '-'):>4}p "
              f"{row.get('chars', 0):>9} chars {row.get('tables', 0):>3} tables "
              f"{row.get('headings', 0):>4} headings  {row['status']}")
    print(f"\nwritten to {args.out}/")


if __name__ == "__main__":
    main()
