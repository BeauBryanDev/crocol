RRF_K = 60


def rrf_merge(
    lists: list[list[dict]],
    weights: list[float],
    k: int = RRF_K,
    limit: int | None = None,
) -> list[dict]:
    """Weighted reciprocal rank fusion of rows keyed by "id", best first."""
    if len(lists) != len(weights):
        raise ValueError("lists and weights must have the same length")

    scores: dict[str, float] = {}
    rows: dict[str, dict] = {}
    for ranked, weight in zip(lists, weights):
        for rank, row in enumerate(ranked):
            gain = weight / (k + rank + 1)
            scores[row["id"]] = scores.get(row["id"], 0.0) + gain
            rows.setdefault(row["id"], row)

    ordered = sorted(scores,
                     key=scores.get,
                     reverse=True)
    
    if limit is not None:
        ordered = ordered[:limit]

    fused = []
    for row_id in ordered:
        fused.append({**rows[row_id], "fused_score": scores[row_id]})
        
    return fused
