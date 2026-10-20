import re
from collections.abc import Iterable, Mapping

KG = "KG"
LABEL = r"(?:C\d+|KG)"
LABEL_GROUP_RE = re.compile(rf"\[({LABEL}(?:\s*,\s*{LABEL})*)\]")
LABEL_RE = re.compile(rf"\b{LABEL}\b")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
SUGGESTIONS_RE = re.compile(
    r"^\s*#{1,6}\s*(?:investigaci[oó]n sugerida|suggested further work)\b",
    re.I | re.M)
LABEL_ONLY_RE = re.compile(rf"^\s*\[{LABEL}(?:\s*,\s*{LABEL})*\][.!?]?\s*$")
PARAGRAPH_RE = re.compile(r"\n[ \t]*\n")

# Citation markers
CITATION_RE = re.compile(r"\b(C\d+)\b")

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


def sentences(text: str) -> list[str]:
    """Sentences, with a trailing 'text. [KG]' label kept on its sentence."""
    out: list[str] = []
    for part in SENTENCE_RE.split(text):
        if out and LABEL_ONLY_RE.match(part):
            out[-1] = f"{out[-1]} {part}"
        else:
            out.append(part)
    return out


def without_suggestions(text: str) -> str:
    """The answer before its 'Investigación sugerida' section."""
    found = SUGGESTIONS_RE.search(text)
    return text[:found.start()].rstrip() if found else text

# General only function I do not want my Agent to cited every single time.
# I want to use this function to check if the text is a general only text.
def general_only(text: str) -> bool:
    """Check if the text is a general only text."""
    labels = cited_labels(text)
    return bool(labels) and set(labels) == {KG}
    

def corpus_text(text: str) -> str:
    """Checkable text: no suggestions, no [KG] paragraphs or sentences."""
    kept = []
    for paragraph in PARAGRAPH_RE.split(without_suggestions(text)):
        if general_only(paragraph):
            continue
        for sentence in sentences(paragraph):
            if not general_only(sentence):
                kept.append(sentence)
    return " ".join(part for part in kept if part.strip())


def inner(rendered: str) -> str:
    # Remove outer parentheses from a citation group, if present.
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
