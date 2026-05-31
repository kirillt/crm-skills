#!/usr/bin/env python3
"""Resolve an explicit company subset into a deterministic collection JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[5] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from lib.queue_common import DEFAULT_LIST_DIR, REPO_ROOT, UserError, repo_rel


COMPANIES_DIR = REPO_ROOT / "companies"
ALIASES_PATH = REPO_ROOT / "aliases.json"
WS_RE = re.compile(r"\s+")
NON_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def norm_ws(s: str) -> str:
    return WS_RE.sub(" ", (s or "").strip())


def norm_key(s: str) -> str:
    s = norm_ws(s).casefold()
    s = re.sub(r"[\W_]+", " ", s)
    return norm_ws(s)


def slugify(expr: str) -> str:
    s = norm_key(expr).replace(" ", "-")
    s = NON_SLUG_RE.sub("-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "companies"


def load_aliases() -> dict[str, str]:
    if not ALIASES_PATH.exists():
        return {}
    data = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(key, str) and isinstance(value, str):
            out[norm_key(key)] = value
    return out


def load_company_index() -> tuple[dict[str, str], dict[str, str]]:
    by_id: dict[str, str] = {}
    by_name: dict[str, str] = {}
    for path in sorted(COMPANIES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        name = data.get("name")
        if isinstance(name, str) and name.strip():
            by_id[path.stem.casefold()] = path.stem
            by_name[norm_key(name)] = path.stem
    return by_id, by_name


def resolve_one(raw: str, *, aliases: dict[str, str], by_id: dict[str, str], by_name: dict[str, str]) -> str:
    text = raw.strip()
    if not text:
        raise UserError("Empty company selector")
    key = norm_key(text)
    if key in aliases:
        return aliases[key]
    if text.casefold() in by_id:
        return by_id[text.casefold()]
    if key in by_name:
        return by_name[key]
    id_matches = [cid for cf, cid in by_id.items() if cf.startswith(text.casefold())]
    name_matches = [cid for nk, cid in by_name.items() if nk.startswith(key)]
    matches = sorted(set(id_matches + name_matches))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise UserError(f"Ambiguous company selector `{raw}`: {', '.join(matches[:10])}")
    raise UserError(f"Unknown company selector: {raw}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("companies", help="Semicolon-separated company names / ids / aliases")
    args = parser.parse_args(argv)

    try:
        aliases = load_aliases()
        by_id, by_name = load_company_index()
        parts = [part.strip() for part in args.companies.split(";") if part.strip()]
        if not parts:
            raise UserError("No companies provided")
        resolved: list[str] = []
        seen: set[str] = set()
        for part in parts:
            cid = resolve_one(part, aliases=aliases, by_id=by_id, by_name=by_name)
            if cid not in seen:
                seen.add(cid)
                resolved.append(cid)

        DEFAULT_LIST_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = slugify(args.companies)
        out_path = DEFAULT_LIST_DIR / f"collection-{slug}-{ts}.json"
        out_path.write_text(json.dumps(resolved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        sys.stdout.write(repo_rel(out_path) + "\n")
        return 0
    except UserError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
