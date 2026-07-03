# Copilot Instructions for `wim-support-metrics`

## Build, test, and lint commands

```bash
# Install project + dev dependencies
python3 -m pip install -e ".[dev]"

# Run all tests
python3 -m pytest -q

# Run one test file
python3 -m pytest -q tests/test_metrics.py

# Run one test case
python3 -m pytest -q tests/test_metrics.py::test_age_bucket_boundaries
```

There is no dedicated lint command configured in this repository today.

## High-level architecture

The project is a weekly pipeline that moves from Jira data extraction to Markdown report generation and then Confluence publishing:

1. `scripts/extract.py` -> `wim_metrics.pipeline.run_extract` -> `wim_metrics.extractor.extract_week` writes immutable snapshots to `data/export/<week>.json`.
2. `scripts/report.py` -> `wim_metrics.pipeline.run_report` -> `wim_metrics.report.write_weekly_report` reads the snapshot and writes `data/reports/<week>.md`.
3. `scripts/publish.py` -> `wim_metrics.pipeline.run_publish` publishes weekly report content to Confluence and refreshes the historical summary on the parent page.
4. `scripts/weekly.py` orchestrates all 3 steps in order.

Core modules:

- `wim_metrics/week.py`: ISO week parsing (`YYYY-Www`), Europe/Madrid week boundaries, default week selection, Confluence page title format.
- `wim_metrics/config.py`: environment validation and defaults (Jira + Confluence credentials/settings).
- `wim_metrics/jira_client.py`: Jira API paging for issue search/changelog/sprint metadata.
- `wim_metrics/extractor.py`: issue enrichment (assignment dates + sprint overlap) and snapshot assembly.
- `wim_metrics/metrics.py`: queue/flow/capacity metric calculations.
- `wim_metrics/report.py`: Markdown report rendering and historical summary generation.
- `wim_metrics/confluence_client.py`: Confluence page lookup/create/update plus constrained Markdown->storage HTML conversion.
- `wim_metrics/serialization.py`: stable JSON read/write with create-only safeguards.

Operational entrypoints from `README.md`:

```bash
python3 scripts/extract.py 2026-W26
python3 scripts/report.py 2026-W26
python3 scripts/publish.py 2026-W26
python3 scripts/weekly.py 2026-W26
python3 scripts/weekly.py 2026-W26 --force
python3 scripts/weekly.py
```

## Key conventions in this codebase

- **Week handling is strict and timezone-aware**: week keys must be exactly `YYYY-Www`; calculations use `Europe/Madrid`; week intervals are half-open (`start <= ts < end_exclusive`).
- **Create-only outputs by default**: extraction/report fail if target file exists; explicit `--force` is required to overwrite (`ExistingOutputError`).
- **Snapshot-first contract**: report/publish logic consume generated snapshots; snapshots are treated as immutable historical source of truth.
- **Deterministic artifacts**: snapshot JSON is written with sorted keys and fixed formatting; issue keys and metric issue lists are sorted.
- **Queue classification uses current components**:
  - Support queue: has `Support` and no squad component.
  - Squad queue: has `Support` plus `Phoenix` or `Unicorns`.
- **Assignment dates come from component changelog transitions**, not only current fields; support age can fall back to `created_at`, squad age does not.
- **Capacity metrics depend on sprint overlap metadata** from Jira sprint field (`JIRA_SPRINT_FIELD`, default `customfield_10261`), not only labels/status.
- **Report format is intentionally constrained**:
  - Main sections: Executive Summary, Flow Metrics, Inventory Metrics, Capacity Metrics, Metrics by Squad.
  - Main tables are two-column (`Metric | Count`), where count may embed a Jira query link.
  - Squad breakdown uses collapsible `<details>` blocks and per-squad vs total columns.
- **Publishing semantics**:
  - Weekly page is found/created under the configured parent page.
  - Parent page is updated with a rolling historical summary from snapshots up to the selected week.
- **CI behavior** (`.github/workflows/weekly.yml`): scheduled Monday run executes `scripts/weekly.py`, then commits generated `data/export` and `data/reports` changes.
