import json

import pytest

from wim_metrics.serialization import ExistingOutputError, read_json, write_json


def test_write_json_is_stable_and_sorted(tmp_path):
    path = tmp_path / "snapshot.json"
    write_json(path, {"b": 1, "a": {"d": 4, "c": 3}}, force=False)

    assert path.read_text() == json.dumps(
        {"a": {"c": 3, "d": 4}, "b": 1},
        indent=2,
        sort_keys=True,
    ) + "\n"


def test_write_json_refuses_existing_file_without_force(tmp_path):
    path = tmp_path / "snapshot.json"
    path.write_text("{}\n")

    with pytest.raises(ExistingOutputError, match="already exists"):
        write_json(path, {"a": 1}, force=False)


def test_write_json_allows_force(tmp_path):
    path = tmp_path / "snapshot.json"
    path.write_text("{}\n")

    write_json(path, {"a": 1}, force=True)

    assert read_json(path) == {"a": 1}
