#!/usr/bin/env python3
"""Expand a company topic expression into a deterministic subset collection."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

TOOLS_DIR = Path(__file__).resolve().parents[5] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from lib.queue_common import DEFAULT_LIST_DIR, REPO_ROOT, UserError, repo_rel

ABOUT_US_DIR = REPO_ROOT / "about-us"
if str(ABOUT_US_DIR) not in sys.path:
    sys.path.insert(0, str(ABOUT_US_DIR))

from rubrics import ALLOWED_RUBRIC_IDS


COMPANIES_DIR = REPO_ROOT / "companies"

WS_RE = re.compile(r"\s+")
NON_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def norm_ws(s: str) -> str:
    return WS_RE.sub(" ", (s or "").strip())


def norm_key(s: str) -> str:
    s = norm_ws(s).casefold()
    s = re.sub(r"[\W_]+", " ", s)
    return norm_ws(s)


def slugify(expr: str) -> str:
    s = norm_ws(expr)
    s = s.replace("<", "").replace(">", "")
    s = s.replace(" - ", " minus ")
    s = s.replace("/", " or ")
    s = s.replace("&", " and ")
    s = norm_key(s).replace(" ", "-")
    s = NON_SLUG_RE.sub("-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    if not s:
        s = "subset"
    if len(s) <= 48:
        return s
    h = hashlib.sha1(expr.encode("utf-8")).hexdigest()[:8]
    return f"{s[:40]}-{h}".strip("-")


def strip_outer_angle(s: str) -> str | None:
    s = s.strip()
    if not (s.startswith("<") and s.endswith(">")):
        return None
    depth = 0
    for i, ch in enumerate(s):
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
            if depth == 0 and i != len(s) - 1:
                return None
        if depth < 0:
            return None
    if depth != 0:
        return None
    return s[1:-1]


def split_top_level(s: str, sep: str) -> list[str]:
    out: list[str] = []
    depth = 0
    i = 0
    start = 0
    while i <= len(s) - len(sep):
        ch = s[i]
        if ch == "<":
            depth += 1
            i += 1
            continue
        if ch == ">":
            depth = max(0, depth - 1)
            i += 1
            continue
        if depth == 0 and s.startswith(sep, i):
            out.append(s[start:i])
            i += len(sep)
            start = i
            continue
        i += 1
    out.append(s[start:])
    return out


def split_top_level_char(s: str, ch: str) -> list[str]:
    out: list[str] = []
    depth = 0
    start = 0
    for i, c in enumerate(s):
        if c == "<":
            depth += 1
            continue
        if c == ">":
            depth = max(0, depth - 1)
            continue
        if depth == 0 and c == ch:
            out.append(s[start:i])
            start = i + 1
    out.append(s[start:])
    return out


@dataclass(frozen=True, slots=True)
class CompanyFacts:
    company_id: str
    title: str
    rubrics: tuple[str, ...]


def all_companies() -> dict[str, CompanyFacts]:
    if not COMPANIES_DIR.exists():
        raise UserError("companies/ folder not found")
    out: dict[str, CompanyFacts] = {}
    for path in sorted(COMPANIES_DIR.glob("*.json"), key=lambda p: p.name.casefold()):
        data = json.loads(path.read_text(encoding="utf-8"))
        name = data.get("name")
        rubrics = data.get("rubrics")
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(rubrics, list):
            rubrics = []
        out[path.stem] = CompanyFacts(
            company_id=path.stem,
            title=name.strip(),
            rubrics=tuple(r for r in rubrics if isinstance(r, str) and r.strip()),
        )
    if not out:
        raise UserError("no companies found under companies/")
    return out


def canonical_term(term: str) -> str:
    term = norm_ws(term)
    if not term:
        raise UserError("empty term in expression")
    if term not in ALLOWED_RUBRIC_IDS:
        raise UserError(
            f"unknown rubric term `{term}`; use canonical rubric IDs from about-us/rubrics.py"
        )
    return term


def matches_term(facts: CompanyFacts, term: str) -> bool:
    return canonical_term(term) in set(facts.rubrics)


def eval_expr(expr: str, *, universe: set[str], facts_by_id: dict[str, CompanyFacts]) -> set[str]:
    expr = expr.strip()
    if not expr:
        raise UserError("empty expression")

    inner = strip_outer_angle(expr)
    if inner is not None:
        return eval_expr(inner, universe=universe, facts_by_id=facts_by_id)

    if expr.startswith("-<") and expr.endswith(">"):
        inner2 = strip_outer_angle(expr[1:])
        if inner2 is None:
            raise UserError("invalid unary negation; expected -<...>")
        return universe - eval_expr(inner2, universe=universe, facts_by_id=facts_by_id)

    parts = [norm_ws(p) for p in split_top_level(expr, " - ") if norm_ws(p)]
    if not parts:
        raise UserError("invalid expression")
    out = eval_or(parts[0], universe=universe, facts_by_id=facts_by_id)
    for p in parts[1:]:
        out = out - eval_or(p, universe=universe, facts_by_id=facts_by_id)
    return out


def eval_or(s: str, *, universe: set[str], facts_by_id: dict[str, CompanyFacts]) -> set[str]:
    parts = [norm_ws(p) for p in split_top_level_char(s, "/") if norm_ws(p)]
    if not parts:
        raise UserError("invalid OR expression")
    out: set[str] = set()
    for p in parts:
        out |= eval_and(p, universe=universe, facts_by_id=facts_by_id)
    return out


def eval_and(s: str, *, universe: set[str], facts_by_id: dict[str, CompanyFacts]) -> set[str]:
    parts = [norm_ws(p) for p in split_top_level_char(s, "&") if norm_ws(p)]
    if not parts:
        raise UserError("invalid AND expression")
    out = universe.copy()
    for p in parts:
        inner = strip_outer_angle(p)
        if inner is not None:
            out &= eval_expr(inner, universe=universe, facts_by_id=facts_by_id)
            continue
        if p.startswith("-<") and p.endswith(">"):
            out &= eval_expr(p, universe=universe, facts_by_id=facts_by_id)
            continue
        out &= {cid for cid in universe if matches_term(facts_by_id[cid], p)}
    return out


def to_sorted_list(ids: Iterable[str], *, facts_by_id: dict[str, CompanyFacts]) -> list[str]:
    return sorted(set(ids), key=lambda cid: facts_by_id[cid].title.casefold())


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("expr", help="Subset selector or topic expression")
    parser.add_argument("--slug", help="Override the output slug; must be [a-z0-9-]+")
    args = parser.parse_args(argv)

    try:
        facts_by_id = all_companies()
        universe = set(facts_by_id.keys())
        expr = args.expr.strip()
        if not expr:
            raise UserError("empty expression")
        matched = eval_expr(expr, universe=universe, facts_by_id=facts_by_id)

        matched_list = to_sorted_list(matched, facts_by_id=facts_by_id)
        if not matched_list:
            raise UserError("no companies matched this expression")

        slug = args.slug.strip().casefold() if args.slug else slugify(expr)
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
            raise UserError("--slug must match: [a-z0-9][a-z0-9-]*")

        DEFAULT_LIST_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_path = DEFAULT_LIST_DIR / f"collection-{slug}-{ts}.json"
        out_path.write_text(json.dumps(matched_list, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        print(repo_rel(out_path))
        print(f"Count: {len(matched_list)}", file=sys.stderr)
        return 0
    except UserError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
