// Settlemark page: interactive charts drawn as SVG from data.json (written by `npm run rebuild`).
(() => {
  "use strict";
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const NS = "http://www.w3.org/2000/svg";
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const el = (tag, attrs = {}, parent) => {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  };
  const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const d2 = (s) => { const [y, m, d] = s.split("-").map(Number); return { y, m, d, t: Date.UTC(y, m - 1, d) }; };
  const dateLabel = (s) => { const x = d2(s); return `${x.d} ${MON[x.m - 1]} ${x.y}`; };
  const money = (v) => v >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : v >= 1e6 ? `$${(v / 1e6).toFixed(v >= 1e8 ? 0 : 1)}M` : v >= 1e3 ? `$${(v / 1e3).toFixed(0)}K` : `$${v.toFixed(0)}`;
  const minus = (s) => s.replace("-", "\u2212");
  const nice = (max, n = 4) => {
    const raw = max / n, p = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / p;
    const step = (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
    return { step, top: Math.ceil(max / step) * step };
  };
  const tip = document.getElementById("tip");
  const showTip = (host, x, y, html) => {
    const r = host.getBoundingClientRect();
    const px = Math.min(Math.max(r.left + x + scrollX, scrollX + 90), scrollX + document.documentElement.clientWidth - 90);
    tip.innerHTML = html; tip.style.left = px + "px"; tip.style.top = (r.top + y + scrollY) + "px"; tip.classList.add("on");
  };
  const hideTip = () => tip.classList.remove("on");

  // Time series chart: optional bars on the left axis, optional line on the right axis.
  function series(host, cfg) {
    const draw = () => {
      host.innerHTML = "";
      const W = host.clientWidth, small = W < 560;
      const H = small ? 280 : 380;
      const m = { t: 16, r: cfg.right ? (small ? 40 : 52) : 8, b: 32, l: small ? 48 : 60 };
      const iw = W - m.l - m.r, ih = H - m.t - m.b, n = cfg.x.length;
      const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, height: H }, host);
      const g = el("g", { transform: `translate(${m.l},${m.t})` }, svg);
      const L = nice(Math.max(...cfg.left.y));
      const ys = (v) => ih - (v / L.top) * ih;
      const xs = (i) => (i + 0.5) * (iw / n);
      for (let v = 0; v <= L.top + 1e-9; v += L.step) {
        el("line", { class: "grid", x1: 0, x2: iw, y1: ys(v), y2: ys(v) }, g);
        el("text", { x: -10, y: ys(v) + 4, "text-anchor": "end" }, g).textContent = cfg.left.fmt(v);
      }
      // x ticks: one label per quarter start, thinned on small screens
      let last = -1;
      cfg.x.forEach((s, i) => {
        const x = d2(s);
        const q = x.y * 12 + x.m - 1;
        const every = small ? 6 : 3;
        if ((x.m - 1) % every === 0 && q !== last && x.d <= 7) {
          last = q;
          el("text", { x: xs(i), y: ih + 24, "text-anchor": "middle" }, g).textContent = x.m === 1 ? String(x.y) : MON[x.m - 1];
        }
      });
      const col = css(cfg.left.color);
      if (cfg.left.type === "bar") {
        const bw = Math.max(1, iw / n - (small ? 1 : 2));
        cfg.left.y.forEach((v, i) => {
          const r = el("rect", { x: xs(i) - bw / 2, y: ys(v), width: bw, height: ih - ys(v), rx: Math.min(2, bw / 3), fill: col }, g);
          if (!reduce) { r.style.transformOrigin = `0 ${ih}px`; r.style.transform = "scaleY(0)"; r.style.transition = `transform .9s cubic-bezier(.16,1,.3,1) ${i * 6}ms`; }
        });
      } else {
        const pts = cfg.left.y.map((v, i) => `${xs(i)},${ys(v)}`);
        if (cfg.left.area) el("path", { d: `M${xs(0)},${ih}L${pts.join("L")}L${xs(n - 1)},${ih}Z`, fill: col, opacity: 0.12 }, g).classList.add("fade");
        const p = el("path", { d: "M" + pts.join("L"), fill: "none", stroke: col, "stroke-width": 2.5, "stroke-linejoin": "round", "stroke-linecap": "round" }, g);
        p.classList.add("drawline");
      }
      let R;
      if (cfg.right) {
        R = nice(Math.max(...cfg.right.y));
        const yr = (v) => ih - (v / R.top) * ih;
        for (let v = 0; v <= R.top + 1e-9; v += R.step) el("text", { x: iw + 10, y: yr(v) + 4 }, g).textContent = cfg.right.fmt(v);
        const p = el("path", { d: "M" + cfg.right.y.map((v, i) => `${xs(i)},${yr(v)}`).join("L"), fill: "none", stroke: css(cfg.right.color), "stroke-width": 2.5, "stroke-linejoin": "round" }, g);
        p.classList.add("drawline");
        R.ys = yr;
      }
      const rule = el("line", { x1: 0, x2: 0, y1: 0, y2: ih, stroke: css("--mute"), "stroke-dasharray": "3 3", opacity: 0 }, g);
      const dot = el("circle", { r: 5, fill: css("--bg"), stroke: col, "stroke-width": 2.5, opacity: 0 }, g);
      const hit = el("rect", { x: 0, y: 0, width: iw, height: ih, fill: "transparent" }, g);
      const move = (ev) => {
        const b = svg.getBoundingClientRect();
        const cx = (ev.touches ? ev.touches[0].clientX : ev.clientX) - b.left - m.l;
        const i = Math.max(0, Math.min(n - 1, Math.floor(cx / (iw / n))));
        rule.setAttribute("x1", xs(i)); rule.setAttribute("x2", xs(i)); rule.setAttribute("opacity", 1);
        const yv = cfg.left.y[i];
        dot.setAttribute("cx", xs(i)); dot.setAttribute("cy", ys(yv)); dot.setAttribute("opacity", 1);
        let h = `<span style="opacity:.7">Week to ${dateLabel(cfg.x[i])}</span><br><b>${cfg.left.tip(yv)}</b>`;
        if (cfg.right) h += ` &nbsp;·&nbsp; <b>${cfg.right.tip(cfg.right.y[i])}</b>`;
        showTip(host, m.l + xs(i), m.t + Math.min(ys(yv), cfg.right ? R.ys(cfg.right.y[i]) : ih), h);
      };
      const leave = () => { rule.setAttribute("opacity", 0); dot.setAttribute("opacity", 0); hideTip(); };
      hit.addEventListener("pointermove", move); hit.addEventListener("pointerdown", move); hit.addEventListener("pointerleave", leave);
      host._play = () => play(svg);
      if (host._played) play(svg, true);
    };
    draw();
    let w = host.clientWidth;
    new ResizeObserver(() => { if (host.clientWidth !== w) { w = host.clientWidth; draw(); } }).observe(host);
  }

  function play(svg, instant) {
    svg.querySelectorAll("rect[style]").forEach((r) => { if (instant) r.style.transition = "none"; r.style.transform = "scaleY(1)"; });
    svg.querySelectorAll(".drawline").forEach((p) => {
      if (reduce || instant) return;
      const len = p.getTotalLength();
      p.style.strokeDasharray = len; p.style.strokeDashoffset = len;
      p.getBoundingClientRect();
      p.style.transition = "stroke-dashoffset 1.6s cubic-bezier(.16,1,.3,1) .2s"; p.style.strokeDashoffset = 0;
    });
  }

  function scatter(host, xsData, ysData, dates) {
    const draw = () => {
      host.innerHTML = "";
      const W = host.clientWidth, small = W < 560, H = small ? 300 : 380;
      const m = { t: 16, r: 16, b: 36, l: small ? 44 : 52 };
      const iw = W - m.l - m.r, ih = H - m.t - m.b;
      const ext = (a) => { const v = Math.max(...a.map(Math.abs)); return nice(v, 2); };
      const X = ext(xsData), Y = ext(ysData);
      const sx = (v) => ((v + X.top) / (2 * X.top)) * iw, sy = (v) => ih - ((v + Y.top) / (2 * Y.top)) * ih;
      const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, height: H }, host);
      const g = el("g", { transform: `translate(${m.l},${m.t})` }, svg);
      for (let v = -X.top; v <= X.top + 1e-9; v += X.step) { el("line", { class: "grid", x1: sx(v), x2: sx(v), y1: 0, y2: ih }, g); el("text", { x: sx(v), y: ih + 24, "text-anchor": "middle" }, g).textContent = minus(`${v}%`); }
      for (let v = -Y.top; v <= Y.top + 1e-9; v += Y.step) { el("line", { class: "grid", x1: 0, x2: iw, y1: sy(v), y2: sy(v) }, g); el("text", { x: -10, y: sy(v) + 4, "text-anchor": "end" }, g).textContent = minus(`${v}%`); }
      el("line", { x1: sx(0), x2: sx(0), y1: 0, y2: ih, stroke: css("--mute"), "stroke-width": 1 }, g);
      el("line", { x1: 0, x2: iw, y1: sy(0), y2: sy(0), stroke: css("--mute"), "stroke-width": 1 }, g);
      const acc = css("--acc");
      const dots = xsData.map((v, i) => {
        const c = el("circle", { cx: sx(v), cy: sy(ysData[i]), r: small ? 4 : 5, fill: acc, "fill-opacity": 0.55 }, g);
        if (!reduce && !host._played) { c.style.opacity = 0; c.style.transition = `opacity .5s ease ${i * 8}ms`; }
        return c;
      });
      const hit = el("rect", { x: 0, y: 0, width: iw, height: ih, fill: "transparent" }, g);
      let cur;
      const move = (ev) => {
        const b = svg.getBoundingClientRect();
        const px = (ev.touches ? ev.touches[0].clientX : ev.clientX) - b.left - m.l, py = (ev.touches ? ev.touches[0].clientY : ev.clientY) - b.top - m.t;
        let best = 0, bd = Infinity;
        xsData.forEach((v, i) => { const d = (sx(v) - px) ** 2 + (sy(ysData[i]) - py) ** 2; if (d < bd) { bd = d; best = i; } });
        if (cur) { cur.setAttribute("fill-opacity", 0.55); cur.setAttribute("r", small ? 4 : 5); }
        cur = dots[best]; cur.setAttribute("fill-opacity", 1); cur.setAttribute("r", 7);
        showTip(host, m.l + sx(xsData[best]), m.t + sy(ysData[best]), `<span style="opacity:.7">Week to ${dateLabel(dates[best])}</span><br>Price <b>${minus(xsData[best].toFixed(1))}%</b> · Volume <b>${minus(ysData[best].toFixed(1))}%</b>`);
      };
      hit.addEventListener("pointermove", move); hit.addEventListener("pointerdown", move);
      hit.addEventListener("pointerleave", () => { if (cur) { cur.setAttribute("fill-opacity", 0.55); cur.setAttribute("r", small ? 4 : 5); } hideTip(); });
      host._play = () => dots.forEach((c) => (c.style.opacity = 1));
      if (host._played) host._play();
    };
    draw();
    let w = host.clientWidth;
    new ResizeObserver(() => { if (host.clientWidth !== w) { w = host.clientWidth; draw(); } }).observe(host);
  }

  function valueBars(host, vc) {
    const entries = Object.entries(vc), max = Math.max(...entries.map((e) => e[1]));
    const colors = { "Intents revenue": "var(--bad)", "NEAR chain gas fees": "var(--mute)", "Intents fees (all)": "var(--acc)" };
    const note = { "Intents revenue": "kept by the protocol", "NEAR chain gas fees": "paid to the network", "Intents fees (all)": "including solvers" };
    host.innerHTML = entries.map(([k, v]) => `<div class="vb"><div class="row"><span>${k} <span style="color:var(--mute)">· ${note[k] || ""}</span></span><b class="num">${money(v)}</b></div><div class="track"><div class="fill" style="--f:${(v / max).toFixed(4)};background:${colors[k] || "var(--acc)"}"></div></div></div>`).join("");
  }

  // Counters, reveals, nav progress and active section.
  const fmt = (v, e) => { const d = +e.dataset.dec || 0; return (e.dataset.pre || "") + v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }) + (e.dataset.suf || ""); };
  const count = (e) => { const to = parseFloat(e.dataset.count); if (reduce || !isFinite(to)) return; const t0 = performance.now(); const step = (t) => { const p = Math.min(1, (t - t0) / 1600), k = 1 - Math.pow(2, -10 * p); e.textContent = fmt(p < 1 ? to * k : to, e); if (p < 1) requestAnimationFrame(step); }; requestAnimationFrame(step); };
  document.querySelectorAll("[data-count]").forEach(count);
  const io = new IntersectionObserver((es) => { for (const x of es) { if (!x.isIntersecting) continue; const t = x.target; t.classList.add("in"); t.querySelectorAll(".plot,.vbars").forEach((p) => { p.classList.add("in"); p._played = true; if (p._play) p._play(); }); io.unobserve(t); } }, { rootMargin: "0px 0px -10% 0px", threshold: 0.15 });
  document.querySelectorAll(".r").forEach((n) => io.observe(n));
  const prog = document.getElementById("prog"), links = [...document.querySelectorAll(".nav ul a[href^='#']")];
  const secs = links.map((a) => document.querySelector(a.getAttribute("href")));
  const onScroll = () => {
    const h = document.documentElement.scrollHeight - innerHeight;
    prog.style.transform = `scaleX(${h > 0 ? scrollY / h : 0})`;
    let on = -1; secs.forEach((s, i) => { if (s && s.getBoundingClientRect().top < innerHeight * 0.4) on = i; });
    links.forEach((a, i) => a.classList.toggle("on", i === on));
  };
  addEventListener("scroll", onScroll, { passive: true }); onScroll();
  document.querySelectorAll(".copy").forEach((b) => b.addEventListener("click", async () => { try { await navigator.clipboard.writeText(b.dataset.copy); b.textContent = "Copied"; } catch { b.textContent = "Select to copy"; } setTimeout(() => (b.textContent = "Copy"), 1600); }));

  fetch("data.json").then((r) => r.json()).then((D) => {
    const w = D.weekly;
    series(document.getElementById("c-flow"), {
      x: w.date,
      left: { y: w.intents_volume_usd, type: "bar", color: "--acc", fmt: money, tip: (v) => `${money(v)} volume` },
      right: { y: w.near_price_usd, color: "--ink", fmt: (v) => `$${v}`, tip: (v) => `NEAR $${v.toFixed(2)}` },
    });
    series(document.getElementById("c-share"), { x: w.date, left: { y: w.share_pct, type: "line", area: true, color: "--good", fmt: (v) => `${+v.toFixed(2)}%`, tip: (v) => `${v.toFixed(2)}% of DEX volume` } });
    series(document.getElementById("c-aa"), { x: w.date, left: { y: w.active_accounts, type: "line", area: true, color: "--bad", fmt: (v) => v >= 1e6 ? `${v / 1e6}M` : `${v / 1e3}K`, tip: (v) => `${Math.round(v).toLocaleString("en-US")} accounts a day` } });
    const c = D.weekly_changes;
    scatter(document.getElementById("c-scatter"), c.near_price_pct, c.intents_volume_pct, c.date);
    valueBars(document.getElementById("c-value"), D.value_capture_365d);
    document.querySelectorAll(".plot,.vbars").forEach((p) => { if (p.closest(".r.in")) { p.classList.add("in"); p._played = true; if (p._play) p._play(); } });
  }).catch((e) => { document.querySelectorAll(".plot").forEach((p) => (p.textContent = "Chart data could not load. See THESIS.md.")); console.error(e); });
})();
