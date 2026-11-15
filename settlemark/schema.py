"""Schema validation for every dataset, applied after fetching and again before analysis.

A dataset fails loudly if a column is missing, a value is not numeric, a value breaks a
bound, dates are not ISO, sorted and unique, or a row lacks its source URL and fetch time.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
PROVENANCE = ("fetched_at_utc", "source_url")


class SchemaError(ValueError):
    """Raised when a dataset does not match its declared schema."""


@dataclass(frozen=True)
class Column:
    name: str
    kind: Literal["date", "number", "int", "str"]
    min: float | None = None


@dataclass(frozen=True)
class Schema:
    name: str
    columns: tuple[Column, ...]
    min_rows: int = 30

    @property
    def header(self) -> list[str]:
        return [c.name for c in self.columns] + list(PROVENANCE)


def validate(schema: Schema, header: Sequence[str], rows: Sequence[dict[str, str]]) -> None:
    """Validate rows read from CSV (all values are strings)."""
    if list(header) != schema.header:
        raise SchemaError(f"{schema.name}: header {list(header)} != expected {schema.header}")
    if len(rows) < schema.min_rows:
        raise SchemaError(f"{schema.name}: {len(rows)} rows, expected at least {schema.min_rows}")
    prev = ""
    for i, r in enumerate(rows, start=2):  # line 1 is the header
        where = f"{schema.name} line {i}"
        if not r["source_url"].startswith(("https://", "bigquery-public-data.")):
            raise SchemaError(f"{where}: source_url must be an https URL, got {r['source_url']!r}")
        if not TS_RE.match(r["fetched_at_utc"]):
            raise SchemaError(f"{where}: fetched_at_utc must be ISO UTC, got {r['fetched_at_utc']!r}")
        for c in schema.columns:
            v = r[c.name]
            if c.kind == "date":
                if not DATE_RE.match(v):
                    raise SchemaError(f"{where}: {c.name} is not YYYY-MM-DD: {v!r}")
                if v <= prev:
                    raise SchemaError(f"{where}: dates must be strictly increasing ({prev} then {v})")
                prev = v
                continue
            if c.kind == "str":
                if not v:
                    raise SchemaError(f"{where}: {c.name} is empty")
                continue
            try:
                x = float(v)
            except ValueError as e:
                raise SchemaError(f"{where}: {c.name} is not a number: {v!r}") from e
            if x != x or x in (float("inf"), float("-inf")):
                raise SchemaError(f"{where}: {c.name} is not finite")
            if c.kind == "int" and not x.is_integer():
                raise SchemaError(f"{where}: {c.name} must be an integer: {v!r}")
            if c.min is not None and x < c.min:
                raise SchemaError(f"{where}: {c.name}={x} below minimum {c.min}")
