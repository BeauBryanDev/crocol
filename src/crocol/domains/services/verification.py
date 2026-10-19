import re
from collections.abc import Iterable

from crocol.domains.services.citations import LABEL_GROUP_RE, cited_labels

NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")
SMALL_INTEGER = 10
PRECISION = 6


def decimal_reading(token: str, 
                    separator: str
                    ) -> float:
    
    whole, _, fraction = token.rpartition(separator)
    whole = whole.replace(".", "").replace(",", "")
    
    return float(f"{whole}.{fraction}")


def readings(token: str) -> set[float]:
    """Every value a number token can mean under ES or EN separators."""
    plain = token.replace(".", "").replace(",", "")
    has_dot = "." in token
    has_comma = "," in token
    
    if not has_dot and not has_comma:
        
        return {float(plain)}

    if has_dot and has_comma:
        
        last = "." if token.rfind(".") > token.rfind(",") else ","
        
        return {round(decimal_reading(token, last), PRECISION)}

    separator = "." if has_dot else ","
    groups = token.split(separator)
    values = set()
    thousands = all(len(g) == 3 for g in groups[1:])
    
    if thousands:
        values.add(float(plain))
        
    if len(groups) == 2:
        values.add(round(decimal_reading(token, separator), PRECISION))
        
    return values


def number_tokens(text: str) -> list[str]:
    
    without_labels = LABEL_GROUP_RE.sub(" ", text)
    
    return NUMBER_RE.findall(without_labels)


def is_trivial(token: str) -> bool:
    
    return token.isdigit() and int(token) <= SMALL_INTEGER


def evidence_values(texts: Iterable[str]) -> set[float]:
    
    values: set[float] = set()
    
    for text in texts:
        for token in number_tokens(text):
            values.update(readings(token))
            
    return values


def unsupported_numbers(answer: str,
                        evidence: Iterable[str]
                        ) -> list[str]:
    """Numbers in the answer that no evidence text contains, in any reading."""
    texts = list(evidence)
    known = evidence_values(texts)
    literal = set()
    
    for text in texts:
        literal.update(number_tokens(text))
        
    missing = []
    for token in number_tokens(answer):

        if is_trivial(token) or token in missing or token in literal:
            continue
        
        if not readings(token) & known:
            missing.append(token)
            
    return missing


def unknown_labels(answer: str, 
                   labels: Iterable[str]
                   ) -> list[str]:
    
    allowed = set(labels)
    
    return [label for label in cited_labels(answer) if label not in allowed]
