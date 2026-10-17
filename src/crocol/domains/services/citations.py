import re
from collections.abc import Iterable, Mapping

LABEL_GROUP_RE = re.compile(r"\[(C\d+(?:\s*,\s*C\d+)*)\]")
LABEL_RE = re.compile(r"C\d+")


def page_span(start: int, end: int) -> str:
    
    if start <= 0:
        return ""
    
    if end <= start:
        return f"p. {start}"
    
    return f"pp. {start}-{end}"


def render_citation(citation: str,
                    start: int,
                    end: int
                    ) -> str:
    """One parenthetical citation such as (Rueda Acevedo, 2016, p. 41)."""
    pages = page_span(start, end)
    
    return f"({citation}, {pages})" if pages else f"({citation})"


def cited_labels(text: str) -> list[str]:
    labels: list[str] = []
    
    for group in LABEL_GROUP_RE.finditer(text):
        
        for label in LABEL_RE.findall(group.group(1)):
            
            if label not in labels:
                labels.append(label)
                
    return labels


def normalize_labels(items: Iterable[str]) -> list[str]:
    """Accept C2, [C2], c2 or "C2, C5" from a model; return ['C2', ...]."""
    labels: list[str] = []

    for item in items:
        for label in LABEL_RE.findall(str(item).upper()):

            if label not in labels:
                labels.append(label)

    return labels


def inner(rendered: str) -> str:
    
    return rendered[1:-1] if rendered.startswith("(") else rendered


def replace_labels(text: str,
                   rendered: Mapping[str, str]
                   ) -> str:
    """Swap [C1] or [C1, C3] markers for citations; unknown labels vanish."""

    def substitute(match: re.Match) -> str:
        parts = []
        
        for label in LABEL_RE.findall(match.group(1)):
            
            if label in rendered:
                parts.append(inner(rendered[label]))
                
        return f"({'; '.join(parts)})" if parts else ""

    replaced = LABEL_GROUP_RE.sub(substitute, text)
    
    return re.sub(r"[ \t]+([.,;:])", r"\1", replaced)


def reference_list(references: Iterable[str]) -> list[str]:
    
    unique = {ref.strip() for ref in references if ref and ref.strip()}
    
    return sorted(unique, key=str.casefold)
