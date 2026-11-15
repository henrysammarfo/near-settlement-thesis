"""The browser tester (templates/model.js) must give the same numbers as the Python model."""

import json
import shutil
import subprocess

import pytest

from settlemark.config import ROOT

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run_node(script: str) -> dict:
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, cwd=ROOT)
    return json.loads(out.stdout)


def test_js_defaults_reproduce_python_base_case():
    R = json.loads((ROOT / "results" / "results.json").read_text())
    V = R["valuation"]
    js = run_node(
        "const M=require('./templates/model.js');const V=require('./results/results.json').valuation;"
        "const o=M.run(M.defaults(V),V);"
        "const s=V.sensitivity.map(g=>({r:g.r,bear:M.dcf(V.holder_cash_flow_usd,V.growth_bear_pct/100,g.r,V.terminal_growth_pct/100,V.explicit_years,V.fade_years)/V.supply_near}));"
        "console.log(JSON.stringify({o,s}))"
    )
    o = js["o"]
    assert o["value_per_token"] == pytest.approx(V["value_per_token_base"], rel=1e-9)
    assert o["buyback_usd"] == pytest.approx(V["holder_cash_flow_usd"], rel=1e-9)
    assert o["breakeven_weekly_volume"] == pytest.approx(V["breakeven_weekly_volume_usd"], rel=1e-9)
    for a, b in zip(js["s"], V["sensitivity"], strict=True):
        assert a["bear"] == pytest.approx(b["bear"], rel=1e-9)
