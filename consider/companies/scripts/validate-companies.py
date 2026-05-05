#!/usr/bin/env python3
import argparse
import calendar
import json
import re
import subprocess
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

from lib.queue_common import person_exists, project_exists

ABOUT_US_DIR = ROOT / "about-us"
if str(ABOUT_US_DIR) not in sys.path:
    sys.path.insert(0, str(ABOUT_US_DIR))

from rubrics import ALLOWED_RUBRIC_IDS

COMPANIES_DIR = ROOT / "companies"
COMPANIES_CACHE_DIR = ROOT / "cache" / "companies"
PROJECTS_DIR = ROOT / "projects"
CACHE_VALIDATOR = ROOT / ".agents" / "skills" / "cache" / "companies" / "scripts" / "validate-companies-cache.py"

FIELD_ORDER = [
    "name",
    "website",
    "twitter",
    "linkedin",
    "github",
    "staff",
    "related",
    "projects",
    "audits",
    "rubrics",
    "transitive_rubrics",
    "potential_intros_by",
    "introduced_by",
    "reserved_for",
    "comms",
]

MANDATORY_FIELDS = {
    "name",
    "website",
    "twitter",
    "linkedin",
    "github",
    "staff",
    "audits",
    "rubrics",
    "comms",
}

OPTIONAL_FIELDS = {"related", "projects", "transitive_rubrics", "potential_intros_by", "introduced_by", "reserved_for"}
ALLOWED_FIELDS = MANDATORY_FIELDS | OPTIONAL_FIELDS
ROLE_RE = re.compile(r"^[A-Z0-9_]+$")
ID_RE = re.compile(r"^\{[a-z0-9_]+\}$")
PROJECT_ID_RE = re.compile(r"^\{[a-z0-9_-]+\}$")
TIER_RE = re.compile(r"^(weak|medium|strong)$")
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PAST_DATE_RE = re.compile(r"^(\d{4}|\d{4}-\d{2}|\d{4}-\d{2}-\d{2})$")


def valid_where_value(value) -> bool:
    return isinstance(value, list) and len(value) > 0 and all(
        isinstance(item, str) and item.strip() and "/" not in item and "," not in item and " via " not in item.casefold()
        for item in value
    )

def err(errors, path, message):
    errors.append(f"{path.relative_to(ROOT)}: {message}")


def warn(warnings, path, message):
    warnings.append(f"{path.relative_to(ROOT)}: {message}")


def is_id(value: str) -> bool:
    return isinstance(value, str) and bool(ID_RE.fullmatch(value))


def id_points_to_entity(raw_id: str, all_companies) -> bool:
    if not is_id(raw_id):
        return False
    entity_id = raw_id[1:-1]
    return entity_id in all_companies or person_exists(entity_id)


def person_file_exists(person_id: str) -> bool:
    return person_exists(person_id)


def project_id_points_to_project(raw_id: str) -> bool:
    if not isinstance(raw_id, str) or not PROJECT_ID_RE.fullmatch(raw_id):
        return False
    project_id = raw_id[1:-1]
    return project_exists(project_id)


def past_bound_to_day(value: str, *, is_end: bool) -> str:
    if DAY_RE.fullmatch(value):
        return value
    if re.fullmatch(r"^\d{4}-\d{2}$", value):
        year, month = map(int, value.split("-"))
        day = calendar.monthrange(year, month)[1] if is_end else 1
        return f"{year:04d}-{month:02d}-{day:02d}"
    year = int(value)
    return f"{year:04d}-12-31" if is_end else f"{year:04d}-01-01"


def resolve_target_paths(raw_paths: list[str]) -> list[Path]:
    if not raw_paths:
        return sorted(COMPANIES_DIR.glob("*.json"))

    if len(raw_paths) != 1:
        raise SystemExit("Provide at most one company JSON path")

    raw = Path(raw_paths[0])
    path = raw if raw.is_absolute() else (ROOT / raw)
    path = path.resolve()

    if not path.exists():
        raise SystemExit(f"Path not found: {raw_paths[0]}")
    if not path.is_file():
        raise SystemExit(f"Not a file: {raw_paths[0]}")
    if path.suffix != ".json":
        raise SystemExit(f"Expected a .json file: {raw_paths[0]}")
    if path.parent != COMPANIES_DIR.resolve():
        raise SystemExit(f"Expected a file under companies/: {raw_paths[0]}")

    return [path]


def load_company_map():
    companies = {}
    for path in sorted(COMPANIES_DIR.glob("*.json")):
        try:
            companies[path.stem] = json.loads(path.read_text())
        except Exception:
            # Per-file parse errors are handled in the target validation pass.
            continue
    return companies


def validate_company(path, company_id, data, all_companies, errors, warnings):

    if not isinstance(data, dict):
        err(errors, path, "top-level JSON value must be an object")
        return

    unknown = [k for k in data.keys() if k not in ALLOWED_FIELDS]
    if unknown:
        err(errors, path, f"unknown fields: {', '.join(unknown)}")

    for field in MANDATORY_FIELDS:
        if field not in data:
            err(errors, path, f"missing mandatory field `{field}`")

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        err(errors, path, "`name` must be a non-empty string")

    for field in ["website", "twitter", "linkedin", "github"]:
        value = data.get(field)
        if not isinstance(value, str):
            err(errors, path, f"`{field}` must be a string")

    if all(isinstance(data.get(f), str) and data.get(f) == "" for f in ["website", "github", "linkedin", "twitter"]):
        err(errors, path, "all primary link fields are empty")
    elif sum(1 for f in ["website", "github", "linkedin", "twitter"] if isinstance(data.get(f), str) and data.get(f).strip()) == 1:
        warn(warnings, path, "only one of `website`, `github`, `linkedin`, or `twitter` is filled; enrich when possible")

    staff = data.get("staff")
    if not isinstance(staff, list):
        err(errors, path, "`staff` must be an array")
    else:
        for i, item in enumerate(staff):
            if not isinstance(item, dict):
                err(errors, path, f"`staff[{i}]` must be an object")
                continue
            if set(item.keys()) not in ({"id"}, {"id", "role"}):
                err(errors, path, f"`staff[{i}]` must contain `id` and optional `role` only")
            sid = item.get("id")
            if not is_id(sid):
                err(errors, path, f"`staff[{i}].id` must be a `{{id}}` string")
            else:
                pid = sid[1:-1]
                if not person_file_exists(pid):
                    err(errors, path, f"`staff[{i}].id` points to missing people file `{pid}`")
            if "role" in item and (not isinstance(item["role"], str) or not ROLE_RE.fullmatch(item["role"])):
                err(errors, path, f"`staff[{i}].role` must be a single upper-case token")

    related = data.get("related")
    if related is not None:
        if not isinstance(related, list) or len(related) == 0:
            err(errors, path, "`related` must be a non-empty array when present")
        else:
            for i, item in enumerate(related):
                if not is_id(item):
                    err(errors, path, f"`related[{i}]` must be a `{{id}}` string")
                    continue
                rid = item[1:-1]
                if rid == company_id:
                    err(errors, path, "`related` must not contain the company itself")
                if rid not in all_companies:
                    err(errors, path, f"`related[{i}]` points to missing company `{rid}`")
                else:
                    other = all_companies[rid].get("related", [])
                    backref = "{" + company_id + "}"
                    if backref not in other:
                        err(errors, path, f"`related` symmetry violated with `{rid}`")

    projects = data.get("projects")
    if projects is not None:
        if not isinstance(projects, list) or len(projects) == 0:
            err(errors, path, "`projects` must be a non-empty array when present")
        else:
            for i, item in enumerate(projects):
                if not isinstance(item, str) or not PROJECT_ID_RE.fullmatch(item):
                    err(errors, path, f"`projects[{i}]` must be a `{{id}}` string")
                elif not project_id_points_to_project(item):
                    err(errors, path, f"`projects[{i}]` points to missing project")
                else:
                    project_id = item[1:-1]
                    project_path = PROJECTS_DIR / f"{project_id}.json"
                    if project_path.exists():
                        try:
                            project = json.loads(project_path.read_text())
                        except Exception:
                            project = None
                        if isinstance(project, dict):
                            self_ref = "{" + company_id + "}"
                            if self_ref not in {project.get("contracting_company"), project.get("audited_company")}:
                                err(errors, path, f"`projects[{i}]` does not point back to this company in project canon")
            if len(set(projects)) != len(projects):
                err(errors, path, "`projects` must not contain duplicates")

    audits = data.get("audits")
    if not isinstance(audits, dict):
        err(errors, path, "`audits` must be an object")
    else:
        for key, value in audits.items():
            if not is_id(key):
                err(errors, path, f"`audits` key `{key}` must be a `{{id}}` string")
            elif key[1:-1] not in all_companies:
                err(errors, path, f"`audits` key `{key}` points to missing company")
            if not isinstance(value, int) or value < 1:
                err(errors, path, f"`audits[{key}]` must be a positive integer")

    rubrics = data.get("rubrics")
    if not isinstance(rubrics, list):
        err(errors, path, "`rubrics` must be an array")
    elif len(rubrics) == 0:
        err(errors, path, "`rubrics` must be non-empty")
    elif any(not isinstance(x, str) or not x for x in rubrics):
        err(errors, path, "`rubrics` must contain only non-empty strings")
    elif any(isinstance(x, str) and x.startswith("transitive_") for x in rubrics):
        err(errors, path, "`rubrics` must not contain `transitive_`-prefixed values; use `transitive_rubrics`")
    else:
        invalid_rubrics = [x for x in rubrics if x not in ALLOWED_RUBRIC_IDS]
        if invalid_rubrics:
            err(errors, path, f"`rubrics` contains unknown values: {', '.join(sorted(set(invalid_rubrics)))}")
        if len(set(rubrics)) != len(rubrics):
            err(errors, path, "`rubrics` must not contain duplicates")

    transitive_rubrics = data.get("transitive_rubrics")
    if transitive_rubrics is not None:
        if not isinstance(transitive_rubrics, list) or len(transitive_rubrics) == 0:
            err(errors, path, "`transitive_rubrics` must be a non-empty array when present")
        elif any(not isinstance(x, str) or not x for x in transitive_rubrics):
            err(errors, path, "`transitive_rubrics` must contain only non-empty strings")
        elif any(isinstance(x, str) and x.startswith("transitive_") for x in transitive_rubrics):
            err(errors, path, "`transitive_rubrics` items must be base rubric IDs, not `transitive_`-prefixed values")
        else:
            invalid_transitive = [x for x in transitive_rubrics if x not in ALLOWED_RUBRIC_IDS]
            if invalid_transitive:
                err(errors, path, f"`transitive_rubrics` contains unknown values: {', '.join(sorted(set(invalid_transitive)))}")
            if len(set(transitive_rubrics)) != len(transitive_rubrics):
                err(errors, path, "`transitive_rubrics` must not contain duplicates")
            if isinstance(rubrics, list):
                overlap = sorted(set(rubrics) & set(transitive_rubrics))
                if overlap:
                    err(errors, path, f"`rubrics` and `transitive_rubrics` must not overlap: {', '.join(overlap)}")

    pibs = data.get("potential_intros_by")
    if pibs is not None:
        if not isinstance(pibs, dict) or len(pibs) == 0:
            err(errors, path, "`potential_intros_by` must be a non-empty object when present")
        else:
            for key, value in pibs.items():
                if not is_id(key):
                    err(errors, path, f"`potential_intros_by` key `{key}` must be a `{{id}}` string")
                elif not id_points_to_entity(key, all_companies):
                    err(errors, path, f"`potential_intros_by` key `{key}` points to missing company/person")
                if not isinstance(value, str) or not TIER_RE.fullmatch(value):
                    err(errors, path, f"`potential_intros_by[{key}]` must be weak/medium/strong")

    introduced_by = data.get("introduced_by")
    if introduced_by is not None:
        if introduced_by != [] and not is_id(introduced_by):
            err(errors, path, "`introduced_by` must be a single `{id}` string or `[]` when present")
        elif is_id(introduced_by) and not id_points_to_entity(introduced_by, all_companies):
            err(errors, path, "`introduced_by` points to missing company/person")

    if isinstance(pibs, dict) and is_id(introduced_by):
        if introduced_by in pibs:
            err(errors, path, f"`potential_intros_by` and `introduced_by` must not overlap: {introduced_by}")

    reserved_for = data.get("reserved_for")
    if reserved_for is not None:
        if not is_id(reserved_for):
            err(errors, path, "`reserved_for` must be a non-empty `{id}` string when present")
        elif not id_points_to_entity(reserved_for, all_companies):
            err(errors, path, "`reserved_for` points to missing company/person")

    comms = data.get("comms")
    if not isinstance(comms, dict):
        err(errors, path, "`comms` must be an object")
    else:
        if set(comms.keys()) - {"events", "past"}:
            err(errors, path, "`comms` may contain only `events` and optional `past`")

        events = comms.get("events")
        if not isinstance(events, list):
            err(errors, path, "`comms.events` must be an array")
            events = []

        for i, item in enumerate(events):
            if not isinstance(item, dict):
                err(errors, path, f"`comms.events[{i}]` must be an object")
                continue
            if set(item.keys()) != {"date", "where", "summary"}:
                err(errors, path, f"`comms.events[{i}]` must contain exactly `date`, `where`, and `summary`")
            if not isinstance(item.get("date"), str) or not DAY_RE.fullmatch(item.get("date", "")):
                err(errors, path, f"`comms.events[{i}].date` must be an exact `YYYY-MM-DD` string")
            if not valid_where_value(item.get("where")):
                err(errors, path, f"`comms.events[{i}].where` must be a non-empty string array without inline comments")
            if not isinstance(item.get("summary"), str) or not item.get("summary").strip():
                err(errors, path, f"`comms.events[{i}].summary` must be a non-empty string")

        valid_event_dates = [
            item["date"]
            for item in events
            if isinstance(item, dict)
            and isinstance(item.get("date"), str)
            and DAY_RE.fullmatch(item["date"])
        ]
        if len(set(valid_event_dates)) != len(valid_event_dates):
            err(errors, path, "`comms.events` must not contain more than one entry for the same date")

        past = comms.get("past")
        if past is not None:
            if not isinstance(past, dict):
                err(errors, path, "`comms.past` must be an object when present")
            else:
                if set(past.keys()) != {"range", "summary"}:
                    err(errors, path, "`comms.past` must contain exactly `range` and `summary`")
                range_value = past.get("range")
                if not isinstance(range_value, list) or len(range_value) != 2:
                    err(errors, path, "`comms.past.range` must be a two-item array")
                else:
                    for idx, value in enumerate(range_value):
                        if not isinstance(value, str) or not PAST_DATE_RE.fullmatch(value):
                            err(errors, path, f"`comms.past.range[{idx}]` must be `YYYY`, `YYYY-MM`, or `YYYY-MM-DD`")
                if (
                    isinstance(range_value, list)
                    and len(range_value) == 2
                    and all(isinstance(value, str) and PAST_DATE_RE.fullmatch(value) for value in range_value)
                ):
                    start_day = past_bound_to_day(range_value[0], is_end=False)
                    end_day = past_bound_to_day(range_value[1], is_end=True)
                    if start_day > end_day:
                        err(errors, path, "`comms.past.range` must be ordered from earlier to later")
                    if events:
                        earliest_event_date = min(
                            item["date"]
                            for item in events
                            if isinstance(item, dict)
                            and isinstance(item.get("date"), str)
                            and DAY_RE.fullmatch(item["date"])
                        )
                        if end_day >= earliest_event_date:
                            err(errors, path, "`comms.past.range` must end before the earliest `comms.events` date")
                    if not isinstance(past.get("summary"), str) or not past.get("summary").strip():
                        err(errors, path, "`comms.past.summary` must be a non-empty string")


def ordered_company(data):
    ordered = OrderedDict()
    for key in FIELD_ORDER:
        if key in data:
            if key == "comms":
                ordered[key] = ordered_comms(data[key])
            else:
                if key == "staff" and isinstance(data[key], list):
                    ordered[key] = [ordered_staff_item(item) if isinstance(item, dict) else item for item in data[key]]
                else:
                    ordered[key] = data[key]
    return ordered


def comm_sort_key(item):
    return (item.get("date", ""), item.get("summary", ""))


def ordered_event(item):
    ordered = OrderedDict()
    for key in ["date", "where", "summary"]:
        if key in item:
            ordered[key] = item[key]
    return ordered


def ordered_staff_item(item):
    ordered = OrderedDict()
    for key in ["id", "role"]:
        if key in item:
            ordered[key] = item[key]
    return ordered


def ordered_comms(comms):
    ordered = OrderedDict()
    events = comms.get("events", [])
    ordered["events"] = [ordered_event(item) if isinstance(item, dict) else item for item in sorted(events, key=comm_sort_key, reverse=True)]
    if "past" in comms:
        past = comms["past"]
        if isinstance(past, dict):
            ordered["past"] = OrderedDict((key, past[key]) for key in ("range", "summary") if key in past)
        else:
            ordered["past"] = past
    return ordered


def validate_matching_cache(path: Path) -> list[str]:
    cache_path = COMPANIES_CACHE_DIR / path.name
    cp = subprocess.run(
        [sys.executable, str(CACHE_VALIDATOR), str(cache_path)],
        text=True,
        capture_output=True,
        cwd=ROOT,
    )
    if cp.returncode == 0:
        return []

    lines = [line.strip() for line in (cp.stderr or "").splitlines() if line.strip()]
    if not lines:
        lines = [line.strip() for line in (cp.stdout or "").splitlines() if line.strip()]
    if not lines:
        lines = [f"{path.relative_to(ROOT)}: matching cache validation failed"]
    return lines


def main():
    parser = argparse.ArgumentParser(description="Validate company JSON files")
    parser.add_argument("path", nargs="*", help="Optional path to a single companies/*.json file")
    parser.add_argument("--migration", action="store_true", help="suppress warning output for explicit migration runs")
    args = parser.parse_args()

    target_paths = resolve_target_paths(args.path)
    all_companies = load_company_map()
    errors = []
    warnings = []

    for path in target_paths:
        company_id = path.stem
        file_errors = []
        try:
            data = json.loads(path.read_text())
        except Exception as exc:
            err(errors, path, f"failed to parse JSON: {exc}")
            continue

        validate_company(path, company_id, data, all_companies, file_errors, warnings)
        if file_errors:
            errors.extend(file_errors)
            continue

        path.write_text(json.dumps(ordered_company(data), indent=2, ensure_ascii=False) + "\n")
        cache_errors = validate_matching_cache(path)
        if cache_errors:
            errors.extend(cache_errors)

    if not args.path:
        company_projects = {
            company_id: set(item[1:-1] for item in data.get("projects", []))
            for company_id, data in all_companies.items()
            if isinstance(data, dict)
        }
        for project_path in sorted(PROJECTS_DIR.glob("*.json")):
            try:
                project = json.loads(project_path.read_text())
            except Exception:
                continue
            if not isinstance(project, dict):
                continue
            project_id = project_path.stem
            for field in ("contracting_company", "audited_company"):
                ref = project.get(field)
                if not is_id(ref):
                    continue
                company_id = ref[1:-1]
                if project_id not in company_projects.get(company_id, set()):
                    err(errors, project_path, f"`{field}` company `{company_id}` must include `{{{project_id}}}` in its `projects` field")

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
