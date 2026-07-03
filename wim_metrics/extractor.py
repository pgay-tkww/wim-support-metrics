from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from wim_metrics.metrics import calculate_metrics, sprint_overlaps_week
from wim_metrics.serialization import write_json
from wim_metrics.week import ReportWeek

BASE_JQL = "project = GPWIM AND component in (Support)"
DEFAULT_SPRINT_FIELD = "customfield_10261"
JIRA_FIELDS = [
    "summary",
    "status",
    "assignee",
    "components",
    "labels",
    "created",
    "resolutiondate",
]

_SQUAD_COMPONENTS = {"Phoenix", "Unicorns"}
_LEGACY_SPRINT_ID_RE = re.compile(r"\bid=(\d+)\b")


def _split_component_names(value: str | None) -> set[str]:
    if not value:
        return set()
    return {part.strip() for part in value.split(",") if part.strip()}


def extract_assignment_dates(changelog: list[dict[str, Any]]) -> dict[str, str | None]:
    assigned_to_support_at: str | None = None
    assigned_to_squad_at: str | None = None
    components: set[str] = set()

    for history in changelog:
        created = history.get("created")
        for item in history.get("items", []):
            field_name = str(item.get("field", "")).strip().lower()
            if not field_name.startswith("component"):
                continue

            before = _split_component_names(item.get("fromString"))
            after = _split_component_names(item.get("toString"))
            was_squad_queue = "Support" in components and bool(
                components.intersection(_SQUAD_COMPONENTS)
            )

            for component in before:
                components.discard(component)
            components.update(after)

            added = after - before
            is_squad_queue = "Support" in components and bool(
                components.intersection(_SQUAD_COMPONENTS)
            )

            if assigned_to_support_at is None and "Support" in added:
                assigned_to_support_at = created

            if assigned_to_squad_at is None and not was_squad_queue and is_squad_queue:
                assigned_to_squad_at = created

    return {
        "assigned_to_support_at": assigned_to_support_at,
        "assigned_to_squad_at": assigned_to_squad_at,
    }


def _collect_sprint_ids(value: Any, sprint_ids: set[int]) -> None:
    if isinstance(value, dict):
        sprint_id = value.get("id")
        if isinstance(sprint_id, int):
            sprint_ids.add(sprint_id)
        elif isinstance(sprint_id, str) and sprint_id.isdigit():
            sprint_ids.add(int(sprint_id))

        for item in value.values():
            _collect_sprint_ids(item, sprint_ids)
        return

    if isinstance(value, (list, tuple)):
        for item in value:
            _collect_sprint_ids(item, sprint_ids)
        return

    if isinstance(value, str):
        for match in _LEGACY_SPRINT_ID_RE.finditer(value):
            sprint_ids.add(int(match.group(1)))


def jira_fields(sprint_field: str = DEFAULT_SPRINT_FIELD) -> list[str]:
    return [*JIRA_FIELDS, sprint_field]


def extract_sprint_ids(raw_issue: dict[str, Any], sprint_field: str = DEFAULT_SPRINT_FIELD) -> list[int]:
    sprint_ids: set[int] = set()
    sprint_field_value = raw_issue.get("fields", {}).get(sprint_field)

    _collect_sprint_ids(sprint_field_value, sprint_ids)

    return sorted(sprint_ids)


def build_issue_snapshot(
    raw_issue: dict[str, Any],
    changelog: list[dict[str, Any]],
    sprint_lookup: dict[int, dict[str, Any]],
    week: ReportWeek,
    jira_base_url: str,
    sprint_field: str = DEFAULT_SPRINT_FIELD,
) -> dict[str, Any]:
    fields = raw_issue.get("fields", {})
    status = fields.get("status") or {}
    assignee = fields.get("assignee") or {}
    assignment_dates = extract_assignment_dates(changelog)
    components = sorted(
        component.get("name")
        for component in fields.get("components", [])
        if component.get("name")
    )
    is_current_squad_issue = "Support" in components and bool(
        set(components).intersection(_SQUAD_COMPONENTS)
    )
    assigned_to_squad_at = assignment_dates["assigned_to_squad_at"]
    if assigned_to_squad_at is None and is_current_squad_issue:
        assigned_to_squad_at = (
            assignment_dates["assigned_to_support_at"] or fields.get("created")
        )

    sprints = []
    issue_key = raw_issue["key"]
    for sprint_id in extract_sprint_ids(raw_issue, sprint_field):
        sprint = sprint_lookup.get(sprint_id)
        if sprint is None:
            raise RuntimeError(
                f"Missing sprint metadata for issue {issue_key}: sprint {sprint_id}"
            )
        start_date = sprint.get("startDate")
        end_date = sprint.get("endDate")
        sprints.append(
            {
                "id": sprint_id,
                "name": sprint.get("name"),
                "state": sprint.get("state"),
                "start_date": start_date,
                "end_date": end_date,
                "overlaps_selected_week": sprint_overlaps_week(start_date, end_date, week),
            }
        )

    return {
        "key": issue_key,
        "summary": fields.get("summary", ""),
        "url": f"{jira_base_url.rstrip('/')}/browse/{issue_key}",
        "status": status.get("name", ""),
        "status_category": (status.get("statusCategory") or {}).get("name", ""),
        "assignee": assignee.get("displayName"),
        "components": components,
        "labels": sorted(fields.get("labels") or []),
        "created_at": fields.get("created"),
        "resolved_at": fields.get("resolutiondate"),
        "assigned_to_support_at": assignment_dates["assigned_to_support_at"],
        "assigned_to_squad_at": assigned_to_squad_at,
        "sprints": sprints,
    }


def extract_week(
    week: ReportWeek,
    jira_client: Any,
    output_dir: Path = Path("data/export"),
    force: bool = False,
    sprint_field: str = DEFAULT_SPRINT_FIELD,
) -> Path:
    raw_issues = jira_client.search_issues(BASE_JQL, jira_fields(sprint_field))

    changelogs: dict[str, list[dict[str, Any]]] = {}
    sprint_ids: set[int] = set()
    for raw_issue in raw_issues:
        issue_key = raw_issue["key"]
        changelogs[issue_key] = jira_client.get_issue_changelog(issue_key)
        sprint_ids.update(extract_sprint_ids(raw_issue, sprint_field))

    sprint_lookup = {
        sprint_id: jira_client.get_sprint(sprint_id)
        for sprint_id in sorted(sprint_ids)
    }

    jira_base_url = getattr(jira_client, "base_url", "")
    if not isinstance(jira_base_url, str) or not jira_base_url.strip():
        raise RuntimeError("Jira client must expose a non-empty base_url")

    issues = {
        raw_issue["key"]: build_issue_snapshot(
            raw_issue,
            changelogs[raw_issue["key"]],
            sprint_lookup,
            week,
            jira_base_url,
            sprint_field,
        )
        for raw_issue in sorted(raw_issues, key=lambda issue: issue["key"])
    }

    snapshot = {
        "schema_version": 1,
        "week": {
            "key": week.key,
            "iso_year": week.iso_year,
            "iso_week": week.iso_week,
            "start_date": week.display_start_date,
            "end_date": week.display_end_date,
            "timezone": "Europe/Madrid",
        },
        "source": {
            "jira_base_jql": BASE_JQL,
            "project_key": "GPWIM",
            "support_component": "Support",
            "squad_components": ["Phoenix", "Unicorns"],
        },
        "issues": issues,
        "metrics": calculate_metrics(issues, week),
    }

    snapshot_path = output_dir / f"{week.key}.json"
    write_json(snapshot_path, snapshot, force=force)
    return snapshot_path
