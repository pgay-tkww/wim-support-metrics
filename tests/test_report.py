import json
import re
from copy import deepcopy
from pathlib import Path

from wim_metrics.report import render_historical_summary, render_weekly_report


def load_snapshot() -> dict:
    return json.loads(Path("tests/fixtures/snapshot_2026-W26.json").read_text())


def test_render_weekly_report_contains_sections_and_issue_links():
    snapshot = load_snapshot()

    markdown = render_weekly_report(snapshot)

    assert "# WIM Support Metrics - 2026-W26" in markdown
    assert "Flow Metrics" in markdown
    assert "Inventory Metrics" in markdown
    assert "Capacity Metrics" in markdown
    assert "https://theknotww.atlassian.net/issues/?jql=" in markdown
    assert "GPWIM-123" in markdown


def test_render_weekly_report_uses_two_column_tables_with_query_links_in_count():
    snapshot = load_snapshot()

    markdown = render_weekly_report(snapshot)

    assert "| Metric | Count |" in markdown
    assert "| Metric | Count | Issues |" not in markdown
    assert '| Resolved | 1 (<a href="https://theknotww.atlassian.net/issues/?jql=key%20in%20%28GPWIM-123%29">query</a>) |' in markdown
    assert "<details>" not in markdown.split("## Metrics by Squad", 1)[0]
    assert "## Detailed Issues" not in markdown
    assert "| Issue | Status | Assignee | Summary |" not in markdown


def test_render_weekly_report_executive_summary_uses_approved_metrics():
    snapshot = load_snapshot()

    markdown = render_weekly_report(snapshot)
    executive_summary = markdown.split("## Flow Metrics", 1)[0]

    assert "| General Queue |" in executive_summary
    assert "| Support Queue |" not in executive_summary
    assert "| Squad Queue |" in executive_summary
    assert "| Squad Planned |" in executive_summary
    assert "| Squad Done |" in executive_summary
    assert "| Resolved |" not in executive_summary
    assert "| Metric | Count | Issues |" not in executive_summary


def test_render_weekly_report_uses_business_friendly_metric_names():
    snapshot = load_snapshot()
    snapshot["metrics"]["support_queue"] = {
        "title": "Support Queue",
        "count": 1,
        "issues": ["GPWIM-123"],
    }
    snapshot["metrics"]["support_queue_new"] = {
        "title": "Support Queue (New)",
        "count": 1,
        "issues": ["GPWIM-123"],
    }
    snapshot["metrics"]["support_queue_one_week_old"] = {
        "title": "Support Queue (One Week Old)",
        "count": 1,
        "issues": ["GPWIM-123"],
    }
    snapshot["metrics"]["support_queue_three_months_old"] = {
        "title": "Support Queue (Three Months Old)",
        "count": 1,
        "issues": ["GPWIM-123"],
    }

    markdown = render_weekly_report(snapshot)

    assert "General Queue" in markdown
    assert "Support Queue" not in markdown
    assert "Resolved without code" in markdown
    assert "Closed as duplicate" in markdown
    assert "Cancelled" not in markdown
    assert "General Queue (new)" in markdown
    assert "General Queue (> 1w)" in markdown
    assert "General Queue (> 3m)" in markdown


def test_render_weekly_report_adds_collapsible_metrics_by_squad_sections():
    snapshot = load_snapshot()
    snapshot["issues"]["GPWIM-456"] = {
        **snapshot["issues"]["GPWIM-123"],
        "key": "GPWIM-456",
        "url": "https://theknotww.atlassian.net/browse/GPWIM-456",
        "components": ["Support", "Unicorns"],
    }
    snapshot["metrics"]["squad_queue"] = {
        "title": "Squad Queue",
        "count": 2,
        "issues": ["GPWIM-123", "GPWIM-456"],
    }
    snapshot["metrics"]["squad_planned"] = {
        "title": "Squad Planned",
        "count": 1,
        "issues": ["GPWIM-123"],
    }
    snapshot["metrics"]["resolved"] = {
        "title": "Resolved",
        "count": 2,
        "issues": ["GPWIM-123", "GPWIM-456"],
    }
    snapshot["metrics"]["squad_queue_one_week_old"] = {
        "title": "Squad Queue (One Week Old)",
        "count": 2,
        "issues": ["GPWIM-123", "GPWIM-456"],
    }

    markdown = render_weekly_report(snapshot)
    by_squad = markdown.split("## Metrics by Squad", 1)[1]

    assert "<summary>Phoenix</summary>" in by_squad
    assert "<summary>Unicorns</summary>" in by_squad
    assert "| Metric | Phoenix | Total |" in by_squad
    assert "| Metric | Unicorns | Total |" in by_squad
    assert '| Squad Queue | 1 (<a href="https://theknotww.atlassian.net/issues/?jql=key%20in%20%28GPWIM-123%29">query</a>) | 2 (50%) |' in by_squad
    phoenix_summary = by_squad.split("### Flow Metrics", 1)[0]
    assert "| Squad Done |" in phoenix_summary
    assert "| Resolved |" not in phoenix_summary
    assert "| Squad Queue (> 1w) |" in by_squad


def test_render_historical_summary_uses_latest_eight_snapshots():
    snapshots = []
    for week_number in range(18, 27):
        snapshot = deepcopy(load_snapshot())
        snapshot["week"]["key"] = f"2026-W{week_number:02d}"
        snapshot["week"]["iso_week"] = week_number
        for metric in snapshot["metrics"].values():
            metric["count"] = week_number
            metric["issues"] = []
        snapshots.append(snapshot)

    markdown = render_historical_summary(snapshots)

    assert "Delta" in markdown
    assert "2026-W18" not in markdown
    for week_number in range(19, 27):
        assert f"2026-W{week_number:02d}" in markdown
    assert len(re.findall(r"2026-W\d{2}", markdown)) == 8
