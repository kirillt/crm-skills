#!/usr/bin/env python3
"""Deterministic company queue/top/display rendering from cache/companies."""

from __future__ import annotations

import argparse
import calendar
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parents[5] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from lib.queue_common import (
    DEFAULT_OUTPUT_DIR,
    REPO_ROOT,
    UserError,
    load_person_name,
    open_in_app,
    parse_collection_filename,
    repo_rel,
    resolve_collection_path,
)


CACHE_DIR = REPO_ROOT / "cache" / "companies"
COMPANIES_DIR = REPO_ROOT / "companies"
PROJECTS_DIR = REPO_ROOT / "projects"
ENTITY_REF_RE = re.compile(r"\{([a-z0-9_]+)\}")
PROJECT_REF_RE = re.compile(r"^\{([a-z0-9_-]+)\}$")
ENTITY_DISPLAY_CACHE: dict[str, str] = {}

TEMPERATURE_RANK = {"cold": 0, "so so": 1, "lukewarm": 2, "warm": 3, "hot": 4}
RELATIVE_RELEVANCE_RANK = {"High": 0, "Low": 1}
ORDER_METRIC_RANK = {"I": 0, "II": 1, "III": 2, "IV": 3}

# Shared company-table contract for renderer-backed views.
# Keep task templates aligned to these mode-specific column definitions instead
# of duplicating the schema in multiple task files.
QUEUE_TABLE_HEADERS: tuple[str, ...] = (
    "Company",
    "Relative relevance",
    "Order",
    "Latest communication",
    "Temperature",
    "Chance (next week)",
    "Chance (6 months)",
    "Groups",
    "Relevance",
    "Audit firms",
    "Total audits",
    "Importance",
)
TOP_TABLE_HEADERS: tuple[str, ...] = (
    "Company",
    "Groups",
    "Chance (next week)",
    "Chance (6 months)",
    "Relevance",
    "Temperature",
    "Audit firms",
    "Total audits",
    "Importance",
)
DISPLAY_TABLE_HEADERS: tuple[str, ...] = (
    "Company",
    "Groups",
    "Chance (next week)",
    "Chance (6 months)",
    "Relevance",
    "Temperature",
    "Summary",
)
DISPLAY_QUEUE_EXTRA_HEADERS: tuple[str, ...] = ("Latest communication",)


@dataclass(frozen=True, slots=True)
class Company:
    id: str
    display_name: str
    summary: str
    relevance_bp: int
    chance_next_bp: int
    chance_6m_bp: int
    temperature: str
    temp_rank: int
    importance: str
    audit_firms: int
    total_audits: int
    latest_comms_yyyymmdd: int
    latest_comms_cell: str | None
    has_active_projects: bool


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_percent(value: Any, *, ctx: str) -> int:
    if not isinstance(value, str):
        raise ValueError(f"{ctx} must be a percentage string")
    s = value.strip()
    if not s.endswith("%"):
        raise ValueError(f"{ctx} must end with %")
    try:
        return int(round(float(s[:-1]) * 100))
    except ValueError as e:
        raise ValueError(f"{ctx} must be numeric") from e


def parse_yyyymmdd(value: Any, *, ctx: str) -> int:
    if value in (None, "", "—"):
        return 0
    if not isinstance(value, str):
        raise ValueError(f"{ctx} must be YYYY-MM-DD")
    parts = value.strip().split("-")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"{ctx} must be YYYY-MM-DD")
    return int(parts[0]) * 10000 + int(parts[1]) * 100 + int(parts[2])


def yyyymmdd_to_date(value: int) -> date | None:
    if not value:
        return None
    s = f"{value:08d}"
    return date(int(s[0:4]), int(s[4:6]), int(s[6:8]))


def one_month_before(today: date) -> date:
    year = today.year
    month = today.month - 1
    if month == 0:
        year -= 1
        month = 12
    day = min(today.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def load_company_name(company_id: str) -> str:
    path = COMPANIES_DIR / f"{company_id}.json"
    data = load_json(path)
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"{path}: missing valid name")
    return name.strip()


def load_entity_display_name(entity_id: str) -> str:
    cached = ENTITY_DISPLAY_CACHE.get(entity_id)
    if cached is not None:
        return cached
    company_path = COMPANIES_DIR / f"{entity_id}.json"
    company_name = load_company_name(entity_id) if company_path.exists() else None
    person_name = load_person_name(entity_id)
    if company_name:
        name = company_name
    elif person_name:
        name = person_name
    else:
        name = entity_id.replace("_", " ")
    ENTITY_DISPLAY_CACHE[entity_id] = name
    return name


def sanitize_cell(value: str) -> str:
    value = ENTITY_REF_RE.sub(lambda m: load_entity_display_name(m.group(1)), value)
    return " ".join(value.replace("|", "\\|").replace("\n", " ").split()).strip()


def load_company_audits(company_id: str) -> tuple[int, int]:
    path = COMPANIES_DIR / f"{company_id}.json"
    data = load_json(path)
    raw = data.get("audits")
    if not isinstance(raw, dict):
        raise ValueError(f"{path}:audits must be an object")
    merged: dict[str, int] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not ENTITY_REF_RE.fullmatch(key):
            raise ValueError(f"{path}: invalid audits key")
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{path}: invalid audits value")
        merged[key] = value
    return len(merged), sum(merged.values())


def company_has_active_projects(company_id: str) -> bool:
    path = COMPANIES_DIR / f"{company_id}.json"
    data = load_json(path)
    raw = data.get("projects")
    if not isinstance(raw, list):
        return False
    for item in raw:
        if not isinstance(item, str):
            continue
        match = PROJECT_REF_RE.fullmatch(item)
        if not match:
            continue
        project_id = match.group(1)
        json_path = PROJECTS_DIR / f"{project_id}.json"
        if json_path.exists():
            project = load_json(json_path)
            dates = project.get("dates")
            if isinstance(dates, list) and dates:
                latest = dates[-1]
                if isinstance(latest, dict) and "to" not in latest:
                    return True
            continue
        # Legacy Markdown project files in the flat folder are treated as delivered
        # during migration; only JSON projects can currently encode "in progress".
    return False


def load_company_data(path: Path) -> Company:
    data = load_json(path)
    company_id = path.stem
    temperature = str(data.get("temperature", "")).strip().casefold()
    if temperature not in TEMPERATURE_RANK:
        raise ValueError(f"{path}: invalid temperature")
    audit_firms, total_audits = load_company_audits(company_id)
    latest_comms = data.get("latest_comms")
    if isinstance(latest_comms, str):
        latest_comms = latest_comms.strip() or None
    else:
        latest_comms = None
    return Company(
        id=company_id,
        display_name=load_company_name(company_id),
        summary=str(data.get("summary", "")).strip() or "—",
        relevance_bp=parse_percent(data.get("relevance"), ctx=f"{path}:relevance"),
        chance_next_bp=parse_percent(data.get("chance_next"), ctx=f"{path}:chance_next"),
        chance_6m_bp=parse_percent(data.get("chance_6m"), ctx=f"{path}:chance_6m"),
        temperature=temperature,
        temp_rank=TEMPERATURE_RANK[temperature],
        importance=str(data.get("importance", "—")).strip() or "—",
        audit_firms=audit_firms,
        total_audits=total_audits,
        latest_comms_yyyymmdd=parse_yyyymmdd(data.get("latest_comms_date"), ctx=f"{path}:latest_comms_date"),
        latest_comms_cell=latest_comms,
        has_active_projects=company_has_active_projects(company_id),
    )


def load_companies_from_cache_dir() -> list[Company]:
    companies: list[Company] = []
    seen: set[str] = set()
    for path in sorted(CACHE_DIR.glob("*.json"), key=lambda p: p.name.casefold()):
        company = load_company_data(path)
        if company.id in seen:
            raise UserError(f"Duplicate company id in cache: {company.id}")
        seen.add(company.id)
        companies.append(company)
    if not companies:
        raise UserError("No company caches found")
    return companies


def compute_benchmarks(companies: list[Company]) -> dict[str, set[str]]:
    def by_id(x: Company) -> str:
        return x.id.casefold()

    r_seed = sorted(companies, key=lambda r: (-r.relevance_bp, -r.chance_6m_bp, -r.chance_next_bp, -r.temp_rank, by_id(r)))[:10]
    l_seed = sorted(companies, key=lambda r: (-r.chance_6m_bp, -r.chance_next_bp, -r.temp_rank, -r.relevance_bp, by_id(r)))[:10]
    n_seed = sorted(companies, key=lambda r: (-r.chance_next_bp, -r.chance_6m_bp, -r.temp_rank, -r.relevance_bp, by_id(r)))[:10]
    t_seed = sorted(companies, key=lambda r: (-r.temp_rank, -r.chance_next_bp, -r.chance_6m_bp, -r.relevance_bp, by_id(r)))[:10]

    r_vals = {r.relevance_bp for r in r_seed}
    l_vals = {r.chance_6m_bp for r in l_seed}
    n_vals = {r.chance_next_bp for r in n_seed}
    t_vals = {r.temperature for r in t_seed}
    bench: dict[str, set[str]] = {"R": set(), "L": set(), "N": set(), "T": set()}
    for r in companies:
        if r.relevance_bp in r_vals:
            bench["R"].add(r.id)
        if r.chance_6m_bp in l_vals:
            bench["L"].add(r.id)
        if r.chance_next_bp in n_vals:
            bench["N"].add(r.id)
        if r.temperature in t_vals:
            bench["T"].add(r.id)
    return bench


def letters_for(bench: dict[str, set[str]], company_id: str) -> str:
    letters = "".join(k for k in "RLNT" if company_id in bench[k])
    return letters or "(none)"


def compute_relative_relevance(companies: list[Company]) -> dict[str, str]:
    total_relevance = sum(company.relevance_bp for company in companies)
    count = len(companies)
    return {company.id: ("High" if company.relevance_bp * count >= total_relevance else "Low") for company in companies}


def compute_order_metric(companies: list[Company], *, today: date) -> dict[str, str]:
    stale_cutoff = one_month_before(today)
    out: dict[str, str] = {}
    for company in companies:
        latest_date = yyyymmdd_to_date(company.latest_comms_yyyymmdd)
        has_latest = latest_date is not None
        if company.temperature in {"so so", "lukewarm"}:
            out[company.id] = "I"
        elif company.temperature == "cold":
            out[company.id] = "IV" if has_latest else "II"
        elif company.temperature == "warm" and has_latest and latest_date < stale_cutoff:
            out[company.id] = "III"
        else:
            out[company.id] = "I"
    return out


def latest_comms_cell_value(company: Company) -> str:
    if company.latest_comms_yyyymmdd:
        date_prefix = f"{company.latest_comms_yyyymmdd:08d}"
        iso_date = f"{date_prefix[0:4]}-{date_prefix[4:6]}-{date_prefix[6:8]}"
        if company.latest_comms_cell:
            return sanitize_cell(f"{iso_date} — {company.latest_comms_cell}")
        return sanitize_cell(iso_date)
    return "—"


def format_percent_bp(bp: int) -> str:
    whole = bp // 100
    frac = bp % 100
    if frac == 0:
        return f"{whole}%"
    if frac % 10 == 0:
        return f"{whole}.{frac // 10}%"
    return f"{whole}.{frac:02d}%"


def render_queue_table(ordered_ids: list[str], *, companies_by_id: dict[str, Company], letters: dict[str, str], relative_relevance: dict[str, str], order_metric: dict[str, str]) -> str:
    show_position = len(ordered_ids) > 1
    headers = []
    aligns = []
    if show_position:
        headers.append("Position")
        aligns.append("---:")
    headers.extend(QUEUE_TABLE_HEADERS)
    aligns.extend(["---", "---", "---", "---", "---", "---:", "---:", "---", "---:", "---:", "---:", "---"])
    lines = ["# Companies Queue", "", "| " + " | ".join(headers) + " |", "|" + "|".join(aligns) + "|"]
    for idx, company_id in enumerate(ordered_ids, start=1):
        company = companies_by_id[company_id]
        row = []
        if show_position:
            row.append(str(idx))
        row.extend(
            [
                sanitize_cell(company.display_name),
                sanitize_cell(relative_relevance[company_id]),
                sanitize_cell(order_metric[company_id]),
                latest_comms_cell_value(company),
                sanitize_cell(company.temperature),
                format_percent_bp(company.chance_next_bp),
                format_percent_bp(company.chance_6m_bp),
                sanitize_cell(letters[company_id]),
                format_percent_bp(company.relevance_bp),
                str(company.audit_firms),
                str(company.total_audits),
                sanitize_cell(company.importance),
            ]
        )
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def render_top_table(ordered_ids: list[str], *, companies_by_id: dict[str, Company], letters: dict[str, str]) -> str:
    show_position = len(ordered_ids) > 1
    headers = []
    aligns = []
    if show_position:
        headers.append("Position")
        aligns.append("---:")
    headers.extend(TOP_TABLE_HEADERS)
    aligns.extend(["---", "---", "---:", "---:", "---:", "---", "---:", "---:", "---"])
    lines = ["# Companies Top", "", "| " + " | ".join(headers) + " |", "|" + "|".join(aligns) + "|"]
    for idx, company_id in enumerate(ordered_ids, start=1):
        company = companies_by_id[company_id]
        row = []
        if show_position:
            row.append(str(idx))
        row.extend(
            [
                sanitize_cell(company.display_name),
                sanitize_cell(letters[company_id]),
                format_percent_bp(company.chance_next_bp),
                format_percent_bp(company.chance_6m_bp),
                format_percent_bp(company.relevance_bp),
                sanitize_cell(company.temperature),
                str(company.audit_firms),
                str(company.total_audits),
                sanitize_cell(company.importance),
            ]
        )
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def load_display_ids(path: Path, *, companies_by_id: dict[str, Company]) -> list[str]:
    data = load_json(path)
    if not isinstance(data, list) or not all(isinstance(x, str) and x.strip() for x in data):
        raise UserError("Collection JSON must be a non-empty array of company ids/basenames")
    by_cf = {cid.casefold(): cid for cid in companies_by_id}
    out: list[str] = []
    seen: set[str] = set()
    for raw in data:
        stem = Path(raw.strip()).stem.strip()
        cid = by_cf.get(stem.casefold())
        if cid and cid not in seen:
            seen.add(cid)
            out.append(cid)
    if not out:
        raise UserError("Collection is empty after normalization")
    return out


def render_display_table(
    ordered_ids: list[str],
    *,
    companies_by_id: dict[str, Company],
    letters: dict[str, str],
    sort_mode: str,
) -> str:
    show_position = len(ordered_ids) > 1
    headers = []
    aligns = []
    if show_position:
        headers.append("Position")
        aligns.append("---:")
    headers.extend(DISPLAY_TABLE_HEADERS[:-1])
    aligns.extend(["---", "---", "---:", "---:", "---:", "---"])
    if sort_mode == "queue":
        headers.extend(DISPLAY_QUEUE_EXTRA_HEADERS)
        aligns.append("---")
    headers.append(DISPLAY_TABLE_HEADERS[-1])
    aligns.append("---")

    lines = ["# Companies Display", "", "| " + " | ".join(headers) + " |", "|" + "|".join(aligns) + "|"]
    for idx, company_id in enumerate(ordered_ids, start=1):
        company = companies_by_id[company_id]
        row = []
        if show_position:
            row.append(str(idx))
        row.extend(
            [
                sanitize_cell(company.display_name),
                sanitize_cell(letters[company_id]),
                format_percent_bp(company.chance_next_bp),
                format_percent_bp(company.chance_6m_bp),
                format_percent_bp(company.relevance_bp),
                sanitize_cell(company.temperature),
            ]
        )
        if sort_mode == "queue":
            row.append(latest_comms_cell_value(company))
        row.append(sanitize_cell(company.summary))
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--mode", choices=("queue", "top", "display"), default="queue")
    parser.add_argument("--sort", choices=("top", "queue"), default="top")
    parser.add_argument("--collection", help="Optional subset collection under cache/lists/")
    parser.add_argument("--preserve-order", action="store_true", help="Keep collection order exactly as provided")
    parser.add_argument("--stdout", action="store_true", help="Write the Markdown table to stdout")
    parser.add_argument("--no-open", action="store_true", help="When writing a Markdown file, print the path without opening it")
    args = parser.parse_args(argv)

    try:
        if args.mode != "display" and args.preserve_order:
            raise UserError("--preserve-order is only valid with --mode display")
        all_cached = load_companies_from_cache_dir()
        pool = all_cached
        if args.mode == "queue":
            pool = [company for company in pool if not company.has_active_projects]
            if not pool:
                raise UserError("no companies available to render")

        companies_by_id = {company.id: company for company in pool}
        display_ids: list[str] | None = None
        collection_slug = "all"
        collection_ts: str | None = None
        if args.collection:
            collection_path = resolve_collection_path(args.collection)
            collection_slug, collection_ts = parse_collection_filename(collection_path)
            display_ids = load_display_ids(collection_path, companies_by_id=companies_by_id)

        if display_ids is None:
            candidate_ids = [company.id for company in pool]
        else:
            candidate_ids = [cid for cid in display_ids if cid in companies_by_id]
        if not candidate_ids:
            raise UserError("no companies available to render after filtering")

        displayed = [companies_by_id[cid] for cid in candidate_ids]
        bench_source = displayed if args.mode == "display" else pool
        bench = compute_benchmarks(bench_source)
        letters = {company.id: letters_for(bench, company.id) for company in bench_source}
        if args.mode == "top" and display_ids is None:
            shortlist_ids = set().union(*bench.values())
            candidate_ids = [cid for cid in candidate_ids if cid in shortlist_ids]
        if not displayed:
            raise UserError("no companies available to render after filtering")

        if args.mode == "queue":
            relative_relevance = compute_relative_relevance(displayed)
            order_metric = compute_order_metric(displayed, today=datetime.now().date())
            ordered_ids = sorted(
                candidate_ids,
                key=lambda cid: (
                    RELATIVE_RELEVANCE_RANK[relative_relevance[cid]],
                    ORDER_METRIC_RANK[order_metric[cid]],
                    companies_by_id[cid].latest_comms_yyyymmdd != 0,
                    companies_by_id[cid].latest_comms_yyyymmdd,
                    companies_by_id[cid].temp_rank,
                    -companies_by_id[cid].chance_next_bp,
                    -companies_by_id[cid].chance_6m_bp,
                    cid.casefold(),
                ),
            )
            md = render_queue_table(
                ordered_ids,
                companies_by_id=companies_by_id,
                letters=letters,
                relative_relevance=relative_relevance,
                order_metric=order_metric,
            )
        elif args.mode == "top":
            ordered_ids = sorted(
                candidate_ids,
                key=lambda cid: (
                    -len(letters[cid].replace("(none)", "")),
                    -companies_by_id[cid].chance_next_bp,
                    -companies_by_id[cid].chance_6m_bp,
                    -companies_by_id[cid].relevance_bp,
                    -companies_by_id[cid].temp_rank,
                    cid.casefold(),
                ),
            )
            md = render_top_table(
                ordered_ids,
                companies_by_id=companies_by_id,
                letters=letters,
            )
        else:
            if args.preserve_order:
                ordered_ids = candidate_ids
            elif args.sort == "queue":
                relative_relevance = compute_relative_relevance(displayed)
                order_metric = compute_order_metric(displayed, today=datetime.now().date())
                ordered_ids = sorted(
                    candidate_ids,
                    key=lambda cid: (
                        RELATIVE_RELEVANCE_RANK[relative_relevance[cid]],
                        ORDER_METRIC_RANK[order_metric[cid]],
                        companies_by_id[cid].latest_comms_yyyymmdd != 0,
                        companies_by_id[cid].latest_comms_yyyymmdd,
                        companies_by_id[cid].temp_rank,
                        -companies_by_id[cid].chance_next_bp,
                        -companies_by_id[cid].chance_6m_bp,
                        cid.casefold(),
                    ),
                )
            else:
                ordered_ids = sorted(
                    candidate_ids,
                    key=lambda cid: (
                        -len(letters[cid].replace("(none)", "")),
                        -companies_by_id[cid].chance_next_bp,
                        -companies_by_id[cid].chance_6m_bp,
                        -companies_by_id[cid].relevance_bp,
                        -companies_by_id[cid].temp_rank,
                        cid.casefold(),
                    ),
                )
            md = render_display_table(
                ordered_ids,
                companies_by_id=companies_by_id,
                letters=letters,
                sort_mode=args.sort,
            )
        if args.stdout:
            sys.stdout.write(md)
            return 0

        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = collection_ts or datetime.now().strftime("%Y%m%d-%H%M%S")
        mode_slug = args.mode if args.mode != "display" else f"display-{args.sort}"
        out_path = DEFAULT_OUTPUT_DIR / f"companies-{mode_slug}-{collection_slug}-{ts}.md"
        out_path.write_text(md, encoding="utf-8")
        if not args.no_open:
            open_in_app(out_path, context=f"companies-display.py mode={args.mode} sort={args.sort}")
        sys.stdout.write(repo_rel(out_path) + "\n")
        return 0
    except (UserError, FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
