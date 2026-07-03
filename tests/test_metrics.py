import pytest

from wim_metrics.metrics import age_bucket, calculate_metrics, sprint_overlaps_week
from wim_metrics.week import ReportWeek


def issue(**overrides):
    base = {
        "key": "GPWIM-1",
        "summary": "Issue",
        "url": "https://theknotww.atlassian.net/browse/GPWIM-1",
        "status": "In Progress",
        "status_category": "In Progress",
        "assignee": None,
        "components": ["Support"],
        "labels": [],
        "created_at": "2026-06-01T09:00:00+02:00",
        "resolved_at": None,
        "assigned_to_support_at": "2026-06-20T09:00:00+02:00",
        "assigned_to_squad_at": None,
        "sprints": [],
    }
    base.update(overrides)
    return base


def test_age_bucket_boundaries():
    assert age_bucket(6) == "new"
    assert age_bucket(7) == "one_week_old"
    assert age_bucket(14) == "two_weeks_old"
    assert age_bucket(30) == "one_month_old"
    assert age_bucket(60) == "two_months_old"
    assert age_bucket(90) == "three_months_old"


def test_sprint_overlap():
    week = ReportWeek.parse("2026-W26")

    assert sprint_overlaps_week("2026-06-15T09:00:00+02:00", "2026-06-29T09:00:00+02:00", week)
    assert not sprint_overlaps_week("2026-06-29T00:00:00+02:00", "2026-07-13T00:00:00+02:00", week)


def test_sprint_overlap_accepts_jira_timezone_offsets_without_colon():
    week = ReportWeek.parse("2026-W26")

    assert sprint_overlaps_week("2026-06-15T09:00:00.000-0400", "2026-06-29T09:00:00.000-0400", week)


def test_sprint_overlap_accepts_jira_utc_z_suffix():
    week = ReportWeek.parse("2026-W26")

    assert sprint_overlaps_week("2026-06-15T09:00:00.000Z", "2026-06-29T09:00:00.000Z", week)


def test_calculates_queue_resolution_and_capacity_metrics():
    week = ReportWeek.parse("2026-W26")
    issues = {
        "GPWIM-1": issue(key="GPWIM-1", components=["Support"]),
        "GPWIM-2": issue(
            key="GPWIM-2",
            components=["Support", "Phoenix"],
            assigned_to_squad_at="2026-06-01T09:00:00+02:00",
            sprints=[{"overlaps_selected_week": True}],
        ),
        "GPWIM-3": issue(
            key="GPWIM-3",
            components=["Support", "Unicorns"],
            status="Done",
            status_category="Done",
            resolved_at="2026-06-23T10:00:00+02:00",
            labels=["wim-support:no-code"],
            assigned_to_squad_at="2026-06-10T09:00:00+02:00",
            sprints=[{"overlaps_selected_week": True}],
        ),
        "GPWIM-4": issue(
            key="GPWIM-4",
            components=["Support"],
            status="Done",
            status_category="Done",
            resolved_at="2026-06-24T11:00:00+02:00",
            labels=["wim-support:duplicate"],
        ),
        "GPWIM-5": issue(
            key="GPWIM-5",
            components=["Support"],
            status="Done",
            status_category="Done",
            resolved_at="2026-06-25T12:00:00+02:00",
            labels=["wim-support:cancelled"],
        ),
        "GPWIM-6": issue(
            key="GPWIM-6",
            components=["Support", "Phoenix"],
            assigned_to_squad_at="2026-06-12T09:00:00+02:00",
            sprints=[{"start_date": "2026-06-15T09:00:00+02:00", "end_date": "2026-06-29T09:00:00+02:00"}],
        ),
    }

    metrics = calculate_metrics(issues, week)

    assert metrics["support_queue"]["issues"] == ["GPWIM-1", "GPWIM-4", "GPWIM-5"]
    assert metrics["squad_queue"]["issues"] == ["GPWIM-2", "GPWIM-3", "GPWIM-6"]
    assert metrics["resolved"]["issues"] == ["GPWIM-3", "GPWIM-4", "GPWIM-5"]
    assert metrics["no_code"]["issues"] == ["GPWIM-3"]
    assert metrics["duplicate"]["issues"] == ["GPWIM-4"]
    assert metrics["cancelled"]["issues"] == ["GPWIM-5"]
    assert metrics["squad_planned"]["issues"] == ["GPWIM-2", "GPWIM-3"]
    assert metrics["squad_done"]["issues"] == ["GPWIM-3"]
    assert metrics["support_queue_one_week_old"]["title"] == "Support Queue (One Week Old)"
    assert metrics["squad_queue_two_months_old"]["title"] == "Squad Queue (Two Months Old)"


def test_rejects_naive_metric_timestamps():
    week = ReportWeek.parse("2026-W26")
    issues = {
        "GPWIM-1": issue(
            key="GPWIM-1",
            assigned_to_support_at="2026-06-20T09:00:00",
        )
    }

    with pytest.raises(ValueError, match="timezone offset"):
        calculate_metrics(issues, week)


def test_null_collections_are_treated_as_empty():
    week = ReportWeek.parse("2026-W26")
    issues = {
        "GPWIM-1": issue(
            key="GPWIM-1",
            components=None,
            labels=None,
            sprints=None,
        )
    }

    metrics = calculate_metrics(issues, week)

    assert metrics["support_queue"]["issues"] == []
    assert metrics["resolved"]["issues"] == []


def test_resolved_week_end_is_exclusive():
    week = ReportWeek.parse("2026-W26")
    issues = {
        "GPWIM-1": issue(
            key="GPWIM-1",
            resolved_at="2026-06-29T00:00:00+02:00",
        )
    }

    metrics = calculate_metrics(issues, week)

    assert metrics["resolved"]["issues"] == []


def test_support_age_falls_back_to_created_at():
    week = ReportWeek.parse("2026-W26")
    issues = {
        "GPWIM-1": issue(
            key="GPWIM-1",
            assigned_to_support_at=None,
            created_at="2026-06-28T09:00:00+02:00",
        )
    }

    metrics = calculate_metrics(issues, week)

    assert metrics["support_queue_new"]["issues"] == ["GPWIM-1"]


def test_squad_age_excludes_missing_assignment_date_but_keeps_total_queue():
    week = ReportWeek.parse("2026-W26")
    issues = {
        "GPWIM-1": issue(
            key="GPWIM-1",
            components=["Support", "Phoenix"],
            assigned_to_squad_at=None,
        )
    }

    metrics = calculate_metrics(issues, week)

    assert metrics["squad_queue"]["issues"] == ["GPWIM-1"]
    assert metrics["squad_queue_new"]["issues"] == []
    assert metrics["squad_queue_one_week_old"]["issues"] == []
