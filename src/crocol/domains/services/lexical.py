import re
import unicodedata

STOPWORDS_ES = {
    "a", "al", "algo", "algunas", "algunos", "ante", "antes", "como", "con",
    "contra", "cual", "cuales", "cuando", "de", "del", "desde", "donde",
    "dos", "durante", "e", "el", "ella", "ellas", "ellos", "en", "entre",
    "era", "eran", "es", "esa", "esas", "ese", "eso", "esos", "esta",
    "estas", "este", "esto", "estos", "fue", "fueron", "ha", "han", "hasta",
    "hay", "la", "las", "le", "les", "lo", "los", "mas", "mismo", "muy",
    "ni", "no", "nos", "o", "otra", "otras", "otro", "otros", "para",
    "pero", "por", "porque", "que", "quien", "se", "segun", "ser", "si",
    "sin", "sobre", "son", "su", "sus", "tambien", "tiene", "tienen",
    "toda", "todas", "todo", "todos", "u", "un", "una", "unas", "uno",
    "unos", "y", "ya",
}
STOPWORDS_EN = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "for",
    "from", "has", "have", "in", "into", "is", "it", "its", "of", "on",
    "or", "that", "the", "their", "these", "this", "to", "was", "were",
    "which", "with",
}
STOPWORDS = sorted(STOPWORDS_ES | STOPWORDS_EN)

CODE_RE = re.compile(r"\b[a-z0-9]+(?:[.\-/_][a-z0-9]+)+\b")
CODE_SEPARATORS = re.compile(r"[.\-/]")
WORD_RE = re.compile(r"\w+")
SPACE_RE = re.compile(r"\s+")


def fold(text: str) -> str:
    
    decomposed = unicodedata.normalize("NFKD", text)
    kept = [c for c in decomposed if not unicodedata.combining(c)]
    
    return "".join(kept).lower()


def is_stopword(word: str) -> bool:
    return word in STOPWORDS_ES or word in STOPWORDS_EN


def normalize_lexical(text: str) -> str:
    """Accent-folded, stopword-free tokens plus joined codes such as vmm_53."""
    folded = fold(text)
    codes = []
    for match in CODE_RE.finditer(folded):
        
        codes.append(CODE_SEPARATORS.sub("_", match.group()))
        
    words = [w for w in WORD_RE.findall(folded) if not is_stopword(w)]
    
    return SPACE_RE.sub(" ", " ".join(words + codes)).strip()
