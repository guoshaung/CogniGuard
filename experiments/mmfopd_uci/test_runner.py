import copy
import json

import numpy as np
import pytest

from experiments.mmfopd_uci.runner import (
    CONFIG, FIELDS, INPUT_FIELDS, METHODS, PRIVATE, HASH_SEED,
    make_profile, release, select_fields, split_indices, parse_csv, run,
)


def row():
    # Synthetic interface fixture only; never counted as experimental evidence.
    r = {field: "1" for field in FIELDS}
    r.update(G1="10", G2="12", G3="19", health="3", Dalc="1", Walc="1", romantic="no", Pstatus="T")
    return r


def test_target_and_identifiers_not_in_selector():
    r = row()
    p, t = make_profile(r, 0)
    assert {record.record_id for record in p.profile_records} == set(INPUT_FIELDS)
    changed = dict(r, G3="0")
    p2, t2 = make_profile(changed, 0)
    assert p == p2 and t == t2
    assert not p.local_only_fields
    assert next(x for x in p.profile_records if x.record_id == "G1").value == .5
    assert not any(x.type in ("preference", "error_pattern") for x in p.profile_records)


def test_release_excludes_target_and_its_mask():
    values = release(row(), set(INPUT_FIELDS), "health")
    assert not any("health" in key for key in values)
    assert not any("G3" in key or "student" in key for key in values)
    empty = release(row(), set())
    assert all(value == 0 for value in empty.values())
    assert not any(key.startswith("value:") for key in empty)
    with pytest.raises(ValueError):
        release(row(), {"G3"})


def test_methods_use_real_selector_and_leave_config_unchanged(monkeypatch):
    p, t = make_profile(row(), 0)
    before = copy.deepcopy(CONFIG)
    from experiments.mmfopd_uci import runner
    calls = []
    actual = runner.ProfileSelector.select
    def wrapped(self, *args):
        calls.append((self.use_orthogonal, self.use_task_attention, self.use_bottleneck))
        return actual(self, *args)
    monkeypatch.setattr(runner.ProfileSelector, "select", wrapped)
    for method in METHODS:
        result = select_fields(method, p, t, 17, ["G1", "G2", "studytime"])
        assert result <= set(INPUT_FIELDS)
        if method in ("DropSensitive", "RandomSafe-3", "SafeTaskTopK-3", "TrainMI-SafeTopK-3", "MM-FOPD"):
            assert not result & PRIVATE
    assert calls == [(True, True, True), (False, True, True), (True, False, True), (True, True, False)]
    assert before == CONFIG


def test_split_disjoint_reproducible():
    records = [dict(row(), G3=str(5 if i % 2 else 15)) for i in range(100)]
    split = split_indices(records, 17)
    assert [len(part) for part in split] == [60, 20, 20]
    assert len(set().union(*(set(part) for part in split))) == 100
    assert all(not set(split[i]) & set(split[j]) for i in range(3) for j in range(i))
    assert all(np.array_equal(a, b) for a, b in zip(split, split_indices(records, 17)))


def test_csv_schema_and_missing_rejected():
    content = (";".join(FIELDS) + "\n" + ";".join(row()[field] for field in FIELDS) + "\n").encode()
    assert len(parse_csv(content, 1)) == 1
    with pytest.raises(ValueError):
        parse_csv(content, 2)
    with pytest.raises(ValueError):
        parse_csv(content.replace(b"health", b"private"), 1)


def test_fresh_output_and_frozen_hash_seed(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTHONHASHSEED", raising=False)
    with pytest.raises(ValueError, match="PYTHONHASHSEED"):
        run(tmp_path / "cache", tmp_path / "result", [17])
    monkeypatch.setenv("PYTHONHASHSEED", HASH_SEED)
    with pytest.raises(FileExistsError):
        run(tmp_path / "cache", tmp_path, [17])
