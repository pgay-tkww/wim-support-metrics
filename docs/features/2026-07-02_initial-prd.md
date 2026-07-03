# PRD - WIM Support Metrics Engine

## Status

Draft v1

## Authors

Pau Gay

---

# Overview

The WIM Support Metrics Engine is an internal automation that generates weekly support metrics from Jira and publishes them into Confluence.

Its goal is to provide a reliable, repeatable and fully automated weekly snapshot of the WIM support process without requiring any manual work.

The system is intentionally designed around simplicity and maintainability rather than runtime performance. It executes once per week, generates immutable weekly snapshots and uses those snapshots as the single source of truth for reporting.

---

# Goals

The system must:

* Automatically extract support metrics from Jira every Monday.
* Store a weekly immutable snapshot in Git.
* Generate weekly Confluence reports.
* Maintain historical trends across previous weeks.
* Allow any historical week to be regenerated.
* Be executable locally without GitHub Actions.

---

# Out of Scope

The following capabilities are intentionally excluded from V1:

* AI-generated analysis.
* Real-time dashboards.
* Live synchronization with Jira.
* Performance optimizations such as query caching or metric dependency graphs.
* Predictive analytics.

---

# Design Principles

## 1. Weekly snapshots are immutable

Each execution generates a snapshot for a specific week.

Example:

```
W26
```

Once generated, the snapshot becomes the source of truth for that week.

Historical weeks may be regenerated manually if required.

---

## 2. Metric Definitions

Every metric is represented by a Metric Definition.

A Metric Definition is responsible for:

* describing the metric
* retrieving the issues
* returning the matching issue set

A metric never returns only a number.

Instead it returns a collection of issues.

```
Metric Definition

↓

Issue Set

↓

count = len(issue_set)
```

This makes every metric fully auditable.

---

## 3. Simplicity over optimization

Each Metric Definition is independent.

Multiple metrics are allowed to execute independent Jira queries even if those queries overlap.

Reducing implementation complexity is preferred over minimizing Jira requests.

---

## 4. JSON is the source of truth

Confluence never talks directly to Jira.

The reporting layer only consumes the exported JSON.

This allows:

* reproducible reports
* easier debugging
* future consumers (AI, dashboards, etc.)

---

## 5. GitHub Actions only orchestrates

Business logic must never live inside GitHub Actions.

Every step must be executable locally.

---

# Architecture

```
                 GitHub Action

                        │

                Every Monday 06:00

                        │

                 weekly.sh

        ┌───────────────┴───────────────┐

        │                               │

 extract.py                      publish.py

        │                               │

data/export/W26.json          Confluence
```

The GitHub Action simply executes the scripts.

All business logic lives inside the scripts.

---

# Repository Structure

```
support-metrics/

data/
    export/
        W26.json

    reports/
        W26.md

extract/
    ...

publish/
    ...

metrics/
    ...

scripts/
    extract.py
    publish.py
    weekly.py

.github/
    workflows/
        weekly.yml
```

---

# Execution

Automatic execution:

Every Monday at 06:00.

Manual execution:

```
python scripts/extract.py W26

python scripts/publish.py W26

python scripts/weekly.py W26
```

All scripts must be idempotent.

Running the same command multiple times must produce the same output.

---

# Pipeline

## Phase 1

Extract data from Jira.

Input

```
W26
```

Output

```
data/export/W26.json
```

---

## Phase 2

Generate Markdown report.

Input

```
data/export/W26.json
```

Output

```
data/reports/W26.md
```

---

## Phase 3

Publish to Confluence.

Actions:

* Create (or update) the weekly report page.
* Update the historical trends page.

---

# Data Model

```
{
    week,

    generated_at,

    issues {

        GPS-123 {

            ...

        }

    },

    metrics {

        support_queue_new {

            count,

            issues[]

        }

    }

}
```

The issue catalog stores each issue only once.

Metrics only reference issue keys.

---

# Issue Model

Each issue contains the minimum information required for reporting.

Suggested fields:

* key
* summary
* url
* status
* assignee
* components
* labels
* created_at
* resolved_at
* assigned_to_support_at
* assigned_to_squad_at

Additional fields may be added later without changing the metric model.

---

# Metric Definition

Every metric implements the same contract.

```
id

title

description

engine

query

issues[]

count
```

The engine may execute:

* a Jira query
* a Python function

This detail is transparent to the rest of the system.

---

# Metric Catalog

## Support Queue

### Support Queue (New)

Definition

Tickets currently in Support for less than 7 days.

---

### Support Queue (Old)

Definition

Tickets currently in Support for more than 7 days.

These tickets indicate that triage is not keeping up.

---

## Squad Queue

### Squad Queue

Definition

Tickets assigned to a squad.

(Component = Support + Squad)

---

### Squad Queue (New)

Less than 7 days since assignment to the squad.

---

### Squad Queue (1 Week Old)

More than 7 days.

---

### Squad Queue (2 Weeks Old)

More than 14 days.

---

### Squad Queue (1 Month)

More than 30 days.

---

### Squad Queue (2 Months)

More than 60 days.

---

### Squad Queue (3 Months)

More than 90 days.

---

## Resolution

### Resolved

Tickets resolved during the selected week.

---

### Wrongly Routed

Resolved during the selected week.

Must contain label:

```
wim-support:wrongly-routed
```

---

### No Code

Resolved during the selected week.

Must contain label:

```
wim-support:no-code
```

---

### Duplicate

Resolved during the selected week.

Must contain label:

```
wim-support:duplicate
```

---

### Cancelled

Resolved during the selected week.

Must contain label:

```
wim-support:cancelled
```

---

## Capacity

### Squad Queue

Tickets assigned to a squad.

---

### Squad Planned

Tickets assigned to a sprint.

Not resolved.

---

### Squad In Progress

Tickets assigned to a sprint.

Currently in progress.

---

### Squad Done

Tickets assigned to a sprint.

Resolved.

Capacity percentages will be calculated later during visualization.

---

# Weekly Report

The weekly report contains:

* Executive Summary
* Flow Metrics
* Inventory Metrics
* Capacity Metrics
* Detailed issue tables

Every metric includes:

* count
* issue list
* links back to Jira

---

# Historical Report

The parent page contains the previous eight weeks.

For every metric it shows:

* weekly values
* delta versus previous week
* trend arrows
* visual indicators

---

# Error Handling

Failures must produce clear and actionable error messages.

Examples:

* Jira authentication failed.
* Jira query failed.
* Confluence publishing failed.
* Invalid week.
* Missing exported data.

If extraction fails, the pipeline aborts.

Publishing never runs with incomplete data.

---

# Future Enhancements

The following capabilities are intentionally left for future versions:

* AI-generated weekly analysis.
* Trend prediction.
* Capacity forecasting.
* Custom dashboards.
* Additional Metric Definitions.
* Query optimization.
* Cached Jira responses.

---

# Success Criteria

The project is considered successful when:

* Weekly metrics are generated automatically.
* Reports require zero manual intervention.
* Historical weeks can be regenerated.
* Every metric is auditable through its issue list.
* Adding a new metric only requires creating a new Metric Definition.

