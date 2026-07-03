# wim-support-metrics

Automated engine that extracts WIM support metrics from Jira, stores immutable weekly snapshots, generates Markdown reports, and publishes weekly metrics to Confluence.

## Local Setup

Use Python 3.11 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
python3 -m pytest -q
```

## Configuration

The extract and publish commands read credentials from environment variables.

Required:

```bash
export JIRA_BASE_URL="https://theknotww.atlassian.net"
export JIRA_EMAIL="name@example.com"
export JIRA_API_TOKEN="jira-api-token"
export CONFLUENCE_BASE_URL="https://theknotww.atlassian.net/wiki"
export CONFLUENCE_EMAIL="name@example.com"
export CONFLUENCE_API_TOKEN="confluence-api-token"
```

Optional:

```bash
export JIRA_SPRINT_FIELD="customfield_10261"
export CONFLUENCE_SPACE_KEY="WWIM"
export CONFLUENCE_PARENT_PAGE_ID="6499926021"
```

`JIRA_SPRINT_FIELD` defaults to `customfield_10261`, which is the Jira sprint field used to calculate squad planned capacity.

For GitHub Actions, configure these repository secrets:

```text
JIRA_BASE_URL
JIRA_EMAIL
JIRA_API_TOKEN
CONFLUENCE_BASE_URL
CONFLUENCE_EMAIL
CONFLUENCE_API_TOKEN
```

## Commands

Use ISO week keys in `YYYY-Www` format.

```bash
python3 scripts/extract.py 2026-W26
python3 scripts/report.py 2026-W26
python3 scripts/publish.py 2026-W26
python3 scripts/weekly.py 2026-W26
python3 scripts/weekly.py 2026-W26 --force
```

`extract.py` writes `data/export/<week>.json`. `report.py` writes `data/reports/<week>.md`. Without `--force`, existing generated files are left untouched and the command exits with an error.

`weekly.py` can omit the week argument:

```bash
python3 scripts/weekly.py
```

When no week is provided, scheduled and local weekly runs use the previous completed ISO week in `Europe/Madrid`.

## Pipeline

The weekly pipeline runs three steps:

1. `extract.py` searches Jira with `project = GPWIM AND component in (Support)`, expands changelogs, reads sprint metadata, and writes an immutable JSON snapshot.
2. `report.py` renders the snapshot into a Markdown report ready for Confluence.
3. `publish.py` creates or updates the weekly Confluence child page and refreshes the parent historical summary.

Snapshots include the source issue data, assignment dates derived from component changelogs, sprint overlap flags, and calculated metrics. The report can be regenerated from the snapshot without re-querying Jira.

## Report Format

Weekly reports contain these top-level sections:

- Executive Summary
- Flow Metrics
- Inventory Metrics
- Capacity Metrics
- Metrics by Squad

All main report tables use two columns: `Metric` and `Count`. When a metric has issues, the count is rendered as `<count> (query)`, where `query` links to a Jira search for the exact issue keys behind that metric. The report no longer lists detailed ticket rows.

Executive Summary contains:

- General Queue
- Squad Queue
- Squad Planned
- Squad Done

Flow metrics include `Resolved`, `Resolved without code`, and `Closed as duplicate`. Cancelled issues are still present in the snapshot metrics but are not displayed in the report.

Inventory metrics split General Queue and Squad Queue by age buckets:

- `new`
- `> 1w`
- `> 2w`
- `> 1m`
- `> 2m`
- `> 3m`

Capacity metrics include:

- Squad Planned
- Squad In Progress
- Squad Done

`Squad Planned` is calculated from squad queue issues whose Jira sprint metadata overlaps the selected ISO week. `Squad Done` in the Executive Summary uses the weekly resolved metric, while the Capacity Metrics `Squad Done` uses planned squad issues with Jira status category `Done`.

## Metrics by Squad

The report adds collapsible squad sections for Phoenix and Unicorns. Each section repeats the relevant Summary, Flow Metrics, Inventory Metrics, and Capacity Metrics with this table shape:

```markdown
| Metric | Phoenix | Total |
| --- | ---: | ---: |
| Squad Queue | 5 (query) | 10 (50%) |
```

The squad column contains that squad's count and Jira query link. The `Total` column contains the global metric count and the percentage represented by the squad count. For zero totals, the percentage is rendered as `0%`.

## Scheduled Runs

GitHub Actions runs every Monday with cron `0 4 * * 1`, installs `.[dev]`, runs `python scripts/weekly.py`, and commits generated changes under `data/export` and `data/reports`.

The workflow can also be started manually with optional `week` and `force` inputs. `week` accepts an ISO week key like `2026-W26`; `force` overwrites existing generated files.
