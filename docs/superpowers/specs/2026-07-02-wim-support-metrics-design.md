# WIM Support Metrics Engine Design

## Overview

The WIM Support Metrics Engine is a local-first Python automation that extracts weekly Jira metrics for WIM support, stores immutable JSON snapshots in Git, generates Markdown reports, and publishes weekly and historical summaries to Confluence.

The implementation favors maintainability and auditability over request optimization. Each metric is calculated from issue sets, not raw counts, so every reported number can be traced back to the Jira issues that produced it.

## Architecture

The project will use a small Python package named `wim_metrics` plus CLI scripts under `scripts/`.

Core modules:

- `wim_metrics.week`: parses ISO week keys such as `2026-W26`, computes Madrid-time week boundaries, formats Confluence titles, and computes the default scheduled week.
- `wim_metrics.config`: reads and validates Jira and Confluence environment variables.
- `wim_metrics.jira_client`: wraps Jira REST calls for JQL search, issue changelogs, sprint metadata, and field lookup.
- `wim_metrics.extractor`: fetches the Jira issue universe, enriches issues with changelog-derived dates and sprint metadata, calculates metrics, and writes immutable JSON snapshots.
- `wim_metrics.metrics`: defines metric rules. Each metric returns sorted issue keys plus a count.
- `wim_metrics.report`: renders weekly Markdown reports and the rolling eight-week historical summary.
- `wim_metrics.confluence_client`: creates or updates weekly child pages and updates the parent historical page.

CLI commands:

- `python scripts/extract.py 2026-W26 [--force]`
- `python scripts/report.py 2026-W26 [--force]`
- `python scripts/publish.py 2026-W26`
- `python scripts/weekly.py [2026-W26] [--force]`

`weekly.py` runs extract, report, and publish. When no week is provided, it uses the previous completed ISO week. The GitHub Actions schedule runs Monday at 06:00 Europe/Madrid time.

## Week Model

Weeks use ISO year-week keys in the form `YYYY-Www`, for example `2026-W26`.

For `2026-W26`:

- Start: `2026-06-22T00:00:00+02:00`
- End exclusive: `2026-06-29T00:00:00+02:00`
- Display end date: `2026-06-28`
- Timezone: `Europe/Madrid`

All week filtering uses a half-open interval:

```text
timestamp >= week.start
AND timestamp < week.end_exclusive
```

Weekly Confluence page titles use the ISO week number and Monday date:

```text
W26 2026-06-22 | WIM Support - Weekly Metrics
```

## Jira Source Rules

The base Jira issue universe is:

```jql
project = GPWIM AND component in (Support)
```

Current components determine queue membership:

- Support queue: current components include `Support` and do not include `Phoenix` or `Unicorns`.
- Squad queue: current components include `Support` and include either `Phoenix` or `Unicorns`.

Assignment dates are derived from Jira changelog history:

- `assigned_to_support_at`: first changelog timestamp where component `Support` was added.
- `assigned_to_squad_at`: first changelog timestamp where component `Phoenix` or `Unicorns` was added while the issue belongs to Support.

If `assigned_to_support_at` cannot be derived from changelog history, support age falls back to `created_at`. If `assigned_to_squad_at` cannot be derived, the issue remains in total squad queue metrics but is excluded from squad age bucket metrics.

## Sprint Rules

Capacity metrics use Jira Software sprint metadata, not JQL alone.

Extraction reads each issue's non-empty sprint field, fetches sprint metadata, and marks a sprint as matching the selected report week when:

```text
sprint.start_date < week.end_exclusive
AND sprint.end_date > week.start
```

Two-week sprints therefore contribute to both weekly reports they overlap.

## Data Contract

Snapshots are written to:

```text
data/export/2026-W26.json
```

Weekly Markdown reports are written to:

```text
data/reports/2026-W26.md
```

Snapshot shape:

```json
{
  "schema_version": 1,
  "week": {
    "key": "2026-W26",
    "iso_year": 2026,
    "iso_week": 26,
    "start_date": "2026-06-22",
    "end_date": "2026-06-28",
    "timezone": "Europe/Madrid"
  },
  "source": {
    "jira_base_jql": "project = GPWIM AND component in (Support)",
    "project_key": "GPWIM",
    "support_component": "Support",
    "squad_components": ["Phoenix", "Unicorns"]
  },
  "issues": {
    "GPWIM-123": {
      "key": "GPWIM-123",
      "summary": "Example issue",
      "url": "https://theknotww.atlassian.net/browse/GPWIM-123",
      "status": "In Progress",
      "status_category": "In Progress",
      "assignee": "Jane Doe",
      "components": ["Support", "Phoenix"],
      "labels": ["wim-support:no-code"],
      "created_at": "2026-06-01T09:30:00+02:00",
      "resolved_at": null,
      "assigned_to_support_at": "2026-06-03T10:00:00+02:00",
      "assigned_to_squad_at": "2026-06-10T11:00:00+02:00",
      "sprints": [
        {
          "id": 123,
          "name": "WIM Sprint 42",
          "state": "active",
          "start_date": "2026-06-15T09:00:00+02:00",
          "end_date": "2026-06-29T09:00:00+02:00",
          "overlaps_selected_week": true
        }
      ]
    }
  },
  "metrics": {
    "support_queue_new": {
      "title": "Support Queue (New)",
      "count": 1,
      "issues": ["GPWIM-123"]
    }
  }
}
```

The JSON writer sorts issue keys and metric IDs and writes stable pretty-printed JSON. Snapshots omit `generated_at` so repeated extraction from identical Jira data produces identical output.

## Metric Rules

All metrics return a sorted issue-key list and a count.

Queue totals:

- `support_queue`: current Support queue issues.
- `squad_queue`: current Squad queue issues.

Age buckets are mutually exclusive and measured at `week.end_exclusive`:

- `new`: age `< 7 days`
- `one_week_old`: age `>= 7 days and < 14 days`
- `two_weeks_old`: age `>= 14 days and < 30 days`
- `one_month_old`: age `>= 30 days and < 60 days`
- `two_months_old`: age `>= 60 days and < 90 days`
- `three_months_old`: age `>= 90 days`

Support age metrics use `assigned_to_support_at`, falling back to `created_at` when needed.

Squad age metrics use `assigned_to_squad_at`. Issues without `assigned_to_squad_at` are excluded from squad age buckets but included in `squad_queue`.

Resolution metrics:

- `resolved`: `resolved_at >= week.start` and `resolved_at < week.end_exclusive`.
- `no_code`: resolved in week and label `wim-support:no-code`.
- `duplicate`: resolved in week and label `wim-support:duplicate`.
- `cancelled`: resolved in week and label `wim-support:cancelled`.

`wim-support:wrongly-routed` is intentionally excluded from V1.

Capacity metrics:

- `squad_planned`: squad queue issue with at least one sprint overlapping the selected week.
- `squad_in_progress`: `squad_planned` issue with status category `In Progress`.
- `squad_done`: `squad_planned` issue with status category `Done`.

## Reporting

The weekly report contains:

- Header with week key and date range.
- Deterministic executive summary using queue totals, resolution counts, and available historical deltas.
- Flow metrics: resolved, no-code, duplicate, cancelled.
- Inventory metrics: support queue totals and age buckets, squad queue totals and age buckets.
- Capacity metrics: planned, in progress, done.
- Detailed issue tables per metric with issue key, summary, status, assignee, components, labels, age, and Jira link.

The historical summary reads the latest eight available snapshots up to the selected week. It shows major metrics by week, delta from the previous available week, and simple trend arrows.

## Confluence Publishing

Confluence settings:

- Space key: `WWIM`
- Parent page ID: `6499926021`
- Parent page URL: `https://theknotww.atlassian.net/wiki/spaces/WWIM/pages/6499926021/WIM+Support+-+Weekly+Metrics`

Publishing behavior:

- Create or update the weekly page as a child of parent page `6499926021`.
- Update the parent page with the rolling eight-week historical summary.
- Find weekly pages by exact title under the parent page.
- Convert generated report content to conservative Confluence-compatible HTML. V1 does not need a general-purpose Markdown-to-Confluence converter.

## GitHub Actions

The workflow runs every Monday at 06:00 Europe/Madrid time.

The workflow:

1. Checks out the repository.
2. Installs Python dependencies.
3. Runs `python scripts/weekly.py`.
4. Commits changed `data/export/*.json` and `data/reports/*.md` files back to the repository when changes exist.

Business logic remains in Python modules and scripts. GitHub Actions only orchestrates.

## Regeneration And Idempotency

Scheduled runs are create-only:

- Extraction fails if `data/export/<week>.json` exists.
- Report generation fails if `data/reports/<week>.md` exists.
- Publishing is not reached if extraction or report generation fails.

Manual regeneration requires `--force`:

- `extract.py <week> --force` overwrites the JSON snapshot.
- `report.py <week> --force` overwrites the Markdown report.
- `weekly.py <week> --force` overwrites JSON, Markdown, and Confluence content for that week.

Running the same command against the same inputs produces stable JSON and Markdown content.

## Error Handling

The system fails fast with actionable messages for:

- Missing Jira or Confluence environment variables.
- Invalid week keys, including an example of the expected `YYYY-Www` format.
- Existing snapshot or report files without `--force`.
- Jira authentication failures.
- Jira search, changelog, or sprint metadata failures.
- Confluence weekly page create/update failures.
- Confluence parent page update failures.
- Missing exported JSON or Markdown report inputs.

Extraction failure aborts the pipeline. Publishing never runs with missing or incomplete data.

## Testing Strategy

Unit tests cover:

- ISO week parsing and Madrid-time boundaries.
- Default scheduled week selection.
- Weekly Confluence title formatting.
- Age bucket classification.
- Sprint overlap classification.
- Metric definitions.
- Stable JSON serialization.
- Weekly and historical report rendering.

API client tests use mocked HTTP responses for Jira and Confluence.

CLI tests cover invalid week keys, missing files, create-only behavior, and `--force` overwrite behavior.

An integration-style fixture test uses representative Jira issue, changelog, and sprint data to produce a stable snapshot and weekly report.
