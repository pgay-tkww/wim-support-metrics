# WIM Support Metrics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first Python engine that extracts WIM support metrics from Jira, stores immutable weekly JSON snapshots, generates weekly and historical reports, and publishes them to Confluence.

**Architecture:** Use a small `wim_metrics` Python package with focused modules for week handling, configuration, Jira access, extraction, metrics, reporting, and Confluence publishing. CLI scripts in `scripts/` call package functions so the same logic works locally and in GitHub Actions.

**Tech Stack:** Python 3.11+, `pytest`, `requests`, standard-library `zoneinfo`, GitHub Actions cron.

**Important:** Do not create git commits while executing this plan unless the user explicitly asks for commits in a future instruction.

---

## File Structure

Create:

- `pyproject.toml`: package metadata, dependencies, pytest config.
- `.gitignore`: Python cache, virtualenv, local env files.
- `wim_metrics/__init__.py`: package marker.
- `wim_metrics/week.py`: ISO week parsing, Madrid-time ranges, default scheduled week, page titles.
- `wim_metrics/config.py`: environment-backed Jira and Confluence config.
- `wim_metrics/models.py`: dataclasses and typed structures shared across modules.
- `wim_metrics/serialization.py`: stable JSON read/write helpers.
- `wim_metrics/metrics.py`: metric definitions and bucket logic.
- `wim_metrics/report.py`: weekly Markdown and historical summary rendering.
- `wim_metrics/jira_client.py`: Jira REST API adapter.
- `wim_metrics/extractor.py`: Jira-to-snapshot orchestration.
- `wim_metrics/confluence_client.py`: Confluence REST API adapter.
- `wim_metrics/pipeline.py`: extract/report/publish orchestration.
- `scripts/extract.py`: CLI wrapper for extraction.
- `scripts/report.py`: CLI wrapper for report generation.
- `scripts/publish.py`: CLI wrapper for publishing.
- `scripts/weekly.py`: CLI wrapper for full weekly run.
- `.github/workflows/weekly.yml`: Monday 06:00 Europe/Madrid scheduled run.
- `tests/fixtures/jira_issue.json`: representative Jira issue fixture.
- `tests/fixtures/snapshot_2026-W26.json`: stable snapshot fixture.
- `tests/test_week.py`: week model tests.
- `tests/test_metrics.py`: metric and bucket tests.
- `tests/test_serialization.py`: stable JSON tests.
- `tests/test_report.py`: report rendering tests.
- `tests/test_config.py`: env validation tests.
- `tests/test_jira_client.py`: mocked Jira API tests.
- `tests/test_extractor.py`: fixture extraction tests.
- `tests/test_confluence_client.py`: mocked Confluence API tests.
- `tests/test_cli.py`: CLI behavior tests.

Modify:

- `README.md`: local setup, required env vars, command examples.

---

### Task 1: Project Skeleton And Test Harness

**Files:**

- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `wim_metrics/__init__.py`
- Create: `tests/`

- [ ] **Step 1: Create package/test config**

Add `pyproject.toml`:

```toml
[project]
name = "wim-support-metrics"
version = "0.1.0"
description = "Weekly WIM support metrics extracted from Jira and published to Confluence"
requires-python = ">=3.11"
dependencies = [
  "requests>=2.32.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 2: Add local ignore rules**

Add `.gitignore`:

```gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
.env
data/export/*.tmp
data/reports/*.tmp
```

- [ ] **Step 3: Create package marker**

Add `wim_metrics/__init__.py`:

```python
"""WIM support metrics engine."""
```

- [ ] **Step 4: Run test discovery**

Run:

```bash
python -m pytest -q
```

Expected: pytest exits successfully. If pytest returns code 5 because no tests exist yet, continue to Task 2 and use the Task 2 test run as the first required passing check.

---

### Task 2: ISO Week Model

**Files:**

- Create: `wim_metrics/week.py`
- Create: `tests/test_week.py`

- [ ] **Step 1: Write failing week tests**

Add `tests/test_week.py`:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from wim_metrics.week import ReportWeek, default_report_week


def test_parse_iso_week_key_builds_madrid_boundaries():
    week = ReportWeek.parse("2026-W26")

    assert week.key == "2026-W26"
    assert week.iso_year == 2026
    assert week.iso_week == 26
    assert week.start.isoformat() == "2026-06-22T00:00:00+02:00"
    assert week.end_exclusive.isoformat() == "2026-06-29T00:00:00+02:00"
    assert week.display_end_date == "2026-06-28"


def test_rejects_invalid_week_key():
    with pytest.raises(ValueError, match="Expected ISO week key like 2026-W26"):
        ReportWeek.parse("W26")


def test_confluence_title_uses_monday_date():
    assert ReportWeek.parse("2026-W26").confluence_title == (
        "W26 2026-06-22 | WIM Support - Weekly Metrics"
    )


def test_default_week_uses_previous_completed_iso_week():
    now = datetime(2026, 6, 29, 6, 0, tzinfo=ZoneInfo("Europe/Madrid"))

    assert default_report_week(now).key == "2026-W26"
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
python -m pytest tests/test_week.py -q
```

Expected: import failure for `wim_metrics.week`.

- [ ] **Step 3: Implement week model**

Add `wim_metrics/week.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")


@dataclass(frozen=True)
class ReportWeek:
    key: str
    iso_year: int
    iso_week: int
    start: datetime
    end_exclusive: datetime

    @classmethod
    def parse(cls, key: str) -> "ReportWeek":
        try:
            year_text, week_text = key.split("-W", 1)
            iso_year = int(year_text)
            iso_week = int(week_text)
            start_date = datetime.fromisocalendar(iso_year, iso_week, 1)
        except (ValueError, TypeError) as exc:
            raise ValueError("Expected ISO week key like 2026-W26") from exc

        if f"{iso_year:04d}-W{iso_week:02d}" != key:
            raise ValueError("Expected ISO week key like 2026-W26")

        start = start_date.replace(tzinfo=MADRID)
        return cls(
            key=key,
            iso_year=iso_year,
            iso_week=iso_week,
            start=start,
            end_exclusive=start + timedelta(days=7),
        )

    @property
    def display_start_date(self) -> str:
        return self.start.date().isoformat()

    @property
    def display_end_date(self) -> str:
        return (self.end_exclusive.date() - timedelta(days=1)).isoformat()

    @property
    def confluence_title(self) -> str:
        return f"W{self.iso_week:02d} {self.display_start_date} | WIM Support - Weekly Metrics"


def default_report_week(now: datetime | None = None) -> ReportWeek:
    current = now.astimezone(MADRID) if now else datetime.now(MADRID)
    previous_week_date = current.date() - timedelta(days=7)
    iso = previous_week_date.isocalendar()
    return ReportWeek.parse(f"{iso.year:04d}-W{iso.week:02d}")
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_week.py -q
```

Expected: all tests pass.

---

### Task 3: Shared Models And Stable Serialization

**Files:**

- Create: `wim_metrics/models.py`
- Create: `wim_metrics/serialization.py`
- Create: `tests/test_serialization.py`

- [ ] **Step 1: Write failing serialization tests**

Add `tests/test_serialization.py`:

```python
import json

import pytest

from wim_metrics.serialization import ExistingOutputError, read_json, write_json


def test_write_json_is_stable_and_sorted(tmp_path):
    path = tmp_path / "snapshot.json"
    write_json(path, {"b": 1, "a": {"d": 4, "c": 3}}, force=False)

    assert path.read_text() == json.dumps(
        {"a": {"c": 3, "d": 4}, "b": 1},
        indent=2,
        sort_keys=True,
    ) + "\n"


def test_write_json_refuses_existing_file_without_force(tmp_path):
    path = tmp_path / "snapshot.json"
    path.write_text("{}\n")

    with pytest.raises(ExistingOutputError, match="already exists"):
        write_json(path, {"a": 1}, force=False)


def test_write_json_allows_force(tmp_path):
    path = tmp_path / "snapshot.json"
    path.write_text("{}\n")

    write_json(path, {"a": 1}, force=True)

    assert read_json(path) == {"a": 1}
```

- [ ] **Step 2: Implement shared dataclasses**

Add `wim_metrics/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SprintSnapshot:
    id: int
    name: str
    state: str
    start_date: str | None
    end_date: str | None
    overlaps_selected_week: bool


@dataclass(frozen=True)
class IssueSnapshot:
    key: str
    summary: str
    url: str
    status: str
    status_category: str
    assignee: str | None
    components: list[str]
    labels: list[str]
    created_at: str
    resolved_at: str | None
    assigned_to_support_at: str | None
    assigned_to_squad_at: str | None
    sprints: list[SprintSnapshot] = field(default_factory=list)
```

- [ ] **Step 3: Implement serialization**

Add `wim_metrics/serialization.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ExistingOutputError(RuntimeError):
    pass


def write_json(path: Path, data: dict[str, Any], *, force: bool) -> None:
    if path.exists() and not force:
        raise ExistingOutputError(f"{path} already exists; use --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_serialization.py -q
```

Expected: all tests pass.

---

### Task 4: Metric Definitions

**Files:**

- Create: `wim_metrics/metrics.py`
- Create: `tests/test_metrics.py`

- [ ] **Step 1: Write failing metric tests**

Add `tests/test_metrics.py`:

```python
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
    }

    metrics = calculate_metrics(issues, week)

    assert metrics["support_queue"]["issues"] == ["GPWIM-1"]
    assert metrics["squad_queue"]["issues"] == ["GPWIM-2", "GPWIM-3"]
    assert metrics["resolved"]["issues"] == ["GPWIM-3"]
    assert metrics["no_code"]["issues"] == ["GPWIM-3"]
    assert metrics["squad_planned"]["issues"] == ["GPWIM-2", "GPWIM-3"]
    assert metrics["squad_done"]["issues"] == ["GPWIM-3"]
```

- [ ] **Step 2: Implement metrics**

Add `wim_metrics/metrics.py`:

```python
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


def parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


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
    components = set(issue.get("components", []))
    return SUPPORT_COMPONENT in components and components.isdisjoint(SQUAD_COMPONENTS)


def is_squad_queue(issue: dict[str, Any]) -> bool:
    components = set(issue.get("components", []))
    return SUPPORT_COMPONENT in components and not components.isdisjoint(SQUAD_COMPONENTS)


def resolved_in_week(issue: dict[str, Any], week: ReportWeek) -> bool:
    resolved = parse_dt(issue.get("resolved_at"))
    return resolved is not None and week.start <= resolved < week.end_exclusive


def metric(title: str, keys: list[str]) -> dict[str, Any]:
    sorted_keys = sorted(keys)
    return {"title": title, "count": len(sorted_keys), "issues": sorted_keys}


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
            [key for key in resolved_keys if "wim-support:no-code" in issues[key].get("labels", [])],
        ),
        "duplicate": metric(
            METRIC_TITLES["duplicate"],
            [key for key in resolved_keys if "wim-support:duplicate" in issues[key].get("labels", [])],
        ),
        "cancelled": metric(
            METRIC_TITLES["cancelled"],
            [key for key in resolved_keys if "wim-support:cancelled" in issues[key].get("labels", [])],
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
            result[metric_id] = metric(metric_id.replace("_", " ").title(), bucket_keys)

    planned_keys = [
        key
        for key in squad_keys
        if any(sprint.get("overlaps_selected_week") for sprint in issues[key].get("sprints", []))
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
```

- [ ] **Step 3: Run metric tests**

Run:

```bash
python -m pytest tests/test_metrics.py -q
```

Expected: all tests pass.

---

### Task 5: Configuration Validation

**Files:**

- Create: `wim_metrics/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing config tests**

Add `tests/test_config.py`:

```python
import pytest

from wim_metrics.config import ConfigError, load_config


def test_load_config_requires_env(monkeypatch):
    for key in [
        "JIRA_BASE_URL",
        "JIRA_EMAIL",
        "JIRA_API_TOKEN",
        "CONFLUENCE_BASE_URL",
        "CONFLUENCE_EMAIL",
        "CONFLUENCE_API_TOKEN",
    ]:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ConfigError, match="Missing required environment variables"):
        load_config()


def test_load_config_defaults_confluence_page_settings(monkeypatch):
    monkeypatch.setenv("JIRA_BASE_URL", "https://theknotww.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "user@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "jira-token")
    monkeypatch.setenv("CONFLUENCE_BASE_URL", "https://theknotww.atlassian.net/wiki")
    monkeypatch.setenv("CONFLUENCE_EMAIL", "user@example.com")
    monkeypatch.setenv("CONFLUENCE_API_TOKEN", "conf-token")

    config = load_config()

    assert config.confluence_space_key == "WWIM"
    assert config.confluence_parent_page_id == "6499926021"
```

- [ ] **Step 2: Implement config**

Add `wim_metrics/config.py`:

```python
from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class AppConfig:
    jira_base_url: str
    jira_email: str
    jira_api_token: str
    confluence_base_url: str
    confluence_email: str
    confluence_api_token: str
    confluence_space_key: str
    confluence_parent_page_id: str


def load_config() -> AppConfig:
    required = [
        "JIRA_BASE_URL",
        "JIRA_EMAIL",
        "JIRA_API_TOKEN",
        "CONFLUENCE_BASE_URL",
        "CONFLUENCE_EMAIL",
        "CONFLUENCE_API_TOKEN",
    ]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise ConfigError("Missing required environment variables: " + ", ".join(missing))

    return AppConfig(
        jira_base_url=os.environ["JIRA_BASE_URL"].rstrip("/"),
        jira_email=os.environ["JIRA_EMAIL"],
        jira_api_token=os.environ["JIRA_API_TOKEN"],
        confluence_base_url=os.environ["CONFLUENCE_BASE_URL"].rstrip("/"),
        confluence_email=os.environ["CONFLUENCE_EMAIL"],
        confluence_api_token=os.environ["CONFLUENCE_API_TOKEN"],
        confluence_space_key=os.environ.get("CONFLUENCE_SPACE_KEY", "WWIM"),
        confluence_parent_page_id=os.environ.get("CONFLUENCE_PARENT_PAGE_ID", "6499926021"),
    )
```

- [ ] **Step 3: Run config tests**

Run:

```bash
python -m pytest tests/test_config.py -q
```

Expected: all tests pass.

---

### Task 6: Jira Client Adapter

**Files:**

- Create: `wim_metrics/jira_client.py`
- Create: `tests/test_jira_client.py`

- [ ] **Step 1: Write mocked Jira client tests**

Add `tests/test_jira_client.py` using a fake session object with `get()` and `post()` methods. Cover:

```python
def test_search_issues_posts_jql_and_paginates():
    # Fake first response with one issue and total=2.
    # Fake second response with one issue and total=2.
    # Assert returned list has two issues.
    # Assert JQL is "project = GPWIM AND component in (Support)".


def test_get_issue_changelog_calls_expand_changelog():
    # Fake response includes changelog histories.
    # Assert client returns histories.


def test_get_sprint_returns_metadata():
    # Fake response includes id, name, state, startDate, endDate.
    # Assert returned dict preserves those fields.
```

- [ ] **Step 2: Implement Jira client**

Add `wim_metrics/jira_client.py` with a `JiraClient` class implementing these public methods:

- `search_issues(jql: str, fields: list[str]) -> list[dict[str, Any]]`
- `get_issue_changelog(issue_key: str) -> list[dict[str, Any]]`
- `get_sprint(sprint_id: int) -> dict[str, Any]`

Implementation details:

- Use basic auth `(email, api_token)`.
- Use Jira Cloud search endpoint `/rest/api/3/search`.
- Request `maxResults=100` and paginate until all results are read.
- Use `/rest/api/3/issue/{issue_key}?expand=changelog` for changelogs.
- Use `/rest/agile/1.0/sprint/{sprint_id}` for sprint metadata.
- Raise `RuntimeError` with operation name and status code when a response is not successful.
- Keep response handling in a private `_request()` helper so all API errors have consistent messages.

- [ ] **Step 3: Run Jira client tests**

Run:

```bash
python -m pytest tests/test_jira_client.py -q
```

Expected: all tests pass.

---

### Task 7: Extractor And Snapshot Builder

**Files:**

- Create: `wim_metrics/extractor.py`
- Create: `tests/fixtures/jira_issue.json`
- Create: `tests/test_extractor.py`

- [ ] **Step 1: Add representative Jira fixture**

Create `tests/fixtures/jira_issue.json` with an issue containing:

- Key `GPWIM-123`
- Summary
- Status with `statusCategory.name`
- Assignee display name
- Components `Support` and `Phoenix`
- Labels including `wim-support:no-code`
- Created and resolution timestamps
- Sprint custom field value containing sprint id `123`
- Changelog entries adding `Support` and `Phoenix`

- [ ] **Step 2: Write extractor tests**

Add tests for:

```python
def test_extract_snapshot_builds_week_source_issues_and_metrics(tmp_path):
    # Fake Jira client returns the fixture issue, changelog, and sprint metadata.
    # Run extract_week(ReportWeek.parse("2026-W26"), fake_client, tmp_path, force=False).
    # Assert data/export/2026-W26.json exists.
    # Assert source.jira_base_jql == "project = GPWIM AND component in (Support)".
    # Assert assigned_to_support_at and assigned_to_squad_at are populated.
    # Assert metrics include squad_queue and no_code.
```

- [ ] **Step 3: Implement extractor**

Add `wim_metrics/extractor.py` with these functions:

```python
BASE_JQL = "project = GPWIM AND component in (Support)"
JIRA_FIELDS = ["summary", "status", "assignee", "components", "labels", "created", "resolutiondate", "Sprint"]
```

Rules:

- Search `BASE_JQL`.
- Fetch changelog for each issue.
- Extract component-added timestamps for `Support`, `Phoenix`, `Unicorns`.
- Fetch sprint metadata for unique sprint IDs.
- Mark `overlaps_selected_week` using `sprint_overlaps_week`.
- Calculate metrics from the issue catalog.
- Write `data/export/<week>.json` through `write_json()`.
- `build_issue_snapshot(raw_issue, changelog, sprint_lookup, week, jira_base_url)` returns the issue dictionary matching the snapshot schema.
- `extract_assignment_dates(changelog)` returns `{"assigned_to_support_at": str | None, "assigned_to_squad_at": str | None}`.
- `extract_sprint_ids(raw_issue)` returns sorted integer sprint IDs from every Jira field value that looks like a sprint object.
- `extract_week(week, jira_client, output_dir=Path("data/export"), force=False)` writes and returns the snapshot path.

- [ ] **Step 4: Run extractor tests**

Run:

```bash
python -m pytest tests/test_extractor.py -q
```

Expected: all tests pass.

---

### Task 8: Weekly And Historical Report Rendering

**Files:**

- Create: `wim_metrics/report.py`
- Create: `tests/fixtures/snapshot_2026-W26.json`
- Create: `tests/test_report.py`

- [ ] **Step 1: Write report tests**

Add tests for:

```python
def test_render_weekly_report_contains_sections_and_issue_links():
    # Load fixture snapshot.
    # Render Markdown.
    # Assert it contains "# WIM Support Metrics - 2026-W26".
    # Assert it contains "Flow Metrics", "Inventory Metrics", "Capacity Metrics".
    # Assert it contains "GPWIM-123" and Jira URL.


def test_render_historical_summary_uses_latest_eight_snapshots():
    # Provide nine fixture-like snapshots.
    # Assert only eight week keys are rendered.
    # Assert delta column appears.
```

- [ ] **Step 2: Implement report renderer**

Add `wim_metrics/report.py` with:

- `render_weekly_report(snapshot: dict) -> str`: returns deterministic Markdown for one snapshot.
- `render_historical_summary(snapshots: list[dict]) -> str`: returns deterministic Markdown for the latest eight snapshots supplied.
- `write_weekly_report(week_key: str, snapshot_path=Path("data/export"), report_dir=Path("data/reports"), force=False) -> Path`: reads `data/export/<week>.json`, writes `data/reports/<week>.md`, and returns the report path.

Weekly Markdown sections:

- `# WIM Support Metrics - <week>`
- `## Executive Summary`
- `## Flow Metrics`
- `## Inventory Metrics`
- `## Capacity Metrics`
- `## Detailed Issues`

Historical summary:

- Sort snapshots by `week.key`.
- Keep the latest eight snapshots up to the selected week.
- Render rows for `support_queue`, `squad_queue`, `resolved`, `squad_planned`, `squad_done`.
- Show current count and delta versus previous available week.

- [ ] **Step 3: Run report tests**

Run:

```bash
python -m pytest tests/test_report.py -q
```

Expected: all tests pass.

---

### Task 9: Confluence Client And Publisher

**Files:**

- Create: `wim_metrics/confluence_client.py`
- Create: `tests/test_confluence_client.py`

- [ ] **Step 1: Write mocked Confluence tests**

Add tests for:

```python
def test_find_child_page_by_title_queries_parent_and_space():
    # Fake Confluence search response with matching page.
    # Assert returned page id and version.


def test_create_weekly_page_posts_child_under_parent():
    # Fake successful POST.
    # Assert payload includes space WWIM, parent 6499926021, title, and storage body.


def test_update_parent_page_increments_version():
    # Fake current page version=3.
    # Assert PUT sends version=4.
```

- [ ] **Step 2: Implement Confluence client**

Add `wim_metrics/confluence_client.py` with a `ConfluenceClient` class implementing these public methods:

- `find_child_page(space_key: str, parent_page_id: str, title: str) -> dict | None`
- `get_page(page_id: str) -> dict`
- `create_page(space_key: str, parent_page_id: str, title: str, html: str) -> dict`
- `update_page(page_id: str, title: str, html: str) -> dict`

Also add `markdown_to_storage_html(markdown: str) -> str`.

V1 conversion can support only the generated subset:

- Headings become `<h1>`, `<h2>`, `<h3>`.
- Markdown tables become HTML tables.
- Bullet lines become `<ul><li>`.
- Plain paragraphs become `<p>`.

- [ ] **Step 3: Run Confluence tests**

Run:

```bash
python -m pytest tests/test_confluence_client.py -q
```

Expected: all tests pass.

---

### Task 10: Pipeline And CLI Scripts

**Files:**

- Create: `wim_metrics/pipeline.py`
- Create: `scripts/extract.py`
- Create: `scripts/report.py`
- Create: `scripts/publish.py`
- Create: `scripts/weekly.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write CLI tests**

Add tests that run the scripts with `subprocess.run()`:

```python
def test_extract_rejects_invalid_week_key():
    # Run python scripts/extract.py W26.
    # Assert non-zero exit.
    # Assert stderr contains "Expected ISO week key like 2026-W26".


def test_weekly_accepts_no_week_argument():
    # Import build_parser() from scripts.weekly.
    # Assert week can be omitted and force defaults false.
```

- [ ] **Step 2: Implement pipeline**

Add `wim_metrics/pipeline.py` with these public functions:

- `run_extract(week_key: str, force: bool) -> Path`
- `run_report(week_key: str, force: bool) -> Path`
- `run_publish(week_key: str) -> None`
- `run_weekly(week_key: str | None, force: bool) -> None`

Behavior:

- Parse week with `ReportWeek.parse()`.
- Load config only in commands that need APIs.
- `run_weekly(None, force=False)` uses `default_report_week()`.
- Stop immediately if extraction or report generation raises.

- [ ] **Step 3: Implement CLI wrappers**

Each script should:

- Use `argparse`.
- Print actionable errors to stderr.
- Return exit code `1` on known user/config/API errors.
- Return `0` on success.

Example for `scripts/extract.py`:

```python
#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys

from wim_metrics.pipeline import run_extract


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("week")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        path = run_extract(args.week, args.force)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
python -m pytest tests/test_cli.py -q
```

Expected: all tests pass.

---

### Task 11: GitHub Actions Workflow

**Files:**

- Create: `.github/workflows/weekly.yml`

- [ ] **Step 1: Add workflow**

Create `.github/workflows/weekly.yml`:

```yaml
name: Weekly WIM Support Metrics

on:
  schedule:
    - cron: "0 4 * * 1"
  workflow_dispatch:
    inputs:
      week:
        description: "Optional ISO week key, for example 2026-W26"
        required: false
        type: string
      force:
        description: "Overwrite existing snapshot/report"
        required: false
        default: false
        type: boolean

jobs:
  weekly:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: python -m pip install ".[dev]"
      - name: Run weekly metrics
        env:
          JIRA_BASE_URL: ${{ secrets.JIRA_BASE_URL }}
          JIRA_EMAIL: ${{ secrets.JIRA_EMAIL }}
          JIRA_API_TOKEN: ${{ secrets.JIRA_API_TOKEN }}
          CONFLUENCE_BASE_URL: ${{ secrets.CONFLUENCE_BASE_URL }}
          CONFLUENCE_EMAIL: ${{ secrets.CONFLUENCE_EMAIL }}
          CONFLUENCE_API_TOKEN: ${{ secrets.CONFLUENCE_API_TOKEN }}
          CONFLUENCE_SPACE_KEY: WWIM
          CONFLUENCE_PARENT_PAGE_ID: "6499926021"
        run: |
          if [ -n "${{ inputs.week }}" ]; then
            if [ "${{ inputs.force }}" = "true" ]; then
              python scripts/weekly.py "${{ inputs.week }}" --force
            else
              python scripts/weekly.py "${{ inputs.week }}"
            fi
          else
            python scripts/weekly.py
          fi
      - name: Commit generated data
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/export data/reports
          if git diff --cached --quiet; then
            echo "No generated data changes"
          else
            git commit -m "chore: add weekly WIM support metrics"
            git push
          fi
```

The cron is `04:00 UTC`, which corresponds to `06:00 Europe/Madrid` during summer time. If year-round exact Madrid 06:00 is required across DST, replace the schedule with two UTC cron entries and add a Madrid-time guard in the workflow.

- [ ] **Step 2: Validate workflow change with the test suite**

Run:

```bash
python -m pytest -q
```

Expected: tests still pass.

---

### Task 12: README And End-To-End Verification

**Files:**

- Modify: `README.md`

- [ ] **Step 1: Update README**

Add:

```markdown
## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install ".[dev]"
```

## Required Environment Variables

- `JIRA_BASE_URL`
- `JIRA_EMAIL`
- `JIRA_API_TOKEN`
- `CONFLUENCE_BASE_URL`
- `CONFLUENCE_EMAIL`
- `CONFLUENCE_API_TOKEN`
- `CONFLUENCE_SPACE_KEY` defaults to `WWIM`
- `CONFLUENCE_PARENT_PAGE_ID` defaults to `6499926021`

## Commands

```bash
python scripts/extract.py 2026-W26
python scripts/report.py 2026-W26
python scripts/publish.py 2026-W26
python scripts/weekly.py 2026-W26
python scripts/weekly.py 2026-W26 --force
```

Scheduled runs use the previous completed ISO week.
```

- [ ] **Step 2: Run the complete unit suite**

Run:

```bash
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 3: Run local fixture pipeline**

Run the extraction/report path with fake clients from tests or a test-only fixture command if added during Task 7.

Expected:

- `data/export/2026-W26.json` contains sorted `issues` and `metrics`.
- `data/reports/2026-W26.md` contains weekly sections and issue links.
- Re-running without `--force` fails before overwriting.
- Re-running with `--force` produces stable output.

- [ ] **Step 4: Manual live smoke test**

With real env vars configured, run:

```bash
python scripts/extract.py 2026-W26 --force
python scripts/report.py 2026-W26 --force
```

Inspect generated files before publishing.

Then run:

```bash
python scripts/publish.py 2026-W26
```

Expected:

- Weekly child page title is `W26 2026-06-22 | WIM Support - Weekly Metrics`.
- Parent page `6499926021` contains the rolling eight-week historical summary.

---

## Self-Review Checklist

- Spec coverage: week model, Jira base JQL, changelog assignment dates, sprint overlap, immutable JSON, metrics, reports, Confluence publishing, GitHub Actions, and tests are each covered by at least one task.
- No commits: this plan intentionally does not ask the implementer to commit because the user explicitly requested no commits.
- Open implementation risk: Jira Sprint may be exposed under a site-specific custom field ID rather than the literal field name `Sprint`; Task 6 and Task 7 should include field lookup or a configurable `JIRA_SPRINT_FIELD` if live testing confirms that need.
- Open operational risk: GitHub Actions UTC cron cannot express Europe/Madrid daylight-saving changes with one static UTC time. The plan documents the summer-time cron and the DST guard option.
