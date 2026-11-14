"""HTTP retries, backoff and cache, with a fake opener (no network)."""

import io
import json
import urllib.error

import pytest

from settlemark.config import HttpConfig
from settlemark.http import FetchError, get_json

CFG = HttpConfig(
    timeout_seconds=1, retries=3, backoff_seconds=1, cache_ttl_hours=1, user_agent="t", pause_between_coingecko_calls_seconds=0
)


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_retries_then_succeeds_with_exponential_backoff():
    calls, waits = [], []

    def opener(req, timeout):
        calls.append(req.full_url)
        if len(calls) < 3:
            raise urllib.error.URLError("down")
        return Resp(json.dumps({"ok": 1}).encode())

    assert get_json("https://a.test", CFG, opener=opener, sleep=waits.append) == {"ok": 1}
    assert len(calls) == 3 and waits == [1, 2]


def test_gives_up_after_retries():
    def opener(req, timeout):
        raise TimeoutError()

    with pytest.raises(FetchError, match="after 3 attempts"):
        get_json("https://a.test", CFG, opener=opener, sleep=lambda s: None)


def test_client_error_is_not_retried():
    calls = []

    def opener(req, timeout):
        calls.append(1)
        raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, None)

    with pytest.raises(FetchError, match="404"):
        get_json("https://a.test", CFG, opener=opener, sleep=lambda s: None)
    assert len(calls) == 1


def test_cache_serves_second_call(tmp_path):
    calls = []

    def opener(req, timeout):
        calls.append(1)
        return Resp(b'{"v": 2}')

    assert get_json("https://a.test/x", CFG, tmp_path, opener=opener) == {"v": 2}
    assert get_json("https://a.test/x", CFG, tmp_path, opener=opener) == {"v": 2}
    assert len(calls) == 1
    get_json("https://a.test/x", CFG, tmp_path, use_cache=False, opener=opener)
    assert len(calls) == 2
