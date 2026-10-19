import re
from collections import Counter

from crocol.domains.services.citations import LABEL_GROUP_RE, LABEL_RE

MAX_LABELS = 2 # Only two citations per paragraph
BLOCK_SPLIT_RE = re.compile(r"(\n[ \t]*\n)")
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
HEADING_RE = re.compile(r"^\s*#{1,6}\s")
SPACE_BEFORE_PUNCT_RE = re.compile(r"[ \t]+([.,;:!?])")
INNER_SPACES_RE = re.compile(r"(?<=\S)[ \t]{2,}")
END_PUNCT = ".!?"
VERBATIM_PREFIXES = ("|", "```")


def labels_in(text: str) -> list[str]:
    """Every label in order, repeats included."""
    found = []
    for group in LABEL_GROUP_RE.finditer(text):
        found.extend(LABEL_RE.findall(group.group(1)))
    return found


def choose(labels: list[str]) -> list[str]:
    """At most MAX_LABELS sources: most used first, then first seen."""
    distinct = list(dict.fromkeys(labels))
    if len(distinct) <= MAX_LABELS:
        return distinct

    counts = Counter(labels)
    first = {label: distinct.index(label) for label in distinct}

    def rank(label: str) -> tuple[int, int]:
        return -counts[label], first[label]

    top = set(sorted(distinct, key=rank)[:MAX_LABELS])
    return [label for label in distinct if label in top]


def strip_labels(text: str) -> str:
    text = LABEL_GROUP_RE.sub("", text)
    text = SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    text = INNER_SPACES_RE.sub(" ", text)
    return "\n".join(line.rstrip() for line in text.split("\n"))


def place(text: str, labels: list[str]) -> str:
    """One label group at the end, before a final full stop if present."""
    if not labels:
        return text
    group = f"[{', '.join(labels)}]"
    body = text.rstrip()
    if body and body[-1] in END_PUNCT:
        return f"{body[:-1]} {group}{body[-1]}"
    return f"{body} {group}"


def cap_unit(text: str) -> str:
    labels = labels_in(text)
    if not labels:
        return text
    return place(strip_labels(text), choose(labels))


def units_of(block: str) -> list[tuple[str, list[str]]]:
    """Headings, list items (with continuation lines) and prose runs."""
    units: list[tuple[str, list[str]]] = []
    for line in block.split("\n"):
        if HEADING_RE.match(line):
            units.append(("heading", [line]))
        elif LIST_ITEM_RE.match(line):
            units.append(("item", [line]))
        elif units and units[-1][0] != "heading":
            units[-1][1].append(line)
        else:
            units.append(("prose", [line]))
    return units


def collapse_shared(texts: list[str], items: list[int]) -> None:
    """Bullets citing the same sources are cited once, on the last one."""
    sets = []
    for i in items:
        labels = labels_in(texts[i])
        if labels:
            sets.append(tuple(labels))
    if len(sets) < 2 or len(set(sets)) != 1:
        return
    for i in items:
        texts[i] = strip_labels(texts[i])
    texts[items[-1]] = place(texts[items[-1]], list(sets[0]))


def cap_block(block: str) -> str:
    lines = block.lstrip("\n").split("\n")
    if any(line.lstrip().startswith(VERBATIM_PREFIXES) for line in lines):
        return block

    units = units_of(block)
    texts = []
    for kind, unit_lines in units:
        text = "\n".join(unit_lines)
        texts.append(text if kind == "heading" else cap_unit(text))

    items = [i for i, (kind, _) in enumerate(units) if kind == "item"]
    collapse_shared(texts, items)
    return "\n".join(texts)


def cap_citations(text: str) -> str:
    """At most two sources per paragraph, cited once at its end."""
    parts = BLOCK_SPLIT_RE.split(text)
    out = []
    for index, part in enumerate(parts):
        out.append(part if index % 2 else cap_block(part))
    return "".join(out)
