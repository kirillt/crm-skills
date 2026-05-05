#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "AGENTS.md").exists():
            return candidate
    raise RuntimeError("Could not locate repo root from validator path")

ROOT = find_repo_root(Path(__file__).resolve())
TOOLS_DIR = ROOT / "tools"
for extra_path in (ROOT, TOOLS_DIR):
    extra = str(extra_path)
    if extra not in sys.path:
        sys.path.insert(0, extra)

from lib.queue_common import load_person_name

CACHE_DIR = ROOT / "cache" / "companies"
COMPANIES_DIR = ROOT / "companies"

FIELDS = [
    "summary",
    "importance",
    "relevance",
    "temperature",
    "contacts",
    "former_staff_routes",
    "latest_comms",
    "latest_comms_date",
    "chance_next",
    "chance_6m",
]
MANDATORY_FIELDS = [
    "summary",
    "importance",
    "relevance",
    "temperature",
    "contacts",
    "latest_comms",
    "latest_comms_date",
    "chance_next",
    "chance_6m",
]
OPTIONAL_FIELDS = {"former_staff_routes"}
ALLOWED = set(MANDATORY_FIELDS) | OPTIONAL_FIELDS
IMPORTANCE = {"Low", "Medium", "High", "Top"}
TEMPERATURE = {"cold", "so so", "lukewarm", "warm", "hot"}
ID_RE = re.compile(r"^\{[a-z0-9_]+\}$")
PERCENT_RE = re.compile(r"^\d+(?:\.\d+)?%$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def resolve_target_paths(raw_paths: list[str]) -> list[Path]:
    if not raw_paths:
        return sorted(CACHE_DIR.glob("*.json"))
    if len(raw_paths) != 1:
        raise SystemExit("Provide at most one cache JSON path")

    raw = Path(raw_paths[0])
    path = raw if raw.is_absolute() else (ROOT / raw)
    path = path.resolve()
    if not path.exists():
        raise SystemExit(f"Path not found: {raw_paths[0]}")
    if not path.is_file():
        raise SystemExit(f"Not a file: {raw_paths[0]}")
    if path.suffix != ".json":
        raise SystemExit(f"Expected a .json file: {raw_paths[0]}")
    if path.parent != CACHE_DIR.resolve():
        raise SystemExit(f"Expected a file under cache/companies/: {raw_paths[0]}")
    return [path]


def ids_in(dir_path: Path) -> set[str]:
    return {path.stem for path in dir_path.glob("*.json")}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, data: dict):
    ordered = OrderedDict((field, data[field]) for field in FIELDS if field in data)
    path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def warn(warnings: list[str], path: Path, message: str):
    warnings.append(f"{path.relative_to(ROOT)}: {message}")


def percent_value(text: str) -> float:
    return float(text[:-1])


def person_display_name(person_id: str) -> str:
    try:
        name = load_person_name(person_id)
    except Exception:
        name = None
    if name:
        return name
    return person_id.replace("_", " ")


def comm_mentions_person(summary: str, person_ref: str) -> bool:
    if person_ref in summary:
        return True
    person_id = person_ref[1:-1]
    return person_display_name(person_id).casefold() in summary.casefold()


def validate(path: Path, errors: list[str], warnings: list[str]):
    try:
        data = load_json(path)
    except Exception as exc:
        errors.append(f"{path.relative_to(ROOT)}: failed to parse JSON: {exc}")
        return None

    if not isinstance(data, dict):
        errors.append(f"{path.relative_to(ROOT)}: top-level JSON value must be an object")
        return None

    unknown = [key for key in data if key not in ALLOWED]
    if unknown:
        errors.append(f"{path.relative_to(ROOT)}: unknown fields: {', '.join(unknown)}")

    for field in MANDATORY_FIELDS:
        if field not in data:
            errors.append(f"{path.relative_to(ROOT)}: missing mandatory field `{field}`")
    if any(field not in data for field in MANDATORY_FIELDS):
        return None

    if not isinstance(data["summary"], str) or not data["summary"].strip():
        errors.append(f"{path.relative_to(ROOT)}: `summary` must be a non-empty string")
    elif len(data["summary"]) > 80:
        errors.append(f"{path.relative_to(ROOT)}: `summary` must be 80 characters or less")

    if data["importance"] not in IMPORTANCE:
        errors.append(f"{path.relative_to(ROOT)}: `importance` must be one of Low/Medium/High/Top")

    if not isinstance(data["relevance"], str) or not PERCENT_RE.fullmatch(data["relevance"]):
        errors.append(f"{path.relative_to(ROOT)}: `relevance` must be a percentage string")
    elif percent_value(data["relevance"]) < 0:
        errors.append(f"{path.relative_to(ROOT)}: `relevance` must not be negative")

    if data["temperature"] not in TEMPERATURE:
        errors.append(f"{path.relative_to(ROOT)}: `temperature` must be one of cold/so so/lukewarm/warm/hot")

    if not isinstance(data["contacts"], list):
        errors.append(f"{path.relative_to(ROOT)}: `contacts` must be an array")
    former_staff_routes = data.get("former_staff_routes")
    if former_staff_routes is not None:
        if not isinstance(former_staff_routes, list):
            errors.append(f"{path.relative_to(ROOT)}: `former_staff_routes` must be an array when present")
        else:
            seen_former_staff = set()
            for index, item in enumerate(former_staff_routes):
                if not isinstance(item, dict):
                    errors.append(f"{path.relative_to(ROOT)}: `former_staff_routes[{index}]` must be an object")
                    continue
                if set(item.keys()) != {"id", "summary"}:
                    errors.append(f"{path.relative_to(ROOT)}: `former_staff_routes[{index}]` must contain exactly `id` and `summary`")
                    continue
                person_ref = item.get("id")
                summary = item.get("summary")
                if not isinstance(person_ref, str) or not ID_RE.fullmatch(person_ref):
                    errors.append(f"{path.relative_to(ROOT)}: `former_staff_routes[{index}].id` must be a {{id}} string")
                elif person_ref in seen_former_staff:
                    errors.append(f"{path.relative_to(ROOT)}: `former_staff_routes` must not contain duplicate people")
                else:
                    seen_former_staff.add(person_ref)
                if not isinstance(summary, str) or not summary.strip():
                    errors.append(f"{path.relative_to(ROOT)}: `former_staff_routes[{index}].summary` must be a non-empty string")
    if not isinstance(data["latest_comms"], str):
        errors.append(f"{path.relative_to(ROOT)}: `latest_comms` must be a string")
    if not isinstance(data["latest_comms_date"], str):
        errors.append(f"{path.relative_to(ROOT)}: `latest_comms_date` must be a string")
    elif data["latest_comms_date"] and not DATE_RE.fullmatch(data["latest_comms_date"]):
        errors.append(f"{path.relative_to(ROOT)}: `latest_comms_date` must be YYYY-MM-DD")

    if isinstance(data["latest_comms"], str) and isinstance(data["latest_comms_date"], str):
        if data["latest_comms"] and not data["latest_comms_date"]:
            errors.append(f"{path.relative_to(ROOT)}: non-empty `latest_comms` requires `latest_comms_date`")
        if data["latest_comms_date"] and not data["latest_comms"]:
            errors.append(f"{path.relative_to(ROOT)}: non-empty `latest_comms_date` requires `latest_comms`")

    for field in ("chance_next", "chance_6m"):
        if not isinstance(data[field], str) or not PERCENT_RE.fullmatch(data[field]):
            errors.append(f"{path.relative_to(ROOT)}: `{field}` must be a percentage string")

    if isinstance(data["chance_next"], str) and PERCENT_RE.fullmatch(data["chance_next"]):
        if percent_value(data["chance_next"]) <= 0:
            errors.append(f"{path.relative_to(ROOT)}: `chance_next` must be positive")
    if isinstance(data["chance_6m"], str) and PERCENT_RE.fullmatch(data["chance_6m"]):
        if percent_value(data["chance_6m"]) < 1:
            errors.append(f"{path.relative_to(ROOT)}: `chance_6m` must be at least 1%")
    if (
        isinstance(data["chance_next"], str)
        and isinstance(data["chance_6m"], str)
        and PERCENT_RE.fullmatch(data["chance_next"])
        and PERCENT_RE.fullmatch(data["chance_6m"])
        and percent_value(data["chance_next"]) > percent_value(data["chance_6m"])
    ):
        errors.append(f"{path.relative_to(ROOT)}: `chance_next` must not exceed `chance_6m`")

    company_path = COMPANIES_DIR / path.name
    if not company_path.exists():
        errors.append(f"{path.relative_to(ROOT)}: missing canonical company file {company_path.relative_to(ROOT)}")
        return data

    company = load_json(company_path)
    staff_ids = {
        item.get("id")
        for item in company.get("staff", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    comms = [
        item for item in company.get("comms", {}).get("events", [])
        if isinstance(item, dict) and isinstance(item.get("summary"), str) and isinstance(item.get("date"), str)
    ]

    if isinstance(data["contacts"], list):
        for index, item in enumerate(data["contacts"]):
            if not isinstance(item, str) or not ID_RE.fullmatch(item):
                errors.append(f"{path.relative_to(ROOT)}: `contacts[{index}]` must be a {{id}} string")
                continue
            if item not in staff_ids:
                errors.append(f"{path.relative_to(ROOT)}: `contacts[{index}]` is not in canonical company staff")
            if not any(comm_mentions_person(comm["summary"], item) for comm in comms):
                errors.append(f"{path.relative_to(ROOT)}: `contacts[{index}]` is not mentioned in canonical company comms")

    if data["temperature"] != "cold" and isinstance(data["contacts"], list) and len(data["contacts"]) == 0:
        errors.append(f"{path.relative_to(ROOT)}: empty `contacts` requires `temperature` to be cold")

    if isinstance(data["contacts"], list) and len(data["contacts"]) == 0 and len(staff_ids) > 0:
        if any(comm_mentions_person(comm["summary"], sid) for sid in staff_ids for comm in comms):
            warn(warnings, path, "`contacts` is empty even though canonical company comms mention staff members")

    if data["latest_comms_date"]:
        latest_company_date = max((item["date"] for item in comms if DATE_RE.fullmatch(item["date"])), default="")
        if latest_company_date and data["latest_comms_date"] != latest_company_date:
            errors.append(f"{path.relative_to(ROOT)}: `latest_comms_date` must match the latest canonical company comm date")

    return data


def main():
    parser = argparse.ArgumentParser(description="Validate cache/companies JSON files")
    parser.add_argument("path", nargs="*", help="Optional path to a single cache/companies JSON file")
    parser.add_argument("--migration", action="store_true", help="suppress warning output for explicit migration runs")
    args = parser.parse_args()

    targets = resolve_target_paths(args.path)
    errors: list[str] = []
    warnings: list[str] = []

    if not args.path:
        company_ids = ids_in(COMPANIES_DIR)
        cache_ids = ids_in(CACHE_DIR)
        missing = sorted(company_ids - cache_ids)
        orphaned = sorted(cache_ids - company_ids)
        if missing:
            errors.append(f"missing cache files: {', '.join(missing)}")
        if orphaned:
            errors.append(f"orphaned cache files: {', '.join(orphaned)}")

    for path in targets:
        before = len(errors)
        data = validate(path, errors, warnings)
        if data is not None and len(errors) == before:
            dump_json(path, data)

    if errors:
        for message in errors:
            print(message, file=sys.stderr)
        raise SystemExit(1)

    if not args.migration:
        for message in warnings:
            print(f"WARNING: {message}", file=sys.stderr)

    print("OK")


if __name__ == "__main__":
    main()
