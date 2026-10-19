from statistics import fmean, pstdev

from crocol.domains.models.productions import Trend

# Over the whole period, a fitted change within +/-5 % is "stable"; residual
# scatter above 20 % of the mean is "variable" whatever the slope.
STABLE_BAND_PCT = 5.0
VARIABLE_SCATTER_PCT = 20.0
MIN_MONTHS = 3


def classify(values: list[float | None]) -> Trend:
    """Trend of monthly averages from a least-squares line and its scatter."""
    points = [(i, v) for i, v in enumerate(values) if v is not None]
    
    if len(points) < MIN_MONTHS:
        
        return Trend("insufficient_data", len(points))

    xs = [float(i) for i, _ in points]
    ys = [float(v) for _, v in points]
    mean = fmean(ys)
    if mean <= 0:
        return Trend("no_production",
                     len(points), ys[0], ys[-1], 0.0)

    x_mean = fmean(xs)
    sxx = sum((x - x_mean) ** 2 for x in xs)
    slope = sum((x - x_mean) * (y - mean) for x, y in zip(xs, ys)) / sxx
    intercept = mean - slope * x_mean
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]

    span = xs[-1] - xs[0]
    change_pct = 100.0 * slope * span / mean
    scatter_pct = 100.0 * pstdev(residuals) / mean
    
    if scatter_pct > VARIABLE_SCATTER_PCT:
        label = "variable"
        
    elif change_pct <= -STABLE_BAND_PCT:
        label = "decreasing"
        
    elif change_pct >= STABLE_BAND_PCT:
        label = "increasing"
        
    else:
        label = "stable"

    return Trend(label, len(points),
                 round(ys[0], 3),
                 round(ys[-1], 3),
                 round(mean, 3),
                 round(change_pct, 2),
                 round(100.0 * slope / mean, 3), 
                 round(scatter_pct, 2))
