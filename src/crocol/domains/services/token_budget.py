import math

CHARS_PER_TOKEN = 3.6


def estimate(text: str) -> int:
    """Approximate tokens of mostly Spanish text; no tokenizer call."""
    return math.ceil(len(text) / CHARS_PER_TOKEN) if text else 0


def fit_text(text: str, budget: int) -> str:
    """Text cut at a word boundary so it fits the token budget."""
    if estimate(text) <= budget:
        return text

    limit = max(int(budget * CHARS_PER_TOKEN) - 1, 0)
    cut = text[:limit].rsplit(" ", 1)[0].rstrip()
    return f"{cut}…" if cut else ""


def fit_count(sizes: list[int], budget: int, keep_min: int) -> int:
    """How many leading items fit the budget, never fewer than keep_min."""
    used = 0
    count = 0
    for size in sizes:
        if used + size > budget and count >= keep_min:
            break
        used += size
        count += 1

    return count
