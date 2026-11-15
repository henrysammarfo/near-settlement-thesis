/* Settlemark value capture model. Same formulas as settlemark/valuation.py; tests/test_model_js.py
   runs this file under Node and checks it against the Python numbers in results.json. */
(function (root) {
  function growthPath(g1, gt, n1, n2) {
    const out = [];
    for (let i = 0; i < n1; i++) out.push(g1);
    for (let k = 1; k <= n2; k++) out.push(g1 + ((gt - g1) * k) / n2);
    return out;
  }
  function dcf(cash0, g1, r, gt, n1, n2) {
    if (r <= gt) return NaN;
    let pv = 0, cash = cash0;
    const path = growthPath(g1, gt, n1, n2);
    path.forEach((g, i) => { cash *= 1 + g; pv += cash / Math.pow(1 + r, i + 1); });
    return pv + (cash * (1 + gt)) / (r - gt) / Math.pow(1 + r, path.length);
  }
  /* inputs: weekly volume USD, take rate bps, buyback share %, growth %, discount %.
     V: the "valuation" block of results.json (price, supply, issuance, market cap, terminal growth). */
  function run(x, V) {
    const take = x.take_bps / 1e4, share = x.share_pct / 100;
    const revenue = x.weekly_volume * 52 * take;
    const buyUsd = revenue * share;
    const buyNear = buyUsd / V.near_price;
    const perToken = dcf(buyUsd, x.growth_pct / 100, x.discount_pct / 100, V.terminal_growth_pct / 100, V.explicit_years, V.fade_years) / V.supply_near;
    return {
      revenue_usd: revenue,
      buyback_usd: buyUsd,
      buyback_near: buyNear,
      coverage_pct: (buyNear / V.issuance_52w_near) * 100,
      net_supply_pct: ((V.issuance_52w_near - buyNear) / V.supply_near) * 100,
      value_per_token: perToken,
      value_pct_of_price: (perToken / V.near_price) * 100,
      breakeven_weekly_volume: take > 0 && share > 0 ? (V.issuance_usd_per_year) / (52 * take * share) : Infinity,
      mcap_to_revenue: V.market_cap_usd / revenue,
    };
  }
  function defaults(V) {
    return { weekly_volume: V.weekly_volume_13w_usd, take_bps: V.revenue_take_rate_13w_bps, share_pct: V.buyback_share_13w_pct, growth_pct: V.growth_base_pct, discount_pct: V.discount_rate_pct };
  }
  const api = { growthPath, dcf, run, defaults };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.SettlemarkModel = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
