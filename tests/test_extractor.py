import json
from pathlib import Path

import pytest

from wim_metrics.extractor import (
    DEFAULT_SPRINT_FIELD,
    build_issue_snapshot,
    extract_assignment_dates,
    extract_sprint_ids,
    extract_week,
)
from wim_metrics.serialization import read_json
from wim_metrics.week import ReportWeek


def load_fixture() -> dict:
    return json.loads(Path("tests/fixtures/jira_issue.json").read_text())


class FakeJiraClient:
    def __init__(self, issue: dict, sprint_field: str = DEFAULT_SPRINT_FIELD) -> None:
        self._issue = issue
        self.base_url = "https://theknotww.atlassian.net"
        self.sprint_field = sprint_field

    def search_issues(self, jql: str, fields: list[str]) -> list[dict]:
        assert jql == "project = GPWIM AND component in (Support)"
        assert fields == [
            "summary",
            "status",
            "assignee",
            "components",
            "labels",
            "created",
            "resolutiondate",
            self.sprint_field,
        ]
        return [
            {
                "key": self._issue["key"],
                "fields": self._issue["fields"],
            }
        ]

    def get_issue_changelog(self, issue_key: str) -> list[dict]:
        assert issue_key == self._issue["key"]
        return self._issue["changelog"]["histories"]

    def get_sprint(self, sprint_id: int) -> dict:
        assert sprint_id == 123
        return {
            "id": 123,
            "name": "WIM Sprint 42",
            "state": "active",
            "startDate": "2026-06-15T09:00:00+02:00",
            "endDate": "2026-06-29T09:00:00+02:00",
        }


def test_extract_sprint_ids_collects_dict_string_and_nested_values():
    raw_issue = {
        "fields": {
            "status": {"id": "3", "name": "In Progress"},
            "components": [{"id": "10100", "name": "Support"}],
            "assignee": {"accountId": "abc", "id": "not-a-sprint"},
            DEFAULT_SPRINT_FIELD: [
                {"id": 123},
                "com.atlassian.greenhopper.service.sprint.Sprint@123[id=456,rapidViewId=1]",
                [{"id": "456"}],
            ],
        }
    }

    assert extract_sprint_ids(raw_issue, DEFAULT_SPRINT_FIELD) == [123, 456]


def test_extract_assignment_dates_detects_squad_when_support_added_after_squad_component():
    changelog = [
        {
            "created": "2025-08-07T04:03:33.261-0400",
            "items": [{"field": "Component", "fromString": None, "toString": "Phoenix"}],
        },
        {
            "created": "2025-09-16T09:31:41.405-0400",
            "items": [{"field": "Component", "fromString": None, "toString": "Support"}],
        },
    ]

    assert extract_assignment_dates(changelog) == {
        "assigned_to_support_at": "2025-09-16T09:31:41.405-0400",
        "assigned_to_squad_at": "2025-09-16T09:31:41.405-0400",
    }


def test_build_issue_snapshot_falls_back_squad_assignment_for_current_squad_issue():
    week = ReportWeek.parse("2026-W26")
    raw_issue = {
        "key": "GPWIM-999",
        "fields": {
            "summary": "Current squad issue without component history",
            "status": {"name": "To Do", "statusCategory": {"name": "To Do"}},
            "assignee": None,
            "components": [{"name": "Support"}, {"name": "Unicorns"}],
            "labels": [],
            "created": "2026-06-20T10:00:00+02:00",
            "resolutiondate": None,
            DEFAULT_SPRINT_FIELD: [],
        },
    }

    snapshot = build_issue_snapshot(
        raw_issue,
        changelog=[],
        sprint_lookup={},
        week=week,
        jira_base_url="https://theknotww.atlassian.net",
        sprint_field=DEFAULT_SPRINT_FIELD,
    )

    assert snapshot["assigned_to_squad_at"] == "2026-06-20T10:00:00+02:00"


def test_build_issue_snapshot_errors_when_sprint_metadata_missing():
    week = ReportWeek.parse("2026-W26")
    raw_issue = {
        "key": "GPWIM-999",
        "fields": {
            "summary": "Missing sprint metadata",
            "status": {"name": "To Do", "statusCategory": {"name": "To Do"}},
            "assignee": None,
            "components": [],
            "labels": [],
            "created": "2026-06-20T10:00:00+02:00",
            "resolutiondate": None,
            DEFAULT_SPRINT_FIELD: [{"id": 123}],
        },
    }

    with pytest.raises(RuntimeError, match=r"GPWIM-999.*123"):
        build_issue_snapshot(
            raw_issue,
            changelog=[],
            sprint_lookup={},
            week=week,
            jira_base_url="https://theknotww.atlassian.net",
            sprint_field=DEFAULT_SPRINT_FIELD,
        )


def test_extract_snapshot_builds_week_source_issues_and_metrics(tmp_path):
    week = ReportWeek.parse("2026-W26")
    client = FakeJiraClient(load_fixture())

    snapshot_path = extract_week(week, client, tmp_path, force=False)

    assert snapshot_path == tmp_path / "2026-W26.json"
    assert snapshot_path.exists()

    snapshot = read_json(snapshot_path)

    assert snapshot["schema_version"] == 1
    assert snapshot["week"]["key"] == "2026-W26"
    assert snapshot["week"]["start_date"] == "2026-06-22"
    assert snapshot["source"]["jira_base_jql"] == "project = GPWIM AND component in (Support)"
    assert snapshot["issues"]["GPWIM-123"]["url"] == "https://theknotww.atlassian.net/browse/GPWIM-123"
    assert snapshot["issues"]["GPWIM-123"]["assigned_to_support_at"] == "2026-06-03T10:00:00+02:00"
    assert snapshot["issues"]["GPWIM-123"]["assigned_to_squad_at"] == "2026-06-10T11:00:00+02:00"
    assert snapshot["issues"]["GPWIM-123"]["components"] == ["Alpha", "Phoenix", "Support"]
    assert snapshot["issues"]["GPWIM-123"]["labels"] == [
        "alpha-triage",
        "customer-escalation",
        "wim-support:no-code",
    ]
    assert snapshot["issues"]["GPWIM-123"]["sprints"] == [
        {
            "id": 123,
            "name": "WIM Sprint 42",
            "state": "active",
            "start_date": "2026-06-15T09:00:00+02:00",
            "end_date": "2026-06-29T09:00:00+02:00",
            "overlaps_selected_week": True,
        }
    ]
    assert snapshot["metrics"]["squad_queue"]["issues"] == ["GPWIM-123"]
    assert snapshot["metrics"]["no_code"]["issues"] == ["GPWIM-123"]
    assert snapshot["metrics"]["squad_planned"]["issues"] == ["GPWIM-123"]


def test_extract_week_accepts_custom_sprint_field(tmp_path):
    week = ReportWeek.parse("2026-W26")
    fixture = load_fixture()
    fixture["fields"]["customfield_12345"] = fixture["fields"].pop(DEFAULT_SPRINT_FIELD)
    client = FakeJiraClient(fixture, sprint_field="customfield_12345")

    snapshot_path = extract_week(
        week,
        client,
        tmp_path,
        force=False,
        sprint_field="customfield_12345",
    )

    snapshot = read_json(snapshot_path)
    assert snapshot["issues"]["GPWIM-123"]["sprints"][0]["id"] == 123
    assert snapshot["metrics"]["squad_planned"]["issues"] == ["GPWIM-123"]


def test_extract_week_raises_when_jira_client_base_url_missing(tmp_path):
    week = ReportWeek.parse("2026-W26")
    client = FakeJiraClient(load_fixture())
    del client.base_url

    with pytest.raises(RuntimeError, match="Jira client must expose a non-empty base_url"):
        extract_week(week, client, tmp_path, force=False)
