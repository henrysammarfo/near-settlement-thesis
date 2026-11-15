"""The page works opened straight from disk: its data is inlined, with fetch only as a fallback."""

import json
import re

from settlemark.config import ROOT


def _inline(html, el_id):
    m = re.search(rf'<script type="application/json" id="{el_id}">(.*?)</script>', html, re.S)
    assert m, el_id
    return json.loads(m.group(1))


def test_index_inlines_the_same_data_the_server_would_send():
    html = (ROOT / "site" / "index.html").read_text()
    assert _inline(html, "data-json") == json.loads((ROOT / "site" / "data.json").read_text())
    assert _inline(html, "results-json") == json.loads((ROOT / "site" / "results.json").read_text())


def test_app_reads_inline_first():
    js = (ROOT / "site" / "app.js").read_text()
    assert "function loadJSON" in js
    assert 'fetch("data.json")' not in js and 'fetch("results.json")' not in js
    assert 'loadJSON("data-json", "data.json")' in js and 'loadJSON("results-json", "results.json")' in js


def test_new_sections_and_charts_are_on_the_page():
    html = (ROOT / "site" / "index.html").read_text()
    for needle in ('id="lead"', 'id="routers"', "10_lead_lag-light.svg", "11_router_take_rates-light.svg", "testnet.nearblocks.io/txns/"):
        assert needle in html, needle
