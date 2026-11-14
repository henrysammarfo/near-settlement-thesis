"""Take full page screenshots of the site (light and dark, iPhone 14 and desktop). Dev tool, not part of the rebuild."""
import sys
from playwright.sync_api import sync_playwright

url, prefix = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    for name, opts in {
        "iphone14": dict(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True, has_touch=True),
        "desktop": dict(viewport={"width": 1440, "height": 900}, device_scale_factor=1),
    }.items():
        for scheme in ("light", "dark"):
            pg = b.new_page(color_scheme=scheme, **opts)
            errs_js = []
            pg.on("pageerror", lambda e: errs_js.append(str(e)))
            pg.goto(url, wait_until="networkidle")
            h = pg.evaluate("document.body.scrollHeight")
            for y in range(0, h, 400):
                pg.evaluate(f"window.scrollTo(0,{y})"); pg.wait_for_timeout(60)
            pg.wait_for_timeout(1500); pg.evaluate("window.scrollTo(0,0)"); pg.wait_for_timeout(1700)
            pg.screenshot(path=f"{prefix}_{name}_{scheme}_top.png")
            pg.screenshot(path=f"{prefix}_{name}_{scheme}_full.png", full_page=True)
            errs = pg.evaluate("[...document.images].filter(i=>!i.complete||i.naturalWidth===0).map(i=>i.src)")
            ov = pg.evaluate("document.documentElement.scrollWidth>window.innerWidth")
            small = pg.evaluate("[...document.querySelectorAll('body *')].filter(e=>e.childNodes.length&&[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())&&e.offsetParent!==null&&parseFloat(getComputedStyle(e).fontSize)<12.5).map(e=>e.tagName+':'+e.textContent.trim().slice(0,30))")
            wide = pg.evaluate("[...document.querySelectorAll('body *')].filter(e=>{const r=e.getBoundingClientRect();return r.width&&r.right>document.documentElement.clientWidth+1&&!e.closest('.term')}).map(e=>e.tagName+'.'+e.className).slice(0,5)")
            print(name, scheme, "broken images:", errs, "overflow:", ov, wide, "js errors:", errs_js, "small text:", small[:6])
            pg.close()
    b.close()
