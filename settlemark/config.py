"""Typed access to settlemark.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "settlemark.toml"


@dataclass(frozen=True)
class HttpConfig:
    timeout_seconds: float
    retries: int
    backoff_seconds: float
    cache_ttl_hours: float
    user_agent: str
    pause_between_coingecko_calls_seconds: float


@dataclass(frozen=True)
class AnalysisConfig:
    week_rule: str
    compare_weeks: int
    endpoint_weeks: int
    year_days: int
    bootstrap_resamples: int
    bootstrap_seed: int
    ci_level: float
    lag_weeks: int


@dataclass(frozen=True)
class FalsifierConfig:
    price_corr_max: float
    lag_corr_max: float
    btc_corr_max: float
    mcap_to_revenue_min: float


@dataclass(frozen=True)
class ValuationConfig:
    discount_rate: float
    discount_low: float
    discount_high: float
    terminal_growth: float
    explicit_years: int
    fade_years: int
    bull_growth_cap: float


@dataclass(frozen=True)
class RobustnessConfig:
    rolling_weeks: int


@dataclass(frozen=True)
class Paths:
    root: Path
    data: Path
    cache: Path
    results: Path
    charts: Path
    site: Path
    template: Path
    site_template: Path
    thesis: Path
    bigquery_csv: Path


@dataclass(frozen=True)
class Config:
    project: dict[str, str]
    paths: Paths
    http: HttpConfig
    analysis: AnalysisConfig
    falsifiers: FalsifierConfig
    valuation: ValuationConfig
    robustness: RobustnessConfig
    chain: dict = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)
    raw: dict = field(default_factory=dict)  # every table in settlemark.toml, for the newer modules


class ConfigError(ValueError):
    """Raised when settlemark.toml is missing a key or holds an invalid value."""


def load_config(path: Path = DEFAULT_CONFIG, root: Path | None = None, output_root: Path | None = None) -> Config:
    """Load the config. `output_root` redirects every generated file (used by tests)."""
    try:
        raw = tomllib.loads(Path(path).read_text())
    except FileNotFoundError as e:
        raise ConfigError(f"config file not found: {path}") from e
    base = root or ROOT
    out = output_root or base
    try:
        p = raw["paths"]
        paths = Paths(
            root=base,
            data=base / p["data"],
            cache=out / p["cache"],
            results=out / p["results"],
            charts=out / p["charts"],
            site=out / p["site"],
            template=base / p["template"],
            site_template=base / p["site_template"],
            thesis=out / p["thesis"],
            bigquery_csv=base / p["bigquery_csv"],
        )
        cfg = Config(
            project=dict(raw["project"]),
            paths=paths,
            http=HttpConfig(**raw["http"]),
            analysis=AnalysisConfig(**raw["analysis"]),
            falsifiers=FalsifierConfig(**raw["falsifiers"]),
            valuation=ValuationConfig(**raw["valuation"]),
            robustness=RobustnessConfig(**raw["robustness"]),
            chain=dict(raw["chain"]),
            sources=dict(raw["sources"]),
            raw=raw,
        )
    except (KeyError, TypeError) as e:
        raise ConfigError(f"invalid config {path}: {e}") from e
    a = cfg.analysis
    if not 0 < a.ci_level < 1:
        raise ConfigError("analysis.ci_level must be between 0 and 1")
    if a.bootstrap_resamples < 100:
        raise ConfigError("analysis.bootstrap_resamples must be at least 100")
    if a.compare_weeks < 2 or a.endpoint_weeks < 1 or a.lag_weeks < 1:
        raise ConfigError("analysis window sizes must be positive")
    v = cfg.valuation
    if not v.discount_low < v.discount_rate < v.discount_high:
        raise ConfigError("valuation discount rates must satisfy low < base < high")
    if v.terminal_growth >= v.discount_low:
        raise ConfigError("valuation.terminal_growth must be below every discount rate")
    return cfg
