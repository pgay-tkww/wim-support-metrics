from __future__ import annotations

from datetime import datetime
from typing import Any

from wim_metrics.week import ReportWeek

SQUAD_COMPONENTS = {"Phoenix", "Unicorns"}
SUPPORT_COMPONENT = "Support"

METRIC_TITLES = {
    "support_queue": "Support Queue",
    "squad_queue": "Squad Queue",
    "resolved": "Resolved",
    "no_code": "No Code",
    "duplicate": "Duplicate",
    "cancelled": "Cancelled",
    "squad_planned": "Squad Planned",
    "squad_in_progress": "Squad In Progress",
    "squad_done": "Squad Done",
}

BUCKET_TITLES = {
    "new": "New",
    "one_week_old": "One Week Old",
    "two_weeks_old": "Two Weeks Old",
    "one_month_old": "One Month Old",
    "two_months_old": "Two Months Old",
    "three_months_old": "Three Months Old",
}


def parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    if len(value) >= 5 and value[-5] in {"+", "-"} and value[-2:].isdigit():
        value = f"{value[:-2]}:{value[-2:]}"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Metric timestamp must include timezone offset")
    return parsed


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def age_bucket(age_days: int) -> str:
    if age_days < 7:
        return "new"
    if age_days < 14:
        return "one_week_old"
    if age_days < 30:
        return "two_weeks_old"
    if age_days < 60:
        return "one_month_old"
    if age_days < 90:
        return "two_months_old"
    return "three_months_old"


def sprint_overlaps_week(start_date: str | None, end_date: str | None, week: ReportWeek) -> bool:
    start = parse_dt(start_date)
    end = parse_dt(end_date)
    if start is None or end is None:
        return False
    return start < week.end_exclusive and end > week.start


def is_support_queue(issue: dict[str, Any]) -> bool:
    components = set(as_list(issue.get("components")))
    return SUPPORT_COMPONENT in components and components.isdisjoint(SQUAD_COMPONENTS)


def is_squad_queue(issue: dict[str, Any]) -> bool:
    components = set(as_list(issue.get("components")))
    return SUPPORT_COMPONENT in components and not components.isdisjoint(SQUAD_COMPONENTS)


def resolved_in_week(issue: dict[str, Any], week: ReportWeek) -> bool:
    resolved = parse_dt(issue.get("resolved_at"))
    return resolved is not None and week.start <= resolved < week.end_exclusive


def metric(title: str, keys: list[str]) -> dict[str, Any]:
    sorted_keys = sorted(keys)
    return {"title": title, "count": len(sorted_keys), "issues": sorted_keys}


def _bucket_title(metric_id: str) -> str:
    if metric_id.startswith("support_queue_"):
        return f"{METRIC_TITLES['support_queue']} ({BUCKET_TITLES[metric_id.removeprefix('support_queue_')]})"
    if metric_id.startswith("squad_queue_"):
        return f"{METRIC_TITLES['squad_queue']} ({BUCKET_TITLES[metric_id.removeprefix('squad_queue_')]})"
    raise KeyError(f"Unsupported bucket metric id: {metric_id}")


def calculate_metrics(issues: dict[str, dict[str, Any]], week: ReportWeek) -> dict[str, Any]:
    support_keys = [key for key, value in issues.items() if is_support_queue(value)]
    squad_keys = [key for key, value in issues.items() if is_squad_queue(value)]
    resolved_keys = [key for key, value in issues.items() if resolved_in_week(value, week)]

    result = {
        "support_queue": metric(METRIC_TITLES["support_queue"], support_keys),
        "squad_queue": metric(METRIC_TITLES["squad_queue"], squad_keys),
        "resolved": metric(METRIC_TITLES["resolved"], resolved_keys),
        "no_code": metric(
            METRIC_TITLES["no_code"],
            [key for key in resolved_keys if "wim-support:no-code" in as_list(issues[key].get("labels"))],
        ),
        "duplicate": metric(
            METRIC_TITLES["duplicate"],
            [key for key in resolved_keys if "wim-support:duplicate" in as_list(issues[key].get("labels"))],
        ),
        "cancelled": metric(
            METRIC_TITLES["cancelled"],
            [key for key in resolved_keys if "wim-support:cancelled" in as_list(issues[key].get("labels"))],
        ),
    }

    for queue_name, keys, date_field in [
        ("support_queue", support_keys, "assigned_to_support_at"),
        ("squad_queue", squad_keys, "assigned_to_squad_at"),
    ]:
        buckets: dict[str, list[str]] = {
            "new": [],
            "one_week_old": [],
            "two_weeks_old": [],
            "one_month_old": [],
            "two_months_old": [],
            "three_months_old": [],
        }
        for key in keys:
            raw_date = issues[key].get(date_field) or (
                issues[key].get("created_at") if date_field == "assigned_to_support_at" else None
            )
            assigned = parse_dt(raw_date)
            if assigned is None:
                continue
            age_days = (week.end_exclusive - assigned).days
            buckets[age_bucket(age_days)].append(key)
        for bucket, bucket_keys in buckets.items():
            metric_id = f"{queue_name}_{bucket}"
            result[metric_id] = metric(_bucket_title(metric_id), bucket_keys)

    planned_keys = [
        key
        for key in squad_keys
        if any(sprint.get("overlaps_selected_week") for sprint in as_list(issues[key].get("sprints")))
    ]
    result["squad_planned"] = metric(METRIC_TITLES["squad_planned"], planned_keys)
    result["squad_in_progress"] = metric(
        METRIC_TITLES["squad_in_progress"],
        [key for key in planned_keys if issues[key].get("status_category") == "In Progress"],
    )
    result["squad_done"] = metric(
        METRIC_TITLES["squad_done"],
        [key for key in planned_keys if issues[key].get("status_category") == "Done"],
    )
    return dict(sorted(result.items()))
