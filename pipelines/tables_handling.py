"""Extract tables from PDFs for a text-only RAG pipeline.

Two detectors run on every page:
  - ruled tables: PyMuPDF find_tables() on drawn cell borders;
  - borderless tables: anchored on a "Tabla N." / "Table N." caption, the rows
    below it are rebuilt from word positions (row clustering + column gaps).

Grids are repaired (merged cells filled, packed multi-value cells split, wrapped
rows joined, multi-row headers combined), tables continued across pages are
merged, and every table is emitted as Markdown plus one linearized text per row.

Usage:
    magdalena/bin/python pipelines/tables_handling.py [input_dir] [--out tables_out]

Writes tables_out/tables.jsonl, tables_out/tables_report.csv and prints a summary.
"""

import argparse
import csv
import json
import re
import statistics
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pymupdf

from clean import normalize_text

MIN_ROWS = 2
MIN_COLS = 2
MAX_HEADER_ROWS = 4
PROSE_BOX_MAX_COLS = 2
PROSE_BOX_CELL_CHARS = 150
MIN_FILLED_RATIO = 0.3
MAX_SPARSE_CELLS = 400
SPARSE_FILLED_RATIO = 0.5
PACKED_MIN_LINES = 3
CAPTION_MAX_ABOVE = 80.0
CAPTION_MAX_BELOW = 40.0
CAPTION_X_SLACK = 0.25
CAPTION_TITLE_GAP = 30.0
TOC_MIN_CAPTIONS = 4
TOC_MAX_SPACING = 45.0
IMAGE_TABLE_GAP = 80.0
IMAGE_TABLE_MIN_WIDTH = 0.2
CAPTION_EXTRA_LINES = 3
ROW_Y_TOLERANCE = 0.5
CELL_GAP = 8.0
COLUMN_GAP = 5.0
COLUMN_GAP_TOLERANCE = 0.1
PROSE_WIDTH_RATIO = 0.6
PROSE_MIN_WORDS = 8
MAX_ROW_GAP_FACTOR = 3.0
MIN_ROW_GAP = 30.0
CONTINUATION_TOP_RATIO = 0.25
MARGIN_ZONE = 0.08
UNCAPTIONED_MIN_SEGMENTS = 3
UNCAPTIONED_MIN_ROWS = 4
UNCAPTIONED_HEADER_LINES = 2
UNCAPTIONED_MODE_SHARE = 0.6
TOC_PAGE_NUMBER_SHARE = 0.6
PAGE_REF_RE = re.compile(r"^\d{1,3}$")
TWO_COLUMN_BLOCK_RATIO = 0.6

CAPTION_RE = re.compile(
    r"^\s*(tabla|table)\s*(\d+(?:[.\-]\d+)*)\s*(?:[.:\-–—]|$)", re.I
)
TOC_RE = re.compile(r"(\.\s*){4,}|…{2,}|_{4,}")
STOP_RE = re.compile(r"^\s*(tabla|table|figura|figure|fig\.)\s*\d+", re.I)
TOC_HEADING_RE = re.compile(
    r"(lista|[ií]ndice) de (tablas|cuadros)|list of tables|tabla de contenido", re.I
)
NOTE_RE = re.compile(r"^\s*(fuente|source|nota|note|modificad[oa]|tomad[oa])\b", re.I)
CONTINUED_RE = re.compile(r"contin[uú]a|continued|cont\.", re.I)
NUMERIC_RE = re.compile(r"^[\d\s.,;:%°º’'”\"<>≤≥~±+\-–/()xX*]+$")


@dataclass
class Table:
    file: str
    page_start: int
    page_end: int
    method: str
    caption: str
    header: list
    rows: list
    notes: str = ""
    regions: list = field(default_factory=list)
    table_id: str = ""

    @property
    def ncols(self):
        return len(self.header) if self.header else max((len(r) for r in self.rows), default=0)


def clean_cell(value):
    if value is None:
        return None
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", value)
    return normalize_text(re.sub(r"\s+", " ", text))


def is_numeric(value):
    return bool(value) and bool(NUMERIC_RE.match(value))


def fill_merged(grid, header_rows):
    for r, row in enumerate(grid):
        for c, cell in enumerate(row):
            if cell is not None:
                continue
            if r == 0:
                row[c] = row[c - 1] if c > 0 and row[c - 1] is not None else ""
            elif r < header_rows:
                above = grid[r - 1][c]
                left = row[c - 1] if c > 0 else None
                row[c] = above if above else (left or "")
            else:
                row[c] = grid[r - 1][c] or ""
    return grid


def collapse_spanned_columns(grid, header_rows):
    body = grid[header_rows:]
    if not body:
        return grid
    width = max(len(row) for row in grid)
    grid = [row + [""] * (width - len(row)) for row in grid]
    body = grid[header_rows:]
    keep = [0] + [c for c in range(1, width) if any(row[c] is not None for row in body)]
    if len(keep) == width:
        return grid
    collapsed = []
    for r, row in enumerate(grid):
        new_row = []
        for i, start in enumerate(keep):
            stop = keep[i + 1] if i + 1 < len(keep) else width
            parts = [row[c] for c in range(start, stop) if row[c]]
            if r >= header_rows:
                new_row.append(row[start] if row[start] is not None else (parts[0] if parts else None))
            else:
                unique = []
                for part in parts:
                    if part not in unique:
                        unique.append(part)
                new_row.append(" ".join(unique) if unique else row[start])
        collapsed.append(new_row)
    return collapsed


def split_packed_rows(grid):
    result = []
    for row in grid:
        parts = [(cell or "").split("\n") for cell in row]
        counts = [len(p) for p in parts if len(p) >= PACKED_MIN_LINES]
        if len(counts) >= 2 and len(set(counts)) == 1:
            depth = counts[0]
            for i in range(depth):
                result.append([
                    p[i] if len(p) == depth else (row[c] if i == 0 else "")
                    for c, p in enumerate(parts)
                ])
        else:
            result.append(row)
    return result


def drop_empty(grid):
    grid = [row for row in grid if any(cell for cell in row)]
    if not grid:
        return grid
    width = max(len(row) for row in grid)
    grid = [row + [""] * (width - len(row)) for row in grid]
    keep = [c for c in range(width) if any(row[c] for row in grid)]
    return [[row[c] for c in keep] for row in grid]


def count_header_rows(grid, merged_first_row):
    first_filled = [c for c in grid[0] if c and str(c).strip()]
    if first_filled and sum(1 for c in first_filled if is_numeric(clean_cell(c))) >= len(first_filled) / 2:
        return 0
    leading = 0
    for row in grid:
        if any(is_numeric(clean_cell(c)) for c in row if c):
            break
        leading += 1
    if 2 <= leading < len(grid):
        return min(leading, MAX_HEADER_ROWS)
    if len(grid) < 3:
        return 1
    first, second = grid[0], grid[1]
    second_textual = sum(1 for c in second if c and not is_numeric(c)) > len(second) / 2
    first_sparse = sum(1 for c in first if c) < len(first) / 2 + 1
    if second_textual and (merged_first_row or first_sparse):
        return 2
    return 1


def combine_header(grid, header_rows):
    if header_rows == 0:
        return [f"col_{c + 1}" for c in range(len(grid[0]))]
    names = []
    for c in range(len(grid[0])):
        parts = []
        for r in range(header_rows):
            value = grid[r][c]
            if value and value not in parts:
                parts.append(value)
        names.append(" / ".join(parts) or f"col_{c + 1}")
    return names


def is_transposed(grid):
    if len(grid) < 3 or len(grid[0]) < 3:
        return False
    head = [clean_cell(c) for c in grid[0][1:] if c]
    labels = [clean_cell(row[0]) for row in grid if row[0]]
    if len(head) < 2 or len(labels) < 3:
        return False
    repeated = 1 - len(set(head)) / len(head)
    textual_labels = all(not is_numeric(label) for label in labels)
    return repeated >= 0.5 and textual_labels and len(set(labels)) == len(labels)


def split_note_rows(raw):
    notes = []
    rows = list(raw)
    while rows:
        filled = [c for c in rows[-1] if c and str(c).strip()]
        if len(filled) == 1 and NOTE_RE.match(clean_cell(filled[0]) or ""):
            notes.insert(0, clean_cell(filled[0]))
            rows.pop()
        else:
            break
    return rows, " ".join(notes)


def finalize_grid(raw):
    merged_first_row = any(cell is None for cell in raw[0]) if raw else False
    grid = [[cell for cell in row] for row in raw]
    grid = split_packed_rows(grid)
    if is_transposed(grid):
        width = max(len(row) for row in grid)
        grid = [row + [""] * (width - len(row)) for row in grid]
        grid = [list(column) for column in zip(*grid)]
        merged_first_row = False
    header_rows = count_header_rows(grid, merged_first_row)
    grid = collapse_spanned_columns(grid, header_rows)
    grid = fill_merged(grid, header_rows)
    grid = [[clean_cell(cell) or "" for cell in row] for row in grid]
    grid = drop_empty(grid)
    if len(grid) < MIN_ROWS or len(grid[0]) < MIN_COLS:
        return None, None
    header_rows = min(header_rows, len(grid) - 1)
    return combine_header(grid, header_rows), grid[header_rows:]


def is_prose_box(raw):
    width = sum(1 for c in range(max((len(row) for row in raw), default=0))
                if any(c < len(row) and row[c] and row[c].strip() for row in raw))
    texts = [cell.strip() for row in raw for cell in row if cell and cell.strip()]
    if width > PROSE_BOX_MAX_COLS or not texts:
        return False
    return sum(len(t) for t in texts) / len(texts) > PROSE_BOX_CELL_CHARS


def acceptable(raw):
    cells = [cell for row in raw for cell in row]
    if not cells or is_prose_box(raw):
        return False
    filled = sum(1 for cell in cells if cell and cell.strip()) / len(cells)
    if filled < MIN_FILLED_RATIO:
        return False
    if len(cells) > MAX_SPARSE_CELLS and filled < SPARSE_FILLED_RATIO:
        return False
    return True


def page_words(page):
    return [w for w in page.get_text("words") if w[4].strip()]


def visual_lines(words):
    lines = []
    for word in sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0])):
        center = (word[1] + word[3]) / 2
        height = word[3] - word[1]
        if lines and abs(center - lines[-1]["center"]) <= ROW_Y_TOLERANCE * max(height, lines[-1]["height"]):
            line = lines[-1]
            line["words"].append(word)
            line["center"] = statistics.fmean((w[1] + w[3]) / 2 for w in line["words"])
            line["y0"] = min(line["y0"], word[1])
            line["y1"] = max(line["y1"], word[3])
        else:
            lines.append({"words": [word], "center": center, "height": height,
                          "y0": word[1], "y1": word[3]})
    for line in lines:
        line["words"].sort(key=lambda w: w[0])
    return lines


def segments(line):
    groups = []
    for word in line["words"]:
        if groups and word[0] - groups[-1][-1][2] < CELL_GAP:
            groups[-1].append(word)
        else:
            groups.append([word])
    return groups


def is_two_column(page):
    width = page.rect.width
    blocks = [b for b in page.get_text("blocks") if b[6] == 0 and len(b[4]) > 100]
    if len(blocks) < 3:
        return False
    narrow = sum(1 for b in blocks if b[2] - b[0] < 0.5 * width)
    return narrow / len(blocks) >= TWO_COLUMN_BLOCK_RATIO


def find_captions(page):
    captions = []
    listed = 0
    blocks = [b for b in page.get_text("dict")["blocks"] if b["type"] == 0]
    blocks.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
    for position, block in enumerate(blocks):
        lines = [
            ("".join(s["text"] for s in line["spans"]).strip(), pymupdf.Rect(line["bbox"]))
            for line in block["lines"]
        ]
        lines = [(t, r) for t, r in lines if t]
        for index, (text, rect) in enumerate(lines):
            match = CAPTION_RE.match(text)
            if not match:
                continue
            if TOC_RE.search(text):
                listed += 1
                continue
            parts = [text]
            bbox = pymupdf.Rect(rect)
            for extra_text, extra_rect in lines[index + 1:index + 1 + CAPTION_EXTRA_LINES]:
                if STOP_RE.match(extra_text) or abs(extra_rect.x0 - rect.x0) > 40:
                    break
                if len(parts) > 1 and len(parts[-1]) < 30:
                    break
                parts.append(extra_text)
                bbox |= extra_rect
            if len(parts) == 1 and not text[match.end():].strip():
                for following in blocks[position + 1:position + 3]:
                    rect_f = pymupdf.Rect(following["bbox"])
                    title = clean_cell(" ".join(
                        "".join(s["text"] for s in line["spans"]) for line in following["lines"]
                    ))
                    if not title:
                        continue
                    if rect_f.y0 - bbox.y1 <= CAPTION_TITLE_GAP and len(title) < 250:
                        parts.append(title)
                        bbox |= rect_f
                    break
            captions.append({
                "number": match.group(2),
                "text": clean_cell(" ".join(parts)),
                "bbox": bbox,
                "continued": bool(CONTINUED_RE.search(text)),
            })
    if is_toc_page(page, captions):
        return [], listed + len(captions)
    return captions, listed


def is_toc_page(page, captions):
    if not captions:
        return False
    if TOC_HEADING_RE.search(page.get_text()[:600]):
        return True
    if len(captions) < TOC_MIN_CAPTIONS:
        return False
    tops = sorted(c["bbox"].y0 for c in captions)
    spacing = statistics.median(b - a for a, b in zip(tops, tops[1:]))
    return spacing <= TOC_MAX_SPACING


def ruled_tables(page):
    found = []
    try:
        tables = page.find_tables().tables
    except Exception:
        return found
    for table in tables:
        if table.row_count < MIN_ROWS or table.col_count < MIN_COLS:
            continue
        raw = table.extract()
        if not acceptable(raw):
            continue
        found.append({"bbox": pymupdf.Rect(table.bbox), "raw": raw})
    return found


def caption_for(bbox, captions, used, page_width):
    slack = CAPTION_X_SLACK * page_width
    above, below = [], []
    for index, caption in enumerate(captions):
        if index in used:
            continue
        cap = caption["bbox"]
        if min(cap.x1, bbox.x1 + slack) - max(cap.x0, bbox.x0 - slack) <= 0:
            continue
        gap_above = bbox.y0 - cap.y1
        gap_below = cap.y0 - bbox.y1
        if -2 <= gap_above <= CAPTION_MAX_ABOVE:
            above.append((gap_above, index))
        elif -2 <= gap_below <= CAPTION_MAX_BELOW:
            below.append((gap_below, index))
    if above:
        return min(above)[1]
    if below:
        return min(below)[1]
    return None


def image_table(page, caption):
    cap = caption["bbox"]
    for info in page.get_image_info():
        box = pymupdf.Rect(info["bbox"])
        if box.width < IMAGE_TABLE_MIN_WIDTH * page.rect.width:
            continue
        if 0 <= box.y0 - cap.y1 <= IMAGE_TABLE_GAP or 0 <= cap.y0 - box.y1 <= CAPTION_MAX_BELOW:
            return True
    return False


def column_range(page, caption, words, two_column):
    full = (page.rect.x0 + 10, page.rect.x1 - 10)
    cap = caption["bbox"]
    if not two_column or cap.width >= 0.5 * page.rect.width:
        return full
    mid = page.rect.x0 + page.rect.width / 2
    left = cap.x0 + cap.width / 2 < mid
    own = (full[0], mid) if left else (mid, full[1])
    other = (mid, full[1]) if left else (full[0], mid)
    below = [w for w in words if cap.y1 <= w[1] <= cap.y1 + 80
             and other[0] <= w[0] and w[2] <= other[1]]
    for line in visual_lines(below)[:5]:
        for group in segments(line):
            if group[-1][2] - group[0][0] > 0.7 * (other[1] - other[0]):
                return own
    return full


def borderless_region(page, caption, words, occupied, two_column):
    x0, x1 = column_range(page, caption, words, two_column)
    width = x1 - x0
    cap = caption["bbox"]
    candidates = [
        w for w in words
        if w[1] >= cap.y1 - 1 and w[0] >= x0 - 1 and w[2] <= x1 + 1
        and not any(pymupdf.Rect(w[:4]).intersects(r) for r in occupied)
    ]
    rows, notes = [], []
    heights = []
    for line in visual_lines(candidates):
        text = " ".join(w[4] for w in line["words"])
        groups = segments(line)
        span = line["words"][-1][2] - line["words"][0][0]
        if rows:
            gap = line["y0"] - rows[-1]["y1"]
            limit = max(MAX_ROW_GAP_FACTOR * statistics.median(heights), MIN_ROW_GAP)
            if gap > limit:
                break
        if NOTE_RE.match(text) and rows:
            notes.append(text)
            break
        if STOP_RE.match(text):
            break
        prose = (len(groups) == 1 and span >= PROSE_WIDTH_RATIO * width
                 and len(line["words"]) >= PROSE_MIN_WORDS)
        if prose:
            break
        rows.append(line)
        heights.append(line["y1"] - line["y0"])
    if sum(1 for row in rows if len(segments(row)) >= 2) < 2:
        return None, None, ""
    rect = pymupdf.Rect(x0, rows[0]["y0"], x1, rows[-1]["y1"])
    return rect, rows, " ".join(notes)


def column_bounds(rows, x0, x1):
    start, stop = int(x0), int(x1) + 1
    coverage = [0] * (stop - start + 1)
    for row in rows:
        for word in row["words"]:
            for x in range(max(int(word[0]), start), min(int(word[2]) + 1, stop)):
                coverage[x - start] += 1
    tolerance = int(COLUMN_GAP_TOLERANCE * len(rows))
    bounds, run_start = [], None
    for index, count in enumerate(coverage):
        if count <= tolerance:
            if run_start is None:
                run_start = index
        elif run_start is not None:
            if index - run_start >= COLUMN_GAP and run_start > 0:
                bounds.append(start + (run_start + index) / 2)
            run_start = None
    return bounds


def grid_from_rows(rows, rect):
    bounds = column_bounds(rows, rect.x0, rect.x1)
    ncols = len(bounds) + 1
    grid = []
    for row in rows:
        cells = [[] for _ in range(ncols)]
        for word in row["words"]:
            center = (word[0] + word[2]) / 2
            column = sum(1 for b in bounds if center > b)
            cells[column].append(word[4])
        grid.append([" ".join(c) for c in cells])
    merged = []
    for row in grid:
        filled = sum(1 for c in row if c)
        if merged and not row[0] and filled <= max(1, ncols // 2):
            merged[-1] = [f"{a} {b}".strip() for a, b in zip(merged[-1], row)]
        else:
            merged.append(row)
    return merged


def uncaptioned_regions(page, words, occupied):
    top, bottom = page.rect.height * MARGIN_ZONE, page.rect.height * (1 - MARGIN_ZONE)
    free = [w for w in words
            if top <= w[1] and w[3] <= bottom
            and not any(pymupdf.Rect(w[:4]).intersects(r) for r in occupied)]
    lines = visual_lines(free)
    runs, current, heights = [], [], []

    def close():
        multi = [ln for ln in current if len(segments(ln)) >= UNCAPTIONED_MIN_SEGMENTS]
        while current and len(segments(current[-1])) < UNCAPTIONED_MIN_SEGMENTS:
            current.pop()
        if len(multi) >= UNCAPTIONED_MIN_ROWS:
            counts = [len(segments(ln)) for ln in multi]
            mode = max(set(counts), key=counts.count)
            steady = sum(1 for c in counts if abs(c - mode) <= 1) / len(counts)
            if steady >= UNCAPTIONED_MODE_SHARE:
                runs.append(list(current))
        current.clear()
        heights.clear()

    for index, line in enumerate(lines):
        multi = len(segments(line)) >= UNCAPTIONED_MIN_SEGMENTS
        if current:
            gap = line["y0"] - current[-1]["y1"]
            if gap > max(MAX_ROW_GAP_FACTOR * statistics.median(heights), MIN_ROW_GAP):
                close()
        if multi:
            if not current:
                claimed = {id(ln) for run in runs for ln in run}
                for previous in lines[max(0, index - UNCAPTIONED_HEADER_LINES):index]:
                    if (id(previous) not in claimed and len(segments(previous)) >= 2
                            and line["y0"] - previous["y1"] < MIN_ROW_GAP):
                        current.append(previous)
            current.append(line)
            heights.append(line["y1"] - line["y0"])
        elif current and len(segments(line)) <= 2 and not STOP_RE.match(
                " ".join(w[4] for w in line["words"])):
            span = line["words"][-1][2] - line["words"][0][0]
            if span < 0.5 * page.rect.width:
                current.append(line)
                heights.append(line["y1"] - line["y0"])
            else:
                close()
        elif current:
            close()
    if current:
        close()
    regions = []
    for run in runs:
        x0 = min(w[0] for ln in run for w in ln["words"]) - 1
        x1 = max(w[2] for ln in run for w in ln["words"]) + 1
        regions.append((pymupdf.Rect(x0, run[0]["y0"], x1, run[-1]["y1"]), run))
    return regions


def extract_page_tables(page, file_name, uncaptioned=False):
    page_number = page.number + 1
    captions, listed = find_captions(page)
    tables, used, occupied = [], set(), []

    for found in ruled_tables(page):
        index = caption_for(found["bbox"], captions, used, page.rect.width)
        caption = captions[index] if index is not None else None
        if index is not None:
            used.add(index)
        raw, notes = split_note_rows(found["raw"])
        if len(raw) < MIN_ROWS:
            continue
        header, rows = finalize_grid(raw)
        if header is None:
            continue
        occupied.append(found["bbox"])
        tables.append(Table(
            file=file_name, page_start=page_number, page_end=page_number,
            method="ruled", caption=caption["text"] if caption else "",
            header=header, rows=rows, notes=notes,
            regions=[[page_number, *map(round, found["bbox"])]],
        ))
        tables[-1]._continued = bool(caption and caption["continued"])
        tables[-1]._top = found["bbox"].y0

    words = page_words(page) if len(used) < len(captions) else []
    two_column = is_two_column(page) if words else False
    for index, caption in enumerate(captions):
        if index in used:
            continue
        rect, rows, notes = borderless_region(page, caption, words, occupied, two_column)
        if rect is None:
            continue
        header, body = finalize_grid(grid_from_rows(rows, rect))
        if header is None:
            continue
        occupied.append(rect)
        used.add(index)
        tables.append(Table(
            file=file_name, page_start=page_number, page_end=page_number,
            method="caption_text", caption=caption["text"], header=header,
            rows=body, notes=notes, regions=[[page_number, *map(round, rect)]],
        ))
        tables[-1]._continued = caption["continued"]
        tables[-1]._top = caption["bbox"].y0

    if uncaptioned:
        for rect, rows in uncaptioned_regions(page, page_words(page), occupied):
            raw = grid_from_rows(rows, rect)
            if not acceptable(raw):
                continue
            header, body = finalize_grid(raw)
            if header is None or len(header) < UNCAPTIONED_MIN_SEGMENTS - 1:
                continue
            last = [row[-1] for row in body if row and row[-1]]
            if last and sum(1 for v in last if PAGE_REF_RE.match(v)) >= TOC_PAGE_NUMBER_SHARE * len(body):
                continue
            occupied.append(rect)
            tables.append(Table(
                file=file_name, page_start=page_number, page_end=page_number,
                method="layout", caption="", header=header, rows=body,
                regions=[[page_number, *map(round, rect)]],
            ))
            tables[-1]._continued = False
            tables[-1]._top = rect.y0

    unresolved, images = [], []
    for i, caption in enumerate(captions):
        if i in used:
            continue
        (images if image_table(page, caption) else unresolved).append(caption["text"])
    tables.sort(key=lambda t: t._top)
    return tables, unresolved, images, listed


def merge_continuations(tables, page_heights):
    merged = []
    for table in tables:
        previous = merged[-1] if merged else None
        top_of_page = table._top <= CONTINUATION_TOP_RATIO * page_heights[table.page_start]
        follows = previous and table.page_start == previous.page_end + 1
        own_header = not all(h.startswith("col_") for h in table.header)
        same_header = table.header == previous.header if previous else False
        if follows and table.ncols == previous.ncols and (
            table._continued or (not table.caption and top_of_page and (same_header or not own_header))
        ):
            previous.rows.extend(table.rows)
            previous.page_end = table.page_start
            previous.regions.extend(table.regions)
            if table.notes:
                previous.notes = f"{previous.notes} {table.notes}".strip()
            continue
        merged.append(table)
    return merged


def to_markdown(table):
    def esc(value):
        return value.replace("|", "\\|")
    lines = [
        "| " + " | ".join(esc(h) for h in table.header) + " |",
        "| " + " | ".join("---" for _ in table.header) + " |",
    ]
    for row in table.rows:
        cells = row + [""] * (len(table.header) - len(row))
        lines.append("| " + " | ".join(esc(c) for c in cells[:len(table.header)]) + " |")
    return "\n".join(lines)


def row_texts(table):
    prefix = table.caption or f"Table on page {table.page_start}"
    texts = []
    for row in table.rows:
        pairs = [f"{h}: {v}" for h, v in zip(table.header, row) if v]
        if pairs:
            texts.append(f"{prefix} | " + "; ".join(pairs))
    return texts


def extract_tables(path, uncaptioned=False):
    doc = pymupdf.open(path)
    with doc:
        page_heights = {p.number + 1: p.rect.height for p in doc}
        tables, unresolved, images, listed = [], [], [], 0
        for page in doc:
            try:
                found, missing, pictured, toc = extract_page_tables(page, path.name, uncaptioned)
            except Exception as exc:
                print(f"  page {page.number + 1}: {exc}", file=sys.stderr)
                continue
            tables.extend(found)
            unresolved.extend(f"p{page.number + 1}: {m}" for m in missing)
            images.extend(f"p{page.number + 1}: {m}" for m in pictured)
            listed += toc
    tables = merge_continuations(tables, page_heights)
    for number, table in enumerate(tables, 1):
        table.table_id = f"{path.stem}::t{number:03d}"
    return tables, unresolved, images, listed


def table_record(table):
    record = asdict(table)
    record["n_rows"] = len(table.rows)
    record["n_cols"] = table.ncols
    record["markdown"] = to_markdown(table)
    record["row_texts"] = row_texts(table)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", nargs="?", default=".", type=Path)
    parser.add_argument("--out", default="tables_out", type=Path)
    args = parser.parse_args()

    if not args.input_dir.is_dir():
        sys.exit(f"not a directory: {args.input_dir}")
    args.out.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in args.input_dir.iterdir()
                   if p.is_file() and p.suffix.lower() == ".pdf")
    report = []
    with (args.out / "tables.jsonl").open("w", encoding="utf-8") as sink:
        for index, path in enumerate(files, 1):
            print(f"[{index}/{len(files)}] {path.name}", file=sys.stderr)
            tables, unresolved, images, listed = extract_tables(path)
            for table in tables:
                sink.write(json.dumps(table_record(table), ensure_ascii=False) + "\n")
            captioned = sum(1 for t in tables if t.caption)
            report.append({
                "file": path.name,
                "listed_in_toc": listed,
                "tables": len(tables),
                "captioned": captioned,
                "ruled": sum(1 for t in tables if t.method == "ruled"),
                "caption_text": sum(1 for t in tables if t.method == "caption_text"),
                "multi_page": sum(1 for t in tables if t.page_end > t.page_start),
                "rows": sum(len(t.rows) for t in tables),
                "image_tables": len(images),
                "unresolved_captions": len(unresolved),
                "unresolved_list": " || ".join(unresolved),
                "image_table_list": " || ".join(images),
            })

    with (args.out / "tables_report.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(report[0]))
        writer.writeheader()
        writer.writerows(report)

    header = (f"{'file':44} {'toc':>4} {'tabs':>5} {'capt':>5} {'ruled':>5} "
              f"{'text':>5} {'multi':>5} {'rows':>6} {'img':>4} {'unres':>5}")
    print(header)
    print("-" * len(header))
    for r in report:
        name = r["file"] if len(r["file"]) <= 42 else r["file"][:39] + "..."
        print(f"{name:44} {r['listed_in_toc']:>4} {r['tables']:>5} {r['captioned']:>5} "
              f"{r['ruled']:>5} {r['caption_text']:>5} {r['multi_page']:>5} "
              f"{r['rows']:>6} {r['image_tables']:>4} {r['unresolved_captions']:>5}")
    print(f"\n{sum(r['tables'] for r in report)} tables, "
          f"{sum(r['rows'] for r in report)} rows, "
          f"{sum(r['image_tables'] for r in report)} image-only tables (not recoverable), "
          f"{sum(r['unresolved_captions'] for r in report)} unresolved captions")
    print(f"written to {args.out}/")


if __name__ == "__main__":
    main()
