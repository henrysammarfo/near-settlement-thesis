"""Valuation model: what NEAR is worth on the cash that actually reaches holders.

Holder cash flow is the NEAR the buyback wallet actually accumulated on chain, valued at the
price of the week it arrived, annualised. Nothing is assumed about a fee switch that has not
happened. The same formulas run in the browser (templates/app.js) for the thesis tester, and
a test pins both to the same reference vector.

Model, per year t = 1..N1+N2:
  growth g_t = g1 for t <= N1, then fades linearly from g1 to g_terminal over N2 years
  cash_t = cash_{t-1} * (1 + g_t), cash_0 = today's annualised holder cash flow
  value = sum(cash_t / (1 + r)^t) + terminal / (1 + r)^(N1+N2),
  terminal = cash_{N1+N2} * (1 + g_terminal) / (r - g_terminal)
"""

from __future__ import annotations

from .stats import StatsError


def growth_path(g1: float, g_terminal: float, n1: int, n2: int) -> list[float]:
    out = [g1] * n1
    for k in range(1, n2 + 1):
        out.append(g1 + (g_terminal - g1) * k / n2)
    return out


def dcf(cash0: float, g1: float, r: float, g_terminal: float, n1: int = 5, n2: int = 5) -> float:
    """Present value of a growing holder cash flow, with a fading growth path and a terminal value."""
    if r <= g_terminal:
        raise StatsError("discount rate must exceed terminal growth")
    if n1 < 0 or n2 < 1:
        raise StatsError("need n1 >= 0 and n2 >= 1")
    pv, cash = 0.0, cash0
    path = growth_path(g1, g_terminal, n1, n2)
    for t, g in enumerate(path, start=1):
        cash *= 1 + g
        pv += cash / (1 + r) ** t
    terminal = cash * (1 + g_terminal) / (r - g_terminal)
    return pv + terminal / (1 + r) ** len(path)


def implied_growth(target_value: float, cash0: float, r: float, g_terminal: float, n1: int = 5, n2: int = 5) -> float:
    """The early growth rate g1 at which the DCF equals `target_value` (bisection)."""
    if cash0 <= 0:
        raise StatsError("holder cash flow must be positive to imply a growth rate")
    lo, hi = -0.9, 20.0
    if dcf(cash0, hi, r, g_terminal, n1, n2) < target_value:
        return hi
    for _ in range(200):
        mid = (lo + hi) / 2
        if dcf(cash0, mid, r, g_terminal, n1, n2) < target_value:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def breakeven_weekly_volume(issuance_usd_per_year: float, take_rate: float, buyback_share: float) -> float:
    """Weekly Intents volume at which buybacks would match new supply, at today's price."""
    if take_rate <= 0 or buyback_share <= 0:
        raise StatsError("take rate and buyback share must be positive")
    return issuance_usd_per_year / (52 * take_rate * buyback_share)
