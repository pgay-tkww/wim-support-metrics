from __future__ import annotations

from inspect import signature
from pathlib import Path
from time import perf_counter
from typing import Callable

from wim_metrics.config import load_config
from wim_metrics.extractor import extract_week
from wim_metrics.jira_client import JiraClient
from wim_metrics.serialization import read_json
from wim_metrics.week import ReportWeek, default_report_week


EXPORT_DIR = Path("data/export")
REPORT_DIR = Path("data/reports")


def run_extract(week_key: str, force: bool) -> Path:
    week = ReportWeek.parse(week_key)
    config = load_config()
    jira_client = JiraClient(
        base_url=config.jira_base_url,
        email=config.jira_email,
        api_token=config.jira_api_token,
    )

    return extract_week(
        week,
        jira_client,
        output_dir=EXPORT_DIR,
        force=force,
        sprint_field=config.jira_sprint_field,
    )


def run_report(week_key: str, force: bool) -> Path:
    week = ReportWeek.parse(week_key)

    from wim_metrics.report import write_weekly_report

    kwargs = {"report_dir": REPORT_DIR, "force": force}
    parameters = signature(write_weekly_report).parameters
    if "snapshot_dir" in parameters:
        kwargs["snapshot_dir"] = EXPORT_DIR
    elif "snapshot_path" in parameters:
        kwargs["snapshot_path"] = EXPORT_DIR

    return write_weekly_report(week.key, **kwargs)


def run_publish(week_key: str) -> str:
    week = ReportWeek.parse(week_key)
    report_path = REPORT_DIR / f"{week.key}.md"
    markdown = report_path.read_text()
    config = load_config()

    from wim_metrics.confluence_client import ConfluenceClient, markdown_to_storage_html

    render_historical_summary = _load_historical_summary_renderer()

    client = ConfluenceClient(
        base_url=config.confluence_base_url,
        email=config.confluence_email,
        api_token=config.confluence_api_token,
    )
    html = markdown_to_storage_html(markdown)
    existing_page = client.find_child_page(
        config.confluence_space_key,
        config.confluence_parent_page_id,
        week.confluence_title,
    )
    if existing_page:
        published_page = client.update_page(existing_page["id"], week.confluence_title, html)
    else:
        published_page = client.create_page(
            config.confluence_space_key,
            config.confluence_parent_page_id,
            week.confluence_title,
            html,
        )

    snapshots = _read_historical_snapshots(week)
    if render_historical_summary is not None and snapshots:
        summary_html = markdown_to_storage_html(render_historical_summary(snapshots))
        client.update_page(
            config.confluence_parent_page_id,
            "WIM Support - Weekly Metrics",
            summary_html,
        )

    page_id = str(published_page.get("id", "")).strip()
    if not page_id:
        raise RuntimeError("Publish succeeded but Confluence response did not include a page id")

    return _confluence_page_url(config.confluence_base_url, page_id)


def run_weekly(week_key: str | None, force: bool) -> None:
    week = default_report_week() if week_key is None else ReportWeek.parse(week_key)
    started_at = perf_counter()

    snapshot_path = run_extract(week.key, force=force)
    snapshot = read_json(snapshot_path)
    ticket_count = _count_snapshot_issues(snapshot)
    print(
        f"[weekly] Extract complete: week={week.key} snapshot={snapshot_path} "
        f"tickets={ticket_count}"
    )

    report_path = run_report(week.key, force=force)
    print(f"[weekly] Report complete: week={week.key} report={report_path}")

    confluence_url = run_publish(week.key)
    print(f"[weekly] Publish complete: week={week.key} confluence={confluence_url}")

    duration_seconds = perf_counter() - started_at
    print(
        f"[weekly] Summary: week={week.key} duration={duration_seconds:.1f}s "
        f"tickets={ticket_count} confluence={confluence_url}"
    )


def _read_historical_snapshots(week: ReportWeek) -> list[dict]:
    snapshots = []
    for snapshot_path in sorted(EXPORT_DIR.glob("*.json")):
        snapshot_week = snapshot_path.stem
        try:
            parsed_week = ReportWeek.parse(snapshot_week)
        except ValueError:
            continue
        if (parsed_week.iso_year, parsed_week.iso_week) <= (week.iso_year, week.iso_week):
            snapshots.append(read_json(snapshot_path))

    return snapshots


def _load_historical_summary_renderer() -> Callable[[list[dict]], str] | None:
    try:
        from wim_metrics.report import render_historical_summary
    except ImportError:
        return None

    return render_historical_summary


def _count_snapshot_issues(snapshot: dict) -> int:
    issues = snapshot.get("issues", {})
    return len(issues) if isinstance(issues, dict) else 0


def _confluence_page_url(base_url: str, page_id: str) -> str:
    return f"{base_url.rstrip('/')}/pages/viewpage.action?pageId={page_id}"
