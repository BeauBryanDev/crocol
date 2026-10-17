import csv
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

PLACEHOLDERS = {"", "PENDIENTE", "NO DEFINIDO", "NO DEFINIDA", "0"}
LEGAL_SUFFIX_RE = re.compile(
    r"[\s,.\-]*\b(S\.?\s?A\.?\s?S?|LTDA|LTD|LIMITED|INC|CO|CORP|CORPORATION"
    r"|COMPANY|SUCURSAL(\s+COLOMBIA)?)\.?$",
    re.I,
)
PARENTHESIS_RE = re.compile(r"\s*\(.*?\)\s*$")
ORG_ALIASES = {
    "GEOFISICASISTEMASYSOLUCIONESGSS": "GEOFISICASISTEMASYSOLUCIONES",
    "GSSGEOFISICASISTEMASYSOLUCIONES": "GEOFISICASISTEMASYSOLUCIONES",
    "WESTERN": "WESTERNGEOPHYSICAL",
    "GEOSOURCEEXPLORATION": "GEOSOURCE",
    "PETTY": "PETTYGEOPHYSICAL",
    "SISMOCOL": "SISMOGRAFIACOLOMBIANA",
    "SISMOPETROLDECOLOMBIA": "SISMOPETROL",
    "UGC": "UNITEDGEOPHYSICAL",
    "UNITEDGEOPHYSICALC": "UNITEDGEOPHYSICAL",
}
REVIEW_FIELDS = [
    "department", "municipality", "wells", "canonical_department",
    "canonical_municipality", "reviewed",
]


def clean_text(value: object) -> str | None:
    """Same rules as core.clean_text: NBSP, spaces and placeholders."""
    if value is None:
        return None
    text = " ".join(str(value).replace("\xa0", " ").split())
    return None if text in PLACEHOLDERS else text


def fold_key(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.upper())
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9]+", "", plain)


def org_key(name: str) -> str:

    stripped = name
    while True:
        shorter = LEGAL_SUFFIX_RE.sub("", stripped).strip()
        if shorter == stripped or not shorter:
            break
        stripped = shorter

    key = fold_key(stripped)
    return ORG_ALIASES.get(key, key)


def rank_variant(item: tuple[str, int]) -> tuple[int, int, str]:

    name, count = item
    return (-count, -len(name), name)


def group_organizations(names: Counter) -> dict[str, list[str]]:
    """Canonical name -> raw variants; the most frequent variant wins."""
    groups: dict[str, Counter] = defaultdict(Counter)
    for name, count in names.items():
        groups[org_key(name)][name] += count

    canonical: dict[str, list[str]] = {}
    for variants in groups.values():
        ranked = sorted(variants.items(), key=rank_variant)
        canonical[ranked[0][0]] = sorted(variants)

    return canonical


def has_accent(value: str) -> bool:

    return any(ord(c) > 127 for c in value)


def spelling_rank(item: tuple[str, int]) -> tuple[int, int, str]:

    name, count = item
    return (0 if has_accent(name) else 1, -count, name)


def preferred_spelling(variants: Counter) -> str:
    """Accented spelling first, then the most wells."""
    ranked = sorted(variants.items(), key=spelling_rank)
    return ranked[0][0]


def propose(pairs: Counter) -> dict[tuple[str, str], tuple[str, str]]:
    """(department, municipality) -> proposed canonical pair."""
    departments: dict[str, Counter] = defaultdict(Counter)
    municipalities: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for (department, municipality), wells in pairs.items():
        base = PARENTHESIS_RE.sub("", municipality) or municipality
        departments[fold_key(department)][department] += wells
        key = (fold_key(department), fold_key(base))
        municipalities[key][base] += wells

    proposals = {}
    for (department, municipality) in pairs:
        base = PARENTHESIS_RE.sub("", municipality) or municipality
        dept = preferred_spelling(departments[fold_key(department)])
        key = (fold_key(department), fold_key(base))
        proposals[(department, municipality)] = (
            dept, preferred_spelling(municipalities[key]))

    return proposals


def read_review(path: Path) -> dict[tuple[str, str], dict]:

    if not path.exists():
        return {}

    rows = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            row["reviewed"] = row["reviewed"].strip().lower() == "true"
            rows[(row["department"], row["municipality"])] = row

    return rows


def merge_review(pairs: Counter,
                 path: Path
                 ) -> tuple[list[dict], bool]:
    """Owner-reviewed rows are kept; new pairs get proposals, unreviewed."""
    existing = read_review(path)
    proposals = propose(pairs)
    rows, changed = [], not path.exists()

    for pair in sorted(pairs):
        row = existing.get(pair)
        if row is None:
            department, municipality = proposals[pair]
            row = {
                "department": pair[0],
                "municipality": pair[1],
                "canonical_department": department,
                "canonical_municipality": municipality,
                "reviewed": False,
            }
            changed = True
        row["wells"] = pairs[pair]
        rows.append(row)

    return rows, changed


def write_review(rows: list[dict], path: Path) -> None:

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        for row in rows:
            out = {key: row[key] for key in REVIEW_FIELDS}
            out["reviewed"] = "true" if row["reviewed"] else "false"
            writer.writerow(out)
