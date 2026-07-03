from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_extract_rejects_invalid_week_key():
    result = subprocess.run(
        [sys.executable, "scripts/extract.py", "W26"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Expected ISO week key like 2026-W26" in result.stderr


def test_weekly_accepts_no_week_argument():
    from scripts.weekly import build_parser

    args = build_parser().parse_args([])

    assert args.week is None
    assert args.force is False
