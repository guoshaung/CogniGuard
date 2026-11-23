"""The smoke comparison writes both tables."""

from __future__ import annotations

import csv

from experiments.capd_eval_20261123.run import COLUMNS, smoke


def test_smoke_writes_csv_and_markdown(tmp_path) -> None:
    csv_path, md_path = smoke(tmp_path)
    assert csv_path.is_file()
    assert md_path.is_file()
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == list(COLUMNS)
    assert [row[0] for row in rows[1:]] == [
        "no_defense",
        "per_recipient_budget",
        "global_budget",
        "capd",
    ]
    lines = md_path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "| " + " | ".join(COLUMNS) + " |"
    assert [line.split("|")[1].strip() for line in lines[2:]] == [
        "no_defense",
        "per_recipient_budget",
        "global_budget",
        "capd",
    ]
