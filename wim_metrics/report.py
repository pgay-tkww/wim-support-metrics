from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

from wim_metrics.serialization import ExistingOutputError, read_json

FLOW_METRICS = ["resolved", "no_code", "duplicate"]
INVENTORY_METRICS = [
    "support_queue",
    "support_queue_new",
    "support_queue_one_week_old",
    "support_queue_two_weeks_old",
    "support_queue_one_month_old",
    "support_queue_two_months_old",
    "support_queue_three_months_old",
    "squad_queue",
    "squad_queue_new",
    "squad_queue_one_week_old",
    "squad_queue_two_weeks_old",
    "squad_queue_one_month_old",
    "squad_queue_two_months_old",
    "squad_queue_three_months_old",
]
CAPACITY_METRICS = ["squad_planned", "squad_in_progress", "squad_done"]
SQUAD_INVENTORY_METRICS = [
    "squad_queue",
    "squad_queue_new",
    "squad_queue_one_week_old",
    "squad_queue_two_weeks_old",
    "squad_queue_one_month_old",
    "squad_queue_two_months_old",
    "squad_queue_three_months_old",
]
HISTORICAL_METRICS = [
    "support_queue",
    "squad_queue",
    "resolved",
    "squad_planned",
    "squad_done",
]
EXECUTIVE_SUMMARY_METRICS = [
    ("General Queue", "support_queue"),
    ("Squad Queue", "squad_queue"),
    ("Squad Planned", "squad_planned"),
    ("Squad Done", "resolved"),
]
DISPLAY_TITLES = {
    "support_queue": "General Queue",
    "no_code": "Resolved without code",
    "duplicate": "Closed as duplicate",
}
AGE_LABELS = {
    "new": "new",
    "one_week_old": "> 1w",
    "two_weeks_old": "> 2w",
    "one_month_old": "> 1m",
    "two_months_old": "> 2m",
    "three_months_old": "> 3m",
}
SQUADS = ["Phoenix", "Unicorns"]


def _week_key(snapshot: dict[str, Any]) -> str:
    return str(snapshot.get("week", {}).get("key", ""))


def _metrics(snapshot: dict[str, Any]) -> dict[str, Any]:
    value = snapshot.get("metrics", {})
    return value if isinstance(value, dict) else {}


def _issues(snapshot: dict[str, Any]) -> dict[str, Any]:
    value = snapshot.get("issues", {})
    return value if isinstance(value, dict) else {}


def _metric(snapshot: dict[str, Any], metric_id: str) -> dict[str, Any]:
    value = _metrics(snapshot).get(metric_id, {})
    return value if isinstance(value, dict) else {}


def _metric_title(snapshot: dict[str, Any], metric_id: str) -> str:
    if metric_id in DISPLAY_TITLES:
        return DISPLAY_TITLES[metric_id]
    if metric_id.startswith("support_queue_"):
        bucket = metric_id.removeprefix("support_queue_")
        return f"General Queue ({AGE_LABELS.get(bucket, bucket)})"
    if metric_id.startswith("squad_queue_"):
        bucket = metric_id.removeprefix("squad_queue_")
        return f"Squad Queue ({AGE_LABELS.get(bucket, bucket)})"
    title = _metric(snapshot, metric_id).get("title")
    return str(title) if title else metric_id.replace("_", " ").title()


def _metric_count(snapshot: dict[str, Any], metric_id: str) -> int:
    count = _metric(snapshot, metric_id).get("count", 0)
    return count if isinstance(count, int) else 0


def _metric_issue_keys(snapshot: dict[str, Any], metric_id: str) -> list[str]:
    issue_keys = _metric(snapshot, metric_id).get("issues", [])
    if not isinstance(issue_keys, list):
        return []
    return sorted(str(issue_key) for issue_key in issue_keys)


def _issue_belongs_to_squad(snapshot: dict[str, Any], issue_key: str, squad: str) -> bool:
    issue = _issues(snapshot).get(issue_key, {})
    components = issue.get("components") if isinstance(issue, dict) else []
    return isinstance(components, list) and squad in components


def _metric_issue_keys_for_squad(
    snapshot: dict[str, Any], metric_id: str, squad: str
) -> list[str]:
    return [
        issue_key
        for issue_key in _metric_issue_keys(snapshot, metric_id)
        if _issue_belongs_to_squad(snapshot, issue_key, squad)
    ]


def _jira_base_url(snapshot: dict[str, Any], issue_keys: list[str]) -> str | None:
    for issue_key in issue_keys:
        issue = _issues(snapshot).get(issue_key, {})
        url = issue.get("url") if isinstance(issue, dict) else None
        if not isinstance(url, str) or not url:
            continue
        parsed = urlsplit(url)
        return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    return None


def _jira_search_link(snapshot: dict[str, Any], issue_keys: list[str]) -> str:
    base_url = _jira_base_url(snapshot, issue_keys)
    if base_url is None:
        return "query"
    jql = f"key in ({', '.join(issue_keys)})"
    return f'<a href="{base_url}/issues/?jql={quote(jql)}">query</a>'


def _count_cell(snapshot: dict[str, Any], metric_id: str) -> str:
    count = _metric_count(snapshot, metric_id)
    issue_keys = _metric_issue_keys(snapshot, metric_id)
    if not issue_keys:
        return str(count)
    return f"{count} ({_jira_search_link(snapshot, issue_keys)})"


def _count_cell_for_issue_keys(snapshot: dict[str, Any], issue_keys: list[str]) -> str:
    if not issue_keys:
        return "0"
    return f"{len(issue_keys)} ({_jira_search_link(snapshot, issue_keys)})"


def _total_cell(total_count: int, squad_count: int) -> str:
    if total_count == 0:
        return "0 (0%)"
    percentage = round((squad_count / total_count) * 100)
    return f"{total_count} ({percentage}%)"


def _render_metric_table(snapshot: dict[str, Any], metric_ids: list[str]) -> list[str]:
    lines = ["| Metric | Count |", "| --- | ---: |"]
    for metric_id in metric_ids:
        if metric_id not in _metrics(snapshot):
            continue
        lines.append(f"| {_metric_title(snapshot, metric_id)} | {_count_cell(snapshot, metric_id)} |")
    return lines


def _render_squad_metric_table(
    snapshot: dict[str, Any], squad: str, metric_rows: list[tuple[str, str]]
) -> list[str]:
    lines = [f"| Metric | {squad} | Total |", "| --- | ---: | ---: |"]
    for title, metric_id in metric_rows:
        if metric_id not in _metrics(snapshot):
            continue
        squad_issue_keys = _metric_issue_keys_for_squad(snapshot, metric_id, squad)
        total_count = _metric_count(snapshot, metric_id)
        lines.append(
            f"| {title} | "
            f"{_count_cell_for_issue_keys(snapshot, squad_issue_keys)} | "
            f"{_total_cell(total_count, len(squad_issue_keys))} |"
        )
    return lines


def _metric_rows(snapshot: dict[str, Any], metric_ids: list[str]) -> list[tuple[str, str]]:
    return [(_metric_title(snapshot, metric_id), metric_id) for metric_id in metric_ids]


def _render_squad_details(snapshot: dict[str, Any], squad: str) -> list[str]:
    lines = [
        "<details>",
        f"<summary>{squad}</summary>",
        "",
        "### Summary",
        "",
    ]
    lines.extend(
        _render_squad_metric_table(
            snapshot,
            squad,
            EXECUTIVE_SUMMARY_METRICS,
        )
    )
    lines.extend(["", "### Flow Metrics", ""])
    lines.extend(_render_squad_metric_table(snapshot, squad, _metric_rows(snapshot, FLOW_METRICS)))
    lines.extend(["", "### Inventory Metrics", ""])
    lines.extend(
        _render_squad_metric_table(
            snapshot, squad, _metric_rows(snapshot, SQUAD_INVENTORY_METRICS)
        )
    )
    lines.extend(["", "### Capacity Metrics", ""])
    lines.extend(_render_squad_metric_table(snapshot, squad, _metric_rows(snapshot, CAPACITY_METRICS)))
    lines.extend(["</details>"])
    return lines


def _format_delta(current: int, previous: int | None) -> str:
    if previous is None:
        return "n/a"
    delta = current - previous
    if delta > 0:
        return f"+{delta}"
    return str(delta)


def _historical_cell(
    current_snapshot: dict[str, Any],
    previous_snapshot: dict[str, Any] | None,
    metric_id: str,
) -> str:
    current = _metric_count(current_snapshot, metric_id)
    previous = _metric_count(previous_snapshot, metric_id) if previous_snapshot else None
    return f"{current} ({_format_delta(current, previous)})"


def render_weekly_report(snapshot: dict[str, Any]) -> str:
    week_key = _week_key(snapshot)
    lines = [
        f"# WIM Support Metrics - {week_key}",
        "",
        "## Executive Summary",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
    ]

    for title, metric_id in EXECUTIVE_SUMMARY_METRICS:
        lines.append(f"| {title} | {_count_cell(snapshot, metric_id)} |")

    lines.extend(["", "## Flow Metrics", ""])
    lines.extend(_render_metric_table(snapshot, FLOW_METRICS))
    lines.extend(["", "## Inventory Metrics", ""])
    lines.extend(_render_metric_table(snapshot, INVENTORY_METRICS))
    lines.extend(["", "## Capacity Metrics", ""])
    lines.extend(_render_metric_table(snapshot, CAPACITY_METRICS))
    lines.extend(["", "## Metrics by Squad", ""])
    for squad in SQUADS:
        lines.extend(_render_squad_details(snapshot, squad))
        lines.append("")

    return "\n".join(lines) + "\n"


def render_historical_summary(snapshots: list[dict[str, Any]]) -> str:
    latest = sorted(snapshots, key=_week_key)[-8:]
    if not latest:
        return "# WIM Support Metrics - Historical Summary\n\nNo snapshots available.\n"

    week_keys = [_week_key(snapshot) for snapshot in latest]
    lines = [
        "# WIM Support Metrics - Historical Summary",
        "",
        "Counts show delta versus previous available week.",
        "",
        "| Metric | " + " | ".join(week_keys) + " | Delta |",
        "| --- | " + " | ".join("---:" for _ in week_keys) + " | ---: |",
    ]

    for metric_id in HISTORICAL_METRICS:
        cells = [
            _historical_cell(snapshot, latest[index - 1] if index > 0 else None, metric_id)
            for index, snapshot in enumerate(latest)
        ]
        final_delta = _format_delta(
            _metric_count(latest[-1], metric_id),
            _metric_count(latest[-2], metric_id) if len(latest) > 1 else None,
        )
        lines.append(f"| {_metric_title(latest[-1], metric_id)} | " + " | ".join(cells) + f" | {final_delta} |")

    return "\n".join(lines) + "\n"


def write_weekly_report(
    week_key: str,
    snapshot_path: Path = Path("data/export"),
    report_dir: Path = Path("data/reports"),
    force: bool = False,
) -> Path:
    snapshot = read_json(snapshot_path / f"{week_key}.json")
    report_path = report_dir / f"{week_key}.md"
    if report_path.exists() and not force:
        raise ExistingOutputError(f"{report_path} already exists; use --force to overwrite")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_weekly_report(snapshot))
    return report_path
