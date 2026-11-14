"""Small, tested statistics used by the analysis. Pure functions, no I/O."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

ArrayLike = Sequence[float] | np.ndarray | pd.Series


class StatsError(ValueError):
    """Raised when a statistic is undefined for the given input."""


def _arrays(a: ArrayLike, b: ArrayLike, min_n: int = 3) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(a, dtype=float)
    y = np.asarray(b, dtype=float)
    if x.shape != y.shape or x.ndim != 1:
        raise StatsError(f"inputs must be 1D and the same length, got {x.shape} and {y.shape}")
    if len(x) < min_n:
        raise StatsError(f"need at least {min_n} paired values, got {len(x)}")
    if not (np.isfinite(x).all() and np.isfinite(y).all()):
        raise StatsError("inputs contain NaN or infinite values")
    return x, y


def pearson(a: ArrayLike, b: ArrayLike) -> float:
    """Pearson correlation. Raises if either series is constant (correlation undefined)."""
    x, y = _arrays(a, b)
    if np.std(x) == 0 or np.std(y) == 0:
        raise StatsError("correlation is undefined for a constant series")
    return float(np.corrcoef(x, y)[0, 1])


def bootstrap_corr_ci(a: ArrayLike, b: ArrayLike, resamples: int = 2000, seed: int = 7, level: float = 0.90) -> tuple[float, float]:
    """Percentile bootstrap interval for the Pearson correlation of paired data.

    Pairs are resampled together with replacement. Resamples where one side is constant
    (correlation undefined) are skipped. Deterministic for a given seed.
    """
    x, y = _arrays(a, b)
    if not 0 < level < 1:
        raise StatsError("level must be between 0 and 1")
    rng = np.random.default_rng(seed)
    n = len(x)
    out = np.empty(resamples)
    for k in range(resamples):
        i = rng.integers(0, n, n)
        xi, yi = x[i], y[i]
        out[k] = np.nan if (xi.std() == 0 or yi.std() == 0) else np.corrcoef(xi, yi)[0, 1]
    out = out[np.isfinite(out)]
    if len(out) < resamples // 2:
        raise StatsError("too many degenerate bootstrap resamples")
    tail = (1 - level) / 2 * 100
    return float(np.percentile(out, tail)), float(np.percentile(out, 100 - tail))


def lagged_corr(leader: ArrayLike, follower: ArrayLike, lag: int = 1) -> float:
    """Correlation of `leader` at time t with `follower` at time t + lag."""
    x, y = _arrays(leader, follower, min_n=lag + 3)
    if lag < 1:
        raise StatsError("lag must be at least 1")
    return pearson(x[:-lag], y[lag:])


def log_changes(df: pd.DataFrame) -> pd.DataFrame:
    """Period over period log changes. Rejects non positive values instead of hiding them."""
    if (df <= 0).any().any():
        bad = [c for c in df.columns if (df[c] <= 0).any()]
        raise StatsError(f"log changes need positive values; non positive in {bad}")
    return np.log(df).diff().dropna()


def weekly(df: pd.DataFrame, agg: dict[str, str], rule: str = "W-SUN") -> pd.DataFrame:
    """Resample daily data to weeks and drop the first and last weeks, which may be partial."""
    if not isinstance(df.index, pd.DatetimeIndex):
        raise StatsError("weekly() needs a DatetimeIndex")
    w = df.resample(rule).agg(agg)
    if len(w) < 3:
        raise StatsError("need at least three weeks of data")
    return w.iloc[1:-1]
