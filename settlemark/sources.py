"""Declared datasets: where each one comes from, how its JSON is parsed, and its schema."""

from __future__ import annotations

import csv
import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .schema import Column, Schema, validate

Row = tuple[Any, ...]


def to_day(ts: float | int | str) -> str:
    """Unix seconds or milliseconds to a UTC YYYY-MM-DD string."""
    t = float(ts)
    if t > 1e11:
        t /= 1000
    return dt.datetime.fromtimestamp(t, dt.UTC).strftime("%Y-%m-%d")


def _dedupe(pairs: list[Row]) -> list[Row]:
    """Keep the last row for each date and sort by date (sources sometimes repeat today)."""
    out: dict[str, Row] = {}
    for r in pairs:
        out[r[0]] = r
    return [out[k] for k in sorted(out)]


def parse_llama_chart(d: Any) -> list[Row]:
    return _dedupe([(to_day(ts), v) for ts, v in d["totalDataChart"]])


def parse_stablecoins(d: Any) -> list[Row]:
    return _dedupe([(to_day(x["date"]), x["totalCirculatingUSD"].get("peggedUSD", 0)) for x in d])


def parse_tvl(d: Any) -> list[Row]:
    return _dedupe([(to_day(x["date"]), x["tvl"]) for x in d])


def parse_nearblocks(d: Any) -> list[Row]:
    return _dedupe(
        [
            (x["date"][:10], x["txns"], x["active_accounts"], x["new_accounts"], x["txn_fee_usd"], x["near_price"], x["market_cap"])
            for x in d["charts"]
        ]
    )


def parse_coingecko(d: Any) -> list[Row]:
    return _dedupe([(to_day(ts), v) for ts, v in d["prices"]])


USD = (Column("date", "date"), Column("usd", "number", min=0))


@dataclass(frozen=True)
class Dataset:
    name: str
    parse: Callable[[Any], list[Row]]
    schema: Schema
    provider: str

    def path(self, data_dir: Path) -> Path:
        return data_dir / f"{self.name}.csv"


DATASETS: tuple[Dataset, ...] = (
    Dataset("intents_volume", parse_llama_chart, Schema("intents_volume", USD, 100), "DefiLlama"),
    Dataset("intents_fees", parse_llama_chart, Schema("intents_fees", USD, 100), "DefiLlama"),
    Dataset("intents_revenue", parse_llama_chart, Schema("intents_revenue", USD, 100), "DefiLlama"),
    Dataset("all_dex_volume", parse_llama_chart, Schema("all_dex_volume", USD, 100), "DefiLlama"),
    Dataset("near_stablecoins", parse_stablecoins, Schema("near_stablecoins", USD, 100), "DefiLlama"),
    Dataset("near_tvl", parse_tvl, Schema("near_tvl", USD, 100), "DefiLlama"),
    Dataset(
        "near_chain",
        parse_nearblocks,
        Schema(
            "near_chain",
            (
                Column("date", "date"),
                Column("txns", "int", min=0),
                Column("active_accounts", "int", min=0),
                Column("new_accounts", "int", min=0),
                Column("txn_fee_usd", "number", min=0),
                Column("near_price_usd", "number", min=0),
                Column("market_cap_usd", "number", min=0),
            ),
            100,
        ),
        "NearBlocks",
    ),
    Dataset("near_price", parse_coingecko, Schema("near_price", USD, 100), "CoinGecko"),
    Dataset("btc_price", parse_coingecko, Schema("btc_price", USD, 100), "CoinGecko"),
)
BY_NAME = {d.name: d for d in DATASETS}


def write_csv(ds: Dataset, rows: list[Row], url: str, fetched_at: str, data_dir: Path) -> Path:
    """Validate then atomically write a dataset with provenance on every row."""
    str_rows = [dict(zip(ds.schema.header, [str(v) for v in r] + [fetched_at, url], strict=True)) for r in rows]
    validate(ds.schema, ds.schema.header, str_rows)
    path = ds.path(data_dir)
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(ds.schema.header)
        for r in rows:
            w.writerow([*r, fetched_at, url])
    tmp.replace(path)
    return path


def read_csv(ds: Dataset, data_dir: Path) -> list[dict[str, str]]:
    """Read and validate a dataset CSV."""
    with ds.path(data_dir).open(newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        validate(ds.schema, reader.fieldnames or [], rows)
    return rows
