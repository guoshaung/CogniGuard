from __future__ import annotations

from pathlib import Path

from protection.student_profile.src.fopd.context_card import build_context_card
from protection.student_profile.src.fopd.profile_selector import ProfileSelector
from protection.student_profile.src.fopd.task_parser import parse_task
from protection.student_profile.src.pipeline.run_demo import load_config, load_profiles
from protection.common.text_utils import read_jsonl


ROOT = Path(__file__).resolve().parents[1]


def test_fopd_no_local_only_leak() -> None:
    config = load_config(ROOT / "configs/default.yaml")
    profiles = load_profiles(ROOT / "data/profiles.jsonl")
    task = parse_task(read_jsonl(ROOT / "data/student_questions.jsonl")[0])
    selected = ProfileSelector(config).select(profiles[task.student_id], task)
    card, _ = build_context_card(profiles[task.student_id], task, selected)
    assert "星河中学" not in card
    assert "家长辅导较少" not in card


def test_fopd_selects_relevant_records() -> None:
    config = load_config(ROOT / "configs/default.yaml")
    profiles = load_profiles(ROOT / "data/profiles.jsonl")
    task = parse_task(read_jsonl(ROOT / "data/student_questions.jsonl")[0])
    selected = ProfileSelector(config).select(profiles[task.student_id], task)
    ids = {x.record.record_id for x in selected}
    assert {"p1", "p2"} <= ids
    assert "p4" not in ids
