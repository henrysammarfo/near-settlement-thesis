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


def test_fonts_are_inlined_so_file_urls_do_not_hit_cors():
    page = (ROOT / "site" / "index.html").read_text()
    assert "brand/fonts/inter.woff2" not in page and page.count("data:font/woff2;base64,") == 2


def test_noise_band_claims_match_the_data():
    import json

    L = json.loads((ROOT / "results" / "results.json").read_text())["leadlag"]
    bars = [(k, r) for t in L["tests"] if "xcorr" in t for k, r in zip(t["xcorr_lags"], t["xcorr"]) if k > 0]
    assert L["lead_bars"] == len(bars)
    assert len(L["lead_bars_outside"]) == sum(abs(r) > L["band"] for _, r in bars)
    page = (ROOT / "site" / "index.html").read_text()
    assert "all inside the noise band" not in page
    assert f"{len(L['lead_bars_outside'])} of {L['lead_bars']}" in page
