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
            start = datetime.fromisocalendar(iso_year, iso_week, 1).replace(
                tzinfo=MADRID
            )
        except (AttributeError, ValueError, TypeError) as exc:
            raise ValueError("Expected ISO week key like 2026-W26") from exc

        if f"{iso_year:04d}-W{iso_week:02d}" != key:
            raise ValueError("Expected ISO week key like 2026-W26")

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
    if now is None:
        current = datetime.now(MADRID)
    else:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("default_report_week requires an aware datetime")
        current = now.astimezone(MADRID)
    previous_week_date = current.date() - timedelta(days=7)
    iso = previous_week_date.isocalendar()
    return ReportWeek.parse(f"{iso.year:04d}-W{iso.week:02d}")
