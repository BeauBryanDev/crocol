"""Audit PDFs for a text-only RAG ingestion (no OCR, no vision models).

Measures how much usable body text each file yields, separating it from legend
text that sits inside figures (maps, strata columns, plates), which pages have
nothing extractable, where extraction is fragmented, and where text is garbled.

Usage:
    magdalena/bin/python pipelines/audit_pdf.py [input_dir] [--out audit_out] [--table-sample 15]

Writes audit_out/audit.csv, audit.json and audit_pages.csv (per-page) and prints a summary.
"""

import argparse
import csv
import hashlib
import json
import random
import re
import sys
import time
from pathlib import Path

import pymupdf

MIN_TEXT_CHARS = 100
LOST_PAGE_RATIO = 0.6
PARTIAL_PAGE_RATIO = 0.1
GARBLED_THRESHOLD = 0.15
GARBLED_PAGE_MIN_CHARS = 200
SHORT_LINE_CHARS = 20
FRAGMENTED_RATIO = 0.6
FRAGMENTED_MIN_LINES = 15
FIGURE_MIN_IMAGE_AREA = 0.05
FIGURE_MIN_PATHS = 20
FIGURE_MIN_CURVES = 5
FIGURE_MIN_FILLS = 10
FIGURE_MIN_FILL_SIDE = 3.0
FIGURE_MAX_AREA = 0.95
LEGEND_OVERLAP = 0.5
LEGEND_HEAVY_RATIO = 0.15
PROSE_LINE_WORDS = 8
PROSE_LINE_SHARE = 0.5
PROSE_MIN_WORDS = 80
MIN_TABLE_ROWS = 2
MIN_TABLE_COLS = 2

CAPTION_PATTERNS = {
    "figure": re.compile(r"^\s*(figura|figure|fig\.)\s*\d+", re.I | re.M),
    "table": re.compile(r"^\s*(tabla|table)\s*\d+", re.I | re.M),
    "map": re.compile(
        r"^\s*(figura|figure|fig\.)\s*\d+.{0,120}\b(mapa|map)\b", re.I | re.M
    ),
    "strat": re.compile(
        r"^\s*(figura|figure|fig\.)\s*\d+.{0,160}"
        r"(columna|column|secci[oó]n|section)\s+"
        r"(estratigr[aá]fic|litol[oó]gic|stratigraphic|lithologic|measured)",
        re.I | re.M,
    ),
}

STOPWORDS = {
    "es": {"el", "la", "los", "las", "de", "del", "que", "en", "y", "por",
           "con", "para", "una", "un", "se", "su", "al", "como", "es", "formacion"},
    "en": {"the", "of", "and", "to", "in", "is", "that", "for", "with", "are",
           "as", "by", "on", "this", "from", "which", "was", "formation", "be"},
}
WORD_RE = re.compile(r"[a-záéíóúñü]+", re.IGNORECASE)


def sha256(path, block=1 << 20):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(block):
            digest.update(chunk)
            
    return digest.hexdigest()


def language_counts(text):
    words = [w.lower() for w in WORD_RE.findall(text)]
    hits = {lang: sum(1 for w in words if w in vocab) for lang, vocab in STOPWORDS.items()}
    
    return len(words), hits


def detect_language(word_total, hits):
    if word_total < 50:
        return "unknown", 0.0
    best = max(hits, key=hits.get)
    score = hits[best] / word_total
    if score < 0.05:
        return "unknown", score
    return best, score


def garbled_count(text):
    return sum(
        1 for c in text
        if c == "�"
        or 0xE000 <= ord(c) <= 0xF8FF
        or (ord(c) < 32 and c not in "\n\r\t")
    )


def figure_regions(page):
    
    page_area = abs(page.rect) or 1.0
    regions = []
    
    for info in page.get_image_info():
        
        bbox = pymupdf.Rect(info["bbox"]) & page.rect
        
        if FIGURE_MIN_IMAGE_AREA <= abs(bbox) / page_area <= FIGURE_MAX_AREA:
            regions.append(bbox)
            
    drawings = page.get_drawings()
    if not drawings:
        return regions, 0
    for cluster in page.cluster_drawings(drawings=drawings):
        if abs(cluster) / page_area > FIGURE_MAX_AREA:
            continue
        members = [d for d in drawings if d["rect"] in cluster]
        curves = sum(1 for d in members for item in d["items"] if item[0] in ("c", "qu"))
        fills = sum(
            1 for d in members
            if d.get("fill") not in (None, (1.0, 1.0, 1.0))
            and min(d["rect"].width, d["rect"].height) >= FIGURE_MIN_FILL_SIDE
        )
        if len(members) >= FIGURE_MIN_PATHS and (
            curves >= FIGURE_MIN_CURVES or fills >= FIGURE_MIN_FILLS
        ):
            regions.append(cluster)
    return [r for r in regions if not is_prose_region(page, r)], len(drawings)


def is_prose_region(page, region):
    lines = {}
    for word in page.get_text("words", clip=region):
        lines.setdefault((word[5], word[6]), []).append(word)
    if not lines:
        return False
    words = sum(len(ws) for ws in lines.values())
    prose = sum(1 for ws in lines.values() if len(ws) >= PROSE_LINE_WORDS)
    return words >= PROSE_MIN_WORDS and prose / len(lines) >= PROSE_LINE_SHARE


def in_figure(rect, regions):
    area = abs(rect)
    if not area:
        return False
    return any(abs(rect & region) / area >= LEGEND_OVERLAP for region in regions)


def classify_page(page):
    regions, drawings = figure_regions(page)
    has_graphics = bool(regions) or drawings > 0 or bool(page.get_images())
    body_parts = []
    legend_chars = 0
    for x0, y0, x1, y1, text, _, block_type in page.get_text("blocks"):
        if block_type != 0:
            continue
        if in_figure(pymupdf.Rect(x0, y0, x1, y1), regions):
            legend_chars += len(text.strip())
        else:
            body_parts.append(text)
    body = "\n".join(body_parts)
    body_chars = len(body.strip())
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    short_ratio = (
        sum(len(ln) < SHORT_LINE_CHARS for ln in lines) / len(lines) if lines else 0.0
    )
    raw_chars = body_chars + legend_chars
    if body_chars >= MIN_TEXT_CHARS:
        state = "text"
    elif raw_chars >= MIN_TEXT_CHARS:
        state = "figure_only"
    elif has_graphics:
        state = "no_text_layer"
    else:
        state = "blank"
    garbled = garbled_count(body)
    return {
        "body": body,
        "body_chars": body_chars,
        "legend_chars": legend_chars,
        "figure_regions": len(regions),
        "state": state,
        "fragmented": len(lines) >= FRAGMENTED_MIN_LINES and short_ratio >= FRAGMENTED_RATIO,
        "garbled": garbled,
        "garbled_ratio": garbled / len(body) if body else 0.0,
        "captions": {
            name: len(pattern.findall(body)) for name, pattern in CAPTION_PATTERNS.items()
        },
    }


def empty_page():
    return {
        "body": "", "body_chars": 0, "legend_chars": 0, "figure_regions": 0,
        "state": "error", "fragmented": False, "garbled": 0, "garbled_ratio": 0.0,
        "captions": dict.fromkeys(CAPTION_PATTERNS, 0),
    }


def count_tables(doc, sample_size, rng):
    candidates = list(range(len(doc)))
    if sample_size == 0:
        return 0, 0
    if 0 < sample_size < len(candidates):
        candidates = sorted(rng.sample(candidates, sample_size))
    found = 0
    for index in candidates:
        try:
            tables = doc[index].find_tables().tables
        except Exception:
            continue
        found += sum(
            1 for t in tables
            if t.row_count >= MIN_TABLE_ROWS and t.col_count >= MIN_TABLE_COLS
        )
    return found, len(candidates)


def audit_pdf(path, table_sample):
    started = time.perf_counter()
    record = {
        "file": path.name,
        "size_mb": round(path.stat().st_size / (1 << 20), 2),
        "sha256": sha256(path),
        "status": "ok",
        "error": "",
    }
    try:
        doc = pymupdf.open(path)
    except Exception as exc:
        record.update(status="unreadable", error=str(exc))
        return record

    with doc:
        record["encrypted"] = doc.is_encrypted
        if doc.is_encrypted and not doc.authenticate(""):
            record.update(status="encrypted", error="password required")
            return record

        meta = doc.metadata or {}
        record["title"] = meta.get("title") or ""
        record["author"] = meta.get("author") or ""
        record["creator"] = meta.get("creator") or ""
        record["producer"] = meta.get("producer") or ""
        record["creation_date"] = meta.get("creationDate") or ""
        record["pages"] = len(doc)
        record["toc_entries"] = len(doc.get_toc())

        pages = []
        word_total = 0
        lang_hits = dict.fromkeys(STOPWORDS, 0)
        for page in doc:
            try:
                info = classify_page(page)
            except Exception:
                info = empty_page()
                record["status"] = "partial"
            words, hits = language_counts(info["body"])
            word_total += words
            for lang, count in hits.items():
                lang_hits[lang] += count
            pages.append(info)

        total = len(pages) or 1
        states = {s: sum(p["state"] == s for p in pages)
                  for s in ("text", "figure_only", "no_text_layer", "blank", "error")}
        body_chars = sum(p["body_chars"] for p in pages)
        legend_chars = sum(p["legend_chars"] for p in pages)
        all_chars = sum(len(p["body"]) for p in pages)
        garbled_total = sum(p["garbled"] for p in pages)
        garbled_pages = [
            n for n, p in enumerate(pages, 1)
            if p["body_chars"] >= GARBLED_PAGE_MIN_CHARS
            and p["garbled_ratio"] > GARBLED_THRESHOLD
        ]
        fragmented_pages = sum(p["fragmented"] for p in pages)
        language, lang_score = detect_language(word_total, lang_hits)
        rng = random.Random(record["sha256"])
        tables, table_pages = count_tables(doc, table_sample, rng)
        captions = {
            name: sum(p["captions"][name] for p in pages) for name in CAPTION_PATTERNS
        }

        record["_page_rows"] = [
            {
                "file": path.name,
                "page": number,
                "state": p["state"],
                "body_chars": p["body_chars"],
                "legend_chars": p["legend_chars"],
                "figure_regions": p["figure_regions"],
                "fragmented": p["fragmented"],
                "garbled_ratio": round(p["garbled_ratio"], 4),
                **{f"cap_{k}": v for k, v in p["captions"].items()},
            }
            for number, p in enumerate(pages, 1)
        ]

        lost_pages = states["no_text_layer"] + states["figure_only"]
        record.update(
            text_pages=states["text"],
            figure_only_pages=states["figure_only"],
            no_text_pages=states["no_text_layer"],
            blank_pages=states["blank"],
            usable_page_ratio=round(states["text"] / total, 2),
            body_chars=body_chars,
            legend_chars=legend_chars,
            legend_ratio=round(legend_chars / ((body_chars + legend_chars) or 1), 3),
            avg_body_chars_per_page=round(body_chars / total, 1),
            fragmented_pages=fragmented_pages,
            garbled_ratio=round(garbled_total / (all_chars or 1), 4),
            garbled_pages=len(garbled_pages),
            garbled_page_list=",".join(map(str, garbled_pages)),
            language=language,
            language_score=round(lang_score, 3),
            tables_in_sample=tables,
            table_sample_pages=table_pages,
            figure_captions=captions["figure"],
            table_captions=captions["table"],
            map_captions=captions["map"],
            strat_column_captions=captions["strat"],
        )

        lost_ratio = lost_pages / total
        if body_chars == 0 or lost_ratio >= LOST_PAGE_RATIO:
            record["kind"] = "no_text"
        elif lost_ratio >= PARTIAL_PAGE_RATIO:
            record["kind"] = "partial"
        else:
            record["kind"] = "text"

        flags = []
        if record["kind"] == "no_text":
            flags.append("EXCLUDE_no_text_layer")
        elif record["kind"] == "partial":
            flags.append("partial_text_loss")
        if fragmented_pages / total >= 0.15:
            flags.append("fragmented_text")
        if record["garbled_ratio"] > GARBLED_THRESHOLD:
            flags.append("garbled_text")
        elif garbled_pages:
            flags.append("garbled_pages")
        if (table_pages and tables / table_pages >= 0.5) or captions["table"] >= 5:
            flags.append("table_heavy")
        if record["legend_ratio"] >= LEGEND_HEAVY_RATIO:
            flags.append("legend_heavy")
        if record["toc_entries"] == 0 and total > 50:
            flags.append("no_toc_long_doc")
        if states["error"]:
            flags.append(f"page_errors:{states['error']}")
        if language == "unknown" and body_chars > 0:
            flags.append("language_unknown")
        record["flags"] = ";".join(flags)

    record["audit_seconds"] = round(time.perf_counter() - started, 2)
    return record


def audit_txt(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    language, score = detect_language(*language_counts(text))
    return {
        "file": path.name,
        "size_mb": round(path.stat().st_size / (1 << 20), 2),
        "sha256": sha256(path),
        "status": "ok",
        "error": "",
        "kind": "text",
        "usable_page_ratio": 1.0,
        "body_chars": len(text),
        "language": language,
        "language_score": round(score, 3),
        "garbled_ratio": round(garbled_count(text) / (len(text) or 1), 4),
        "flags": "",
    }


def mark_duplicates(records):
    seen = {}
    for record in records:
        digest = record.get("sha256")
        if digest in seen:
            record["duplicate_of"] = seen[digest]
        else:
            seen[digest] = record["file"]
            record["duplicate_of"] = ""


def write_outputs(records, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    page_rows = []
    for record in records:
        page_rows.extend(record.pop("_page_rows", []))
    if page_rows:
        with (out_dir / "audit_pages.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(page_rows[0]))
            writer.writeheader()
            writer.writerows(page_rows)
    fields = []
    for record in records:
        for key in record:
            if key not in fields:
                fields.append(key)
    with (out_dir / "audit.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    with (out_dir / "audit.json").open("w", encoding="utf-8") as handle:
        json.dump(records, handle, ensure_ascii=False, indent=2)


def print_summary(records):
    header = (f"{'file':44} {'pg':>4} {'kind':7} {'lang':4} {'use%':>4} "
              f"{'leg%':>4} {'frag':>4} {'garb':>4} {'tab':>4} flags")
    print(header)
    print("-" * len(header))
    for r in records:
        name = r["file"] if len(r["file"]) <= 42 else r["file"][:39] + "..."
        use = int(r.get("usable_page_ratio", 0) * 100)
        legend = int(r.get("legend_ratio", 0) * 100)
        print(f"{name:44} {r.get('pages', '-'):>4} {r.get('kind', r['status']):7} "
              f"{r.get('language', '-'):4} {use:>4} {legend:>4} "
              f"{r.get('fragmented_pages', '-'):>4} {r.get('garbled_pages', '-'):>4} "
              f"{r.get('table_captions', '-'):>4} {r.get('flags', '')}")
    kinds = {}
    for r in records:
        key = r.get("kind", r["status"])
        kinds[key] = kinds.get(key, 0) + 1
    pages = sum(r.get("pages", 0) for r in records)
    print(f"\n{len(records)} files, {pages} pages, by kind: {kinds}")
    lost = sum(r.get("no_text_pages", 0) + r.get("figure_only_pages", 0) for r in records)
    frag = sum(r.get("fragmented_pages", 0) for r in records)
    garb = sum(r.get("garbled_pages", 0) for r in records)
    legend = sum(r.get("legend_chars", 0) for r in records)
    print(f"lost pages (no text / figure only): {lost}; fragmented: {frag}; "
          f"garbled: {garb}; legend chars excluded: {legend}")
    dupes = [f"{r['file']} == {r['duplicate_of']}" for r in records if r.get("duplicate_of")]
    if dupes:
        print(f"duplicates: {dupes}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", nargs="?", default=".", type=Path)
    parser.add_argument("--out", default="audit_out", type=Path)
    parser.add_argument("--table-sample", default=15, type=int,
                        help="pages per PDF probed for tables (0 disables, -1 all)")
    args = parser.parse_args()

    if not args.input_dir.is_dir():
        sys.exit(f"not a directory: {args.input_dir}")

    files = sorted(
        p for p in args.input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in {".pdf", ".txt"}
    )
    records = []
    for index, path in enumerate(files, 1):
        print(f"[{index}/{len(files)}] {path.name}", file=sys.stderr)
        if path.suffix.lower() == ".pdf":
            records.append(audit_pdf(path, args.table_sample))
        else:
            records.append(audit_txt(path))

    mark_duplicates(records)
    write_outputs(records, args.out)
    print_summary(records)
    print(f"\nreports written to {args.out}/")


if __name__ == "__main__":
    main()
