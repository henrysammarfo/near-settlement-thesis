"""`python -m settlemark check`: prove the committed outputs are what the code makes from data/.

1. Rebuild from the committed CSVs into a temporary directory and compare every generated
   file with the committed one, byte for byte.
2. Audit THESIS.md: every number in it must either come from a computed value filled into a
   template placeholder, or be a constant written in the template itself. The constants are
   listed so a reader can see every hand-typed number in one place.
"""

from __future__ import annotations

import filecmp
import re
import string
import tempfile
from pathlib import Path

from .config import Config, load_config

NUM = re.compile(r"(?<![\w.])[-+\u2212]?\$?\d[\d,]*(?:\.\d+)?[%xMBK]?")
GENERATED = ("results", "charts", "site", "THESIS.md")
KEPT = ("site/v1/", "site/.")  # the archived first version and deploy settings are not build outputs


def _files(base: Path) -> set[str]:
    out = set()
    for name in GENERATED:
        p = base / name
        if p.is_file():
            out.add(name)
        elif p.is_dir():
            out |= {str(f.relative_to(base)) for f in p.rglob("*") if f.is_file() and not str(f.relative_to(base)).startswith(KEPT)}
    return out


def template_constants(cfg: Config) -> list[str]:
    tmpl = cfg.paths.template.read_text()
    blank = string.Formatter()
    text = "".join(lit for lit, *_ in blank.parse(tmpl))
    text = re.sub(r"\]\([^)]*\)", "]", text)  # link targets are not claims
    return NUM.findall(text)


def audit_numbers(cfg: Config, thesis: str, filled: dict[str, str]) -> list[str]:
    allowed = set(template_constants(cfg))
    for v in filled.values():
        allowed |= set(NUM.findall(str(v)))
    body = re.sub(r"\]\([^)]*\)", "]", thesis)
    return [n for n in NUM.findall(body) if n not in allowed]


def check(cfg: Config) -> list[str]:
    from .__main__ import build
    from .render import thesis_context

    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        tcfg = load_config(root=cfg.paths.root, output_root=out)
        build(tcfg)
        for rel in sorted(_files(cfg.paths.root) | _files(out)):
            a, b = cfg.paths.root / rel, out / rel
            if not a.exists():
                problems.append(f"not committed: {rel}")
            elif not b.exists():
                problems.append(f"committed but no longer generated: {rel}")
            elif not filecmp.cmp(a, b, shallow=False):
                problems.append(f"differs from a fresh build: {rel}")
    import json

    R = json.loads((cfg.paths.results / "results.json").read_text())
    stray = audit_numbers(cfg, cfg.paths.thesis.read_text(), thesis_context(cfg, R))
    problems += [f"number in THESIS.md not computed and not a template constant: {n}" for n in stray]
    return problems
