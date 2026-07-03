from __future__ import annotations

from pathlib import Path

from wim_metrics import pipeline
from wim_metrics.week import ReportWeek


def test_confluence_page_url_normalizes_base_url():
    assert (
        pipeline._confluence_page_url("https://theknotww.atlassian.net/wiki/", "123456")
        == "https://theknotww.atlassian.net/wiki/pages/viewpage.action?pageId=123456"
    )


def test_run_weekly_logs_step_summaries(monkeypatch, capsys):
    week = ReportWeek.parse("2026-W26")
    snapshot_path = Path("data/export/2026-W26.json")
    report_path = Path("data/reports/2026-W26.md")
    confluence_url = "https://theknotww.atlassian.net/wiki/pages/viewpage.action?pageId=123456"

    monkeypatch.setattr(pipeline, "default_report_week", lambda: week)
    monkeypatch.setattr(pipeline, "run_extract", lambda week_key, force: snapshot_path)
    monkeypatch.setattr(pipeline, "read_json", lambda path: {"issues": {"GPWIM-1": {}, "GPWIM-2": {}}})
    monkeypatch.setattr(pipeline, "run_report", lambda week_key, force: report_path)
    monkeypatch.setattr(pipeline, "run_publish", lambda week_key: confluence_url)

    pipeline.run_weekly(None, force=True)

    output = capsys.readouterr().out
    assert (
        "[weekly] Extract complete: week=2026-W26 snapshot=data/export/2026-W26.json tickets=2"
        in output
    )
    assert "[weekly] Report complete: week=2026-W26 report=data/reports/2026-W26.md" in output
    assert (
        "[weekly] Publish complete: week=2026-W26 "
        "confluence=https://theknotww.atlassian.net/wiki/pages/viewpage.action?pageId=123456"
    ) in output
    assert "[weekly] Summary: week=2026-W26 duration=" in output
    assert "tickets=2" in output
    assert "pageId=123456" in output
