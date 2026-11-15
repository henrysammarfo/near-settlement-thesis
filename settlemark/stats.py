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


def days(n: int) -> np.timedelta64:
    """A whole number of days with an explicit unit.

    `pd.Timedelta(days=n)` triggers NumPy's deprecated 'generic' timedelta unit on some
    pandas 2.x and NumPy 2.5 combinations; an explicit `timedelta64[D]` never does.
    """
    return np.timedelta64(int(n), "D")


# Lead and lag tests ---------------------------------------------------------------------------


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (modified Lentz method)."""
    tiny, eps = 1e-300, 3e-16
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 500):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            return h
    raise StatsError("incomplete beta did not converge")


def betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b), accurate to about 1e-12 (no SciPy needed)."""
    if not (a > 0 and b > 0):
        raise StatsError("betainc needs a > 0 and b > 0")
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    from math import exp, lgamma, log

    front = exp(lgamma(a + b) - lgamma(a) - lgamma(b) + a * log(x) + b * log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def f_pvalue(f: float, d1: int, d2: int) -> float:
    """Upper tail probability of the F distribution with (d1, d2) degrees of freedom."""
    if f <= 0:
        return 1.0
    return betainc(d2 / 2.0, d1 / 2.0, d2 / (d2 + d1 * f))


def _rss(y: np.ndarray, X: np.ndarray) -> float:
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ beta
    return float(r @ r)


def granger_f(effect: ArrayLike, cause: ArrayLike, lags: int) -> tuple[float, int, int]:
    """F statistic for 'lags of `cause` add nothing to predicting `effect` beyond its own lags'.

    Restricted model: effect_t on a constant and effect_{t-1..t-lags}. Unrestricted adds
    cause_{t-1..t-lags}. Returns (F, numerator df, denominator df).
    """
    y, x = _arrays(effect, cause, min_n=3 * lags + 5)
    if lags < 1:
        raise StatsError("lags must be at least 1")
    n = len(y)
    Y = y[lags:]
    own = np.column_stack([y[lags - k : n - k] for k in range(1, lags + 1)])
    other = np.column_stack([x[lags - k : n - k] for k in range(1, lags + 1)])
    one = np.ones((len(Y), 1))
    rss_r = _rss(Y, np.hstack([one, own]))
    rss_u = _rss(Y, np.hstack([one, own, other]))
    d1, d2 = lags, len(Y) - 2 * lags - 1
    if rss_u <= 0 or d2 < 1:
        raise StatsError("Granger test is degenerate for this input")
    return float(((rss_r - rss_u) / d1) / (rss_u / d2)), d1, d2


def granger(effect: ArrayLike, cause: ArrayLike, lags: int, min_shift: int = 8) -> dict:
    """Granger style test with two p values.

    `p_value` is the textbook F test (assumes well behaved errors). `p_shift` is a
    distribution free check: the F statistic recomputed after rotating `cause` by every
    circular shift of at least `min_shift` weeks, which keeps each series' own
    autocorrelation but breaks any real timing link. It is the share of shifts whose F is at
    least the observed one.
    """
    f, d1, d2 = granger_f(effect, cause, lags)
    x = np.asarray(cause, dtype=float)
    n = len(x)
    shifts = range(min_shift, n - min_shift + 1)
    null = [granger_f(effect, np.roll(x, s), lags)[0] for s in shifts]
    if not null:
        raise StatsError("series too short for the shift test")
    p_shift = (1 + sum(v >= f for v in null)) / (1 + len(null))
    return {"lags": lags, "f": f, "df1": d1, "df2": d2, "p_value": f_pvalue(f, d1, d2), "p_shift": float(p_shift), "shifts": len(null)}


def cross_corr(a: ArrayLike, b: ArrayLike, max_lag: int) -> list[tuple[int, float]]:
    """Correlation of a_t with b_{t+k} for k in -max_lag..max_lag. Positive k means a leads b."""
    x, y = _arrays(a, b, min_n=max_lag + 3)
    out = []
    for k in range(-max_lag, max_lag + 1):
        if k > 0:
            out.append((k, pearson(x[:-k], y[k:])))
        elif k < 0:
            out.append((k, pearson(x[-k:], y[:k])))
        else:
            out.append((0, pearson(x, y)))
    return out
