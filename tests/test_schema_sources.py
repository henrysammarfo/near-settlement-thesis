"""Schema validation and source parsers."""

import pytest

from settlemark.schema import Column, Schema, SchemaError, validate
from settlemark.sources import BY_NAME, parse_coingecko, parse_llama_chart, read_csv, to_day, write_csv

S = Schema("t", (Column("date", "date"), Column("usd", "number", min=0)), min_rows=2)
H = S.header


def row(d, v, url="https://x.test/a", ts="2026-11-14T00:00:00Z"):
    return {"date": d, "usd": v, "fetched_at_utc": ts, "source_url": url}


def test_valid_rows_pass():
    validate(S, H, [row("2026-01-01", "1"), row("2026-01-02", "2.5")])


@pytest.mark.parametrize(
    "rows,msg",
    [
        ([row("2026-01-02", "1"), row("2026-01-01", "1")], "increasing"),
        ([row("2026-01-01", "1"), row("2026-01-01", "1")], "increasing"),
        ([row("2026-01-01", "1"), row("2026-01-02", "-1")], "below minimum"),
        ([row("2026-01-01", "1"), row("2026-01-02", "abc")], "not a number"),
        ([row("2026-01-01", "1"), row("2026-01-02", "nan")], "not finite"),
        ([row("2026-01-01", "1"), row("2026/01/02", "1")], "YYYY-MM-DD"),
        ([row("2026-01-01", "1"), row("2026-01-02", "1", url="http://x")], "https"),
        ([row("2026-01-01", "1"), row("2026-01-02", "1", ts="yesterday")], "ISO UTC"),
        ([row("2026-01-01", "1")], "at least"),
    ],
)
def test_invalid_rows_fail(rows, msg):
    with pytest.raises(SchemaError, match=msg):
        validate(S, H, rows)


def test_header_mismatch_fails():
    with pytest.raises(SchemaError, match="header"):
        validate(S, ["date", "usd"], [row("2026-01-01", "1"), row("2026-01-02", "1")])


def test_to_day_handles_seconds_and_milliseconds():
    assert to_day(1763164800) == to_day(1763164800000) == "2025-11-15"


def test_parsers_dedupe_and_sort_last_value_wins():
    d = {"totalDataChart": [[1763251200, 5], [1763164800, 1], [1763251200, 7]]}
    assert parse_llama_chart(d) == [("2025-11-15", 1), ("2025-11-16", 7)]
    g = {"prices": [[1763164800000, 2.0], [1763200000000, 2.5]]}
    assert parse_coingecko(g) == [("2025-11-15", 2.5)]


def test_write_then_read_round_trip(tmp_path):
    ds = BY_NAME["near_price"]
    rows = (
        [(f"2026-01-{i:02d}", float(i)) for i in range(1, 29)]
        + [(f"2026-02-{i:02d}", float(i)) for i in range(1, 28)]
        + [(f"2026-03-{i:02d}", float(i)) for i in range(1, 31)]
        + [(f"2026-04-{i:02d}", float(i)) for i in range(1, 30)]
    )
    write_csv(ds, rows, "https://api.example.test/p", "2026-11-14T00:00:00Z", tmp_path)
    back = read_csv(ds, tmp_path)
    assert len(back) == len(rows) and back[0]["source_url"] == "https://api.example.test/p"


def test_write_refuses_invalid_data_and_leaves_no_file(tmp_path):
    ds = BY_NAME["near_price"]
    with pytest.raises(SchemaError):
        write_csv(ds, [("2026-01-01", -1.0)] * 200, "https://x.test", "2026-11-14T00:00:00Z", tmp_path)
    assert not ds.path(tmp_path).exists()
