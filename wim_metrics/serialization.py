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
