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
