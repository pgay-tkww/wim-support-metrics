from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wim_metrics.config import ConfigError
from wim_metrics.pipeline import run_extract
from wim_metrics.serialization import ExistingOutputError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract a weekly WIM support snapshot.")
    parser.add_argument("week", help="ISO week key like 2026-W26")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        path = run_extract(args.week, force=args.force)
    except (ConfigError, ExistingOutputError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
