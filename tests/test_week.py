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


def test_default_week_rejects_naive_datetime():
    now = datetime(2026, 6, 29, 6, 0)

    with pytest.raises(ValueError, match="requires an aware datetime"):
        default_report_week(now)


def test_default_week_handles_iso_year_rollover():
    now = datetime(2027, 1, 4, 6, 0, tzinfo=ZoneInfo("Europe/Madrid"))

    assert default_report_week(now).key == "2026-W53"
