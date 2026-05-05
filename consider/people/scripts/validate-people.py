#!/usr/bin/env python3
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
PEOPLE_DIR = ROOT / "people"
COMPANIES_DIR = ROOT / "companies"

FIELD_ORDER = [
    "name",
    "linkedin",
    "telegram",
    "twitter",
    "email",
    "links",
    "location",
    "languages",
    "summary",
    "companies",
    "current_start",
    "skills",
    "comms",
    "past_career",
]

MANDATORY_FIELDS = {
    "name",
    "companies",
    "current_start",
    "past_career",
    "comms",
}

OPTIONAL_FIELDS = {
    "linkedin",
    "telegram",
    "twitter",
    "email",
    "links",
    "location",
    "languages",
    "skills",
    "summary",
}

ALLOWED_FIELDS = MANDATORY_FIELDS | OPTIONAL_FIELDS
ID_RE = re.compile(r"^\{[a-z0-9_]+\}$")
ID_TOKEN_RE = re.compile(r"\{[a-z0-9_]+\}")
DATE_RE = re.compile(r"^\d{4}(-\d{2})?$")
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL_RE = re.compile(r"^https?://\S+$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ROLE_RE = re.compile(r"^[A-Z0-9_]+$")
TELEGRAM_RE = re.compile(r"^@[A-Za-z0-9_]{5,32}$")


def err(errors, path, message):
    errors.append(f"{path.relative_to(ROOT)}: {message}")


def warn(warnings, path, message):
    warnings.append(f"{path.relative_to(ROOT)}: {message}")


def is_company_ref(value) -> bool:
    return isinstance(value, str) and bool(ID_RE.fullmatch(value)) and (COMPANIES_DIR / f"{value[1:-1]}.json").exists()


def is_role_list(value) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and ROLE_RE.fullmatch(item) for item in value)


def company_id_from_ref(value) -> str | None:
    if is_company_ref(value):
        return value[1:-1]
    return None


def valid_current_company_value(value) -> bool:
    return isinstance(value, str) and (value == "" or bool(value.strip()))


def looks_like_id_ref(value) -> bool:
    return isinstance(value, str) and value.startswith("{") and value.endswith("}")


def embedded_id_refs(value) -> list[str]:
    if not isinstance(value, str):
        return []
    return ID_TOKEN_RE.findall(value)


def valid_past_company_value(value) -> bool:
    return value == [] or valid_current_company_value(value)


def valid_where_value(value) -> bool:
    return isinstance(value, list) and len(value) > 0 and all(
        isinstance(item, str) and item.strip() and "/" not in item and "," not in item and " via " not in item.casefold()
        for item in value
    )


def validate_comms(path: Path, comms, errors):
    if not isinstance(comms, dict):
        err(errors, path, "`comms` must be an object")
        return
    if set(comms.keys()) - {"events", "past"}:
        err(errors, path, "`comms` may only contain `events` and optional `past`")
    events = comms.get("events")
    if not isinstance(events, list):
        err(errors, path, "`comms.events` must be an array")
    else:
        seen_dates = set()
        prev = None
        for i, item in enumerate(events):
            if not isinstance(item, dict):
                err(errors, path, f"`comms.events[{i}]` must be an object")
                continue
            if set(item.keys()) != {"date", "where", "summary"}:
                err(errors, path, f"`comms.events[{i}]` must contain exactly `date`, `where`, and `summary`")
                continue
            date = item.get("date")
            where = item.get("where")
            summary = item.get("summary")
            if not isinstance(date, str) or not DAY_RE.fullmatch(date):
                err(errors, path, f"`comms.events[{i}].date` must be YYYY-MM-DD")
            if not valid_where_value(where):
                err(errors, path, f"`comms.events[{i}].where` must be a non-empty string array without inline comments")
            if not isinstance(summary, str) or not summary.strip():
                err(errors, path, f"`comms.events[{i}].summary` must be a non-empty string")
            if isinstance(date, str) and DAY_RE.fullmatch(date):
                if date in seen_dates:
                    err(errors, path, f"`comms.events` must not contain duplicate date `{date}`")
                seen_dates.add(date)
                if prev is not None and date > prev:
                    err(errors, path, "`comms.events` must be sorted from most recent to oldest")
                prev = date

    past = comms.get("past")
    if past is not None:
        if not isinstance(past, list) or len(past) == 0:
            err(errors, path, "`comms.past` must be a non-empty array when present")
        else:
            for i, item in enumerate(past):
                if not isinstance(item, dict):
                    err(errors, path, f"`comms.past[{i}]` must be an object")
                    continue
                if set(item.keys()) != {"when", "where", "summary"}:
                    err(errors, path, f"`comms.past[{i}]` must contain exactly `when`, `where`, and `summary`")
                    continue
                when = item.get("when")
                where = item.get("where")
                summary = item.get("summary")
                if not isinstance(when, str) or not when.strip():
                    err(errors, path, f"`comms.past[{i}].when` must be a non-empty string")
                if not valid_where_value(where):
                    err(errors, path, f"`comms.past[{i}].where` must be a non-empty string array without inline comments")
                if not isinstance(summary, str) or not summary.strip():
                    err(errors, path, f"`comms.past[{i}].summary` must be a non-empty string")


def validate_person(path: Path, data, errors, warnings):
    if not isinstance(data, dict):
        err(errors, path, "top-level JSON value must be an object")
        return

    unknown = [k for k in data.keys() if k not in ALLOWED_FIELDS]
    if unknown:
        err(errors, path, f"unknown fields: {', '.join(unknown)}")

    for field in MANDATORY_FIELDS:
        if field not in data:
            err(errors, path, f"missing mandatory field `{field}`")

    if not isinstance(data.get("name"), str) or not data.get("name", "").strip():
        err(errors, path, "`name` must be a non-empty string")
    elif "(" in data["name"] or ")" in data["name"]:
        warn(warnings, path, "`name` contains qualifier metadata; prefer the person's actual name only")

    surfaces = 0
    for field in ("linkedin", "telegram", "twitter", "email"):
        value = data.get(field)
        if value is None:
            continue
        if not isinstance(value, str):
            err(errors, path, f"`{field}` must be a string when present")
            continue
        if value.strip():
            surfaces += 1
        if field == "linkedin" and value and not URL_RE.fullmatch(value):
            err(errors, path, "`linkedin` must be an http(s) URL when non-empty")
        if field == "telegram" and value and not TELEGRAM_RE.fullmatch(value):
            err(errors, path, "`telegram` must be a canonical `@username` when non-empty")
        if field == "twitter" and value and not URL_RE.fullmatch(value):
            err(errors, path, "`twitter` must be an http(s) URL when non-empty")
        if field == "email" and value and not EMAIL_RE.fullmatch(value):
            err(errors, path, "`email` must be a valid email address when non-empty")
    if surfaces == 0:
        err(errors, path, "at least one of `linkedin`, `telegram`, `twitter`, or `email` must be non-empty")

    location = data.get("location")
    if location is not None and (not isinstance(location, str) or not location.strip()):
        err(errors, path, "`location` must be a non-empty string when present")

    languages = data.get("languages")
    if languages is not None:
        if not isinstance(languages, list) or len(languages) == 0:
            err(errors, path, "`languages` must be a non-empty array when present")
        else:
            seen_languages = set()
            for i, item in enumerate(languages):
                if not isinstance(item, str) or not item.strip():
                    err(errors, path, f"`languages[{i}]` must be a non-empty string")
                elif item == "English":
                    err(errors, path, "`languages` must not include `English`; English is assumed by default")
                elif item in seen_languages:
                    err(errors, path, "`languages` must not contain duplicates")
                else:
                    seen_languages.add(item)

    links = data.get("links")
    if links is not None:
        if not isinstance(links, list) or len(links) == 0:
            err(errors, path, "`links` must be a non-empty array when present")
        else:
            seen_links = set()
            for i, item in enumerate(links):
                if not isinstance(item, str) or not item.strip():
                    err(errors, path, f"`links[{i}]` must be a non-empty string")
                elif not URL_RE.fullmatch(item):
                    err(errors, path, f"`links[{i}]` must be an http(s) URL")
                elif item in seen_links:
                    err(errors, path, "`links` must not contain duplicates")
                else:
                    seen_links.add(item)

    companies = data.get("companies")
    current_company_ids = []
    if not isinstance(companies, list):
        err(errors, path, "`companies` must be an array")
    elif companies == []:
        warn(warnings, path, "`companies` is empty; research and enrich when possible")
    else:
        seen_companies = set()
        for i, item in enumerate(companies):
            if not isinstance(item, dict):
                err(errors, path, f"`companies[{i}]` must be an object")
                continue
            if set(item.keys()) != {"company", "role"}:
                err(errors, path, f"`companies[{i}]` must contain exactly `company` and `role`")
                continue
            company = item.get("company")
            role = item.get("role")
            company_id = company_id_from_ref(company)
            refs = embedded_id_refs(company)
            if not valid_current_company_value(company):
                err(errors, path, f"`companies[{i}].company` must be a string: `{{company_id}}`, a company name, or empty string for stealth startups")
            elif company == "" and role == []:
                err(errors, path, f"`companies[{i}].company` empty string is only valid for stealth/pre-public affiliations with a non-empty role")
            elif len(refs) > 1:
                err(errors, path, f"`companies[{i}].company` must not contain more than one `{{id}}` reference")
            elif len(refs) == 1 and company != refs[0]:
                err(errors, path, f"`companies[{i}].company` must not mix a `{{id}}` reference with free-form text")
            elif looks_like_id_ref(company) and company_id is None:
                err(errors, path, f"`companies[{i}].company` looks like an id reference but does not resolve to a tracked company")
            elif company_id is None:
                pass
            elif company_id in seen_companies:
                err(errors, path, f"`companies` must not contain duplicate company `{company_id}`")
            else:
                seen_companies.add(company_id)
                current_company_ids.append(company_id)
            if not is_role_list(role):
                err(errors, path, f"`companies[{i}].role` must be an array of canonical role codes")
            elif len(set(role)) != len(role):
                err(errors, path, f"`companies[{i}].role` must not contain duplicates")
            elif role == []:
                warn(warnings, path, f"`companies[{i}].role` is empty; research and enrich when possible")

    current_start = data.get("current_start")
    if current_start != [] and (not isinstance(current_start, str) or not DATE_RE.fullmatch(current_start)):
        err(errors, path, "`current_start` must be `[]` or YYYY / YYYY-MM")
    elif current_start == []:
        warn(warnings, path, "`current_start` is empty; research and enrich when possible")

    past_career = data.get("past_career")
    if not isinstance(past_career, list):
        err(errors, path, "`past_career` must be an array")
    else:
        if past_career == []:
            warn(warnings, path, "`past_career` is empty; research and enrich when possible")
        for i, item in enumerate(past_career):
            if not isinstance(item, dict):
                err(errors, path, f"`past_career[{i}]` must be an object")
                continue
            if not set(item.keys()).issubset({"company", "role", "from", "to"}):
                err(errors, path, f"`past_career[{i}]` may only contain `company`, `role`, `from`, and `to`")
            past_company = item.get("company")
            refs = embedded_id_refs(past_company)
            if "company" in item and not valid_past_company_value(past_company):
                err(errors, path, f"`past_career[{i}].company` must be `[]`, a valid `{{company_id}}` reference, or a company name")
            elif "company" in item and len(refs) > 1:
                err(errors, path, f"`past_career[{i}].company` must not contain more than one `{{id}}` reference")
            elif "company" in item and len(refs) == 1 and past_company != refs[0]:
                err(errors, path, f"`past_career[{i}].company` must not mix a `{{id}}` reference with free-form text")
            elif "company" in item and looks_like_id_ref(past_company) and not is_company_ref(past_company):
                err(errors, path, f"`past_career[{i}].company` looks like an id reference but does not resolve to a tracked company")
            if "role" in item and not is_role_list(item["role"]):
                err(errors, path, f"`past_career[{i}].role` must be an array of canonical role codes")
            if "from" in item and (not isinstance(item["from"], str) or not DATE_RE.fullmatch(item["from"])):
                err(errors, path, f"`past_career[{i}].from` must be YYYY / YYYY-MM")
            if "to" in item and item["to"] != [] and (not isinstance(item["to"], str) or not DATE_RE.fullmatch(item["to"])):
                err(errors, path, f"`past_career[{i}].to` must be `[]` or YYYY / YYYY-MM")
        for i in range(len(past_career) - 1):
            current_item = past_career[i]
            next_item = past_career[i + 1]
            if not isinstance(current_item, dict) or not isinstance(next_item, dict):
                continue
            current_company = current_item.get("company")
            next_company = next_item.get("company")
            if (
                isinstance(current_company, str)
                and isinstance(next_company, str)
                and current_company == next_company
                and is_company_ref(current_company)
            ):
                err(errors, path, f"`past_career[{i}]` and `past_career[{i + 1}]` repeat the same company; fold adjacent company periods into one item keeping only the latest role")

        if current_company_ids and len(past_career) > 0 and isinstance(past_career[0], dict):
            latest_past_company = past_career[0].get("company")
            latest_past_to = past_career[0].get("to")
            if company_id_from_ref(latest_past_company) in current_company_ids:
                if current_start == [] or latest_past_to in (None, []):
                    err(errors, path, "current company repeats the latest `past_career` company without enough gap evidence; fold them unless this is a proven rejoin")
                elif isinstance(latest_past_to, str) and isinstance(current_start, str) and latest_past_to >= current_start:
                    err(errors, path, "current company repeats the latest `past_career` company without a gap; fold them into the current role unless this is a proven rejoin")

    skills = data.get("skills")
    if skills is not None:
        if not isinstance(skills, list) or len(skills) == 0:
            err(errors, path, "`skills` must be a non-empty array when present")
        else:
            for i, item in enumerate(skills):
                if not isinstance(item, str) or not item.strip():
                    err(errors, path, f"`skills[{i}]` must be a non-empty string")
                elif len(item.split()) > 2:
                    err(errors, path, f"`skills[{i}]` should stay short (1-2 words)")
            if len(set(skills)) != len(skills):
                err(errors, path, "`skills` must not contain duplicates")

    summary = data.get("summary")
    if summary is not None and (not isinstance(summary, str) or not summary.strip()):
        err(errors, path, "`summary` must be a non-empty string when present")
    elif summary is None:
        warn(warnings, path, "`summary` is missing; enrich when possible")

    for item in companies if isinstance(companies, list) else []:
        if not isinstance(item, dict):
            continue
        company_id = company_id_from_ref(item.get("company"))
        role = item.get("role")
        if company_id is None or not is_role_list(role):
            continue
        company_data = json.loads((COMPANIES_DIR / f"{company_id}.json").read_text(encoding="utf-8"))
        staff = company_data.get("staff", [])
        person_ref = "{" + path.stem + "}"
        staff_entry = next(
            (
                item for item in staff
                if isinstance(item, dict) and item.get("id") == person_ref
            ),
            None,
        )
        if staff_entry is None:
            err(errors, path, f"`companies` points to `{company_id}` but the person is missing from that company's `staff`")
        elif "role" in staff_entry:
            staff_role = staff_entry.get("role")
            if isinstance(staff_role, str) and staff_role not in role:
                err(errors, path, f"`companies` role must include company staff role `{staff_role}` from `{company_id}`")
    validate_comms(path, data.get("comms"), errors)


def ordered_event(item: dict) -> OrderedDict:
    out = OrderedDict()
    for field in ("date", "where", "summary"):
        if field in item:
            out[field] = item[field]
    return out


def event_sort_key(item: dict) -> tuple[str, str]:
    return (str(item.get("date", "")), str(item.get("summary", "")))


def ordered_past_item(item: dict) -> OrderedDict:
    out = OrderedDict()
    for field in ("when", "where", "summary"):
        if field in item:
            out[field] = item[field]
    return out


def ordered_career_item(item: dict) -> OrderedDict:
    out = OrderedDict()
    for field in ("company", "role", "from", "to"):
        if field in item:
            out[field] = item[field]
    return out


def ordered_current_company_item(item: dict) -> OrderedDict:
    out = OrderedDict()
    for field in ("company", "role"):
        if field in item:
            out[field] = item[field]
    return out


def ordered_comms(comms: dict) -> OrderedDict:
    out = OrderedDict()
    events = comms.get("events", [])
    out["events"] = [ordered_event(item) if isinstance(item, dict) else item for item in sorted(events, key=event_sort_key, reverse=True)]
    if "past" in comms:
        past = comms["past"]
        out["past"] = [ordered_past_item(item) if isinstance(item, dict) else item for item in past]
    return out


def reorder(data: dict) -> OrderedDict:
    out = OrderedDict()
    for field in FIELD_ORDER:
        if field not in data:
            continue
        if field == "comms" and isinstance(data[field], dict):
            out[field] = ordered_comms(data[field])
        elif field == "companies" and isinstance(data[field], list):
            out[field] = [ordered_current_company_item(item) if isinstance(item, dict) else item for item in data[field]]
        elif field == "past_career" and isinstance(data[field], list):
            out[field] = [ordered_career_item(item) if isinstance(item, dict) else item for item in data[field]]
        else:
            out[field] = data[field]
    return out


def iter_target_paths(raw_paths: list[str]) -> list[Path]:
    if not raw_paths:
        return sorted(PEOPLE_DIR.glob("*.json"))
    if len(raw_paths) != 1:
        raise SystemExit("Provide at most one people JSON path")
    raw = Path(raw_paths[0])
    path = raw if raw.is_absolute() else (ROOT / raw)
    path = path.resolve()
    if not path.exists():
        raise SystemExit(f"Path not found: {raw_paths[0]}")
    if not path.is_file() or path.suffix != ".json":
        raise SystemExit(f"Expected a .json file: {raw_paths[0]}")
    if path.parent != PEOPLE_DIR.resolve():
        raise SystemExit(f"Expected a file under people/: {raw_paths[0]}")
    return [path]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--migration", action="store_true", help="suppress warning output for explicit migration runs")
    args = parser.parse_args(argv)
    target_paths = iter_target_paths(args.paths)

    errors = []
    warnings = []
    valid = []
    for path in target_paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            err(errors, path, f"invalid JSON: {exc}")
            continue
        validate_person(path, data, errors, warnings)
        if not any(e.startswith(f"{path.relative_to(ROOT)}:") for e in errors):
            valid.append((path, data))

    for path, data in valid:
        path.write_text(json.dumps(reorder(data), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if errors:
        for message in errors:
            print(message)
        return 1

    if not args.migration:
        for message in warnings:
            print(f"WARNING: {message}", file=sys.stderr)

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
