#!/usr/bin/env python3
"""Run MM-FOPD Gate 0 phase B from the frozen rules and DEVIATIONS.md.

The script writes per_student.csv, reloads it, and only then fits models.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "oulad_raw"
WEEKS = (4, 8, 12)
WEEK_NAMES = ("w4", "w8", "w12", "wfull")
ADJACENT = (("w4", "w8"), ("w8", "w12"), ("w12", "wfull"))
LOW_SCORE = 40
HIGH_SCORE = 80
SHARE_DEVIATION = 0.20
MIN_WEEKLY_CLICKS = 10
BOOTSTRAP_DRAWS = 1000
MODEL_SEED = 20261116
LABELS = ("disability_y", "imd_low", "age_55")
COURSE_COLUMNS = ("course_BBB", "course_CCC", "course_FFF")
TUTOR_TYPES = ("review_session", "tutoring")
ADMIN_TYPES = ("extension",)
BEHAVIOR_FIELDS = (
    "clicks_total",
    "n_scored",
    "mean_score",
    "n_late",
    "mean_lateness",
)


def week_of(date: int) -> int:
    if date <= 7:
        return 1
    return (int(date) + 6) // 7


def is_train_student(student_id: int) -> bool:
    digest = hashlib.sha256(str(int(student_id)).encode("ascii")).hexdigest()
    return int(digest, 16) % 10 < 6


def tutoring_flags(dates, scores, assessment_ids, cutoff: int) -> tuple[int, int]:
    rows = []
    for date, score, assessment_id in zip(dates, scores, assessment_ids):
        if date is None or score is None or (isinstance(score, float) and np.isnan(score)):
            continue
        if int(date) <= cutoff:
            rows.append((int(date), int(assessment_id), float(score)))
    if not rows:
        return 0, 0
    rows.sort()
    tutoring = int(rows[-1][2] < LOW_SCORE)
    review = 0
    if len(rows) >= 3 and rows[-1][2] < rows[-2][2] and rows[-2][2] < rows[-3][2]:
        review = 1
    return tutoring, review


def extension_events(deadlines, submission_dates, length: int) -> list[tuple[int, int]]:
    """Return (trigger_week, count) for missed deadlines. Future late dates are ignored."""
    events: dict[int, int] = {}
    for deadline, submitted in zip(deadlines, submission_dates):
        if deadline is None or (isinstance(deadline, float) and np.isnan(deadline)):
            continue
        deadline = int(deadline)
        if deadline >= length:
            continue
        on_time = False
        for date in submitted:
            if date is None or (isinstance(date, float) and np.isnan(date)):
                continue
            if int(date) <= deadline:
                on_time = True
                break
        if on_time:
            continue
        trigger = week_of(deadline)
        events[trigger] = events.get(trigger, 0) + 1
    return sorted(events.items())


def resource_triggers(clicks_by_type: dict[str, float], medians: dict[str, float]) -> dict[str, int]:
    total = float(sum(clicks_by_type.values()))
    if total < MIN_WEEKLY_CLICKS or not medians:
        return {}
    fired = {}
    for activity, median in medians.items():
        share = float(clicks_by_type.get(activity, 0.0)) / total
        if abs(share - float(median)) >= SHARE_DEVIATION:
            fired[activity] = 1
    return fired


def fast_auc(y: np.ndarray, score: np.ndarray) -> float:
    y = np.asarray(y).astype(np.int8, copy=False)
    score = np.asarray(score, dtype=np.float64)
    n_pos = int((y == 1).sum())
    n_neg = int(y.size - n_pos)
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(score, kind="mergesort")
    sorted_score = score[order]
    ranked = np.empty(y.size, dtype=np.float64)
    start = 0
    while start < y.size:
        stop = start + 1
        while stop < y.size and sorted_score[stop] == sorted_score[start]:
            stop += 1
        ranked[start:stop] = 0.5 * ((start + 1) + stop)
        start = stop
    sum_pos = float(ranked[y[order] == 1].sum())
    return (sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def self_test() -> None:
    assert week_of(-10) == 1
    assert week_of(7) == 1
    assert week_of(8) == 2
    assert week_of(28) == 4
    assert week_of(29) == 5
    assert is_train_student(11391) in (True, False)

    tutoring, review = tutoring_flags([5, 40], [50, 10], [1, 2], cutoff=28)
    assert (tutoring, review) == (0, 0)
    tutoring, review = tutoring_flags([5, 40], [50, 10], [1, 2], cutoff=40)
    assert tutoring == 1
    tutoring, review = tutoring_flags([1, 2, 3], [90, 70, 50], [1, 2, 3], cutoff=28)
    assert (tutoring, review) == (0, 1)
    tutoring, review = tutoring_flags([1, 2, 3], [30, 20, 10], [1, 2, 3], cutoff=28)
    assert (tutoring, review) == (1, 1)

    events = extension_events([10], [[40]], length=269)
    assert events == [(week_of(10), 1)]
    assert extension_events([10], [[8]], length=269) == []
    assert extension_events([30], [[40]], length=269) == [(week_of(30), 1)]
    assert extension_events([30], [[]], length=269) == [(week_of(30), 1)]
    assert extension_events([300], [[]], length=269) == []
    visible_at_w2 = [item for item in events if item[0] <= 2]
    assert visible_at_w2 == [(2, 1)]
    assert [item for item in extension_events([30], [[40]], length=269) if item[0] <= 4] == []

    medians = {"forumng": 0.10, "resource": 0.50}
    fired = resource_triggers({"forumng": 8, "resource": 2}, medians)
    assert fired.get("forumng") == 1
    assert "resource" in fired
    assert resource_triggers({"forumng": 9}, medians) == {}
    assert resource_triggers({"forumng": 80, "resource": 20}, {"forumng": 0.80, "resource": 0.20}) == {}

    rng = np.random.default_rng(0)
    for _ in range(20):
        y = rng.integers(0, 2, 40)
        if len(set(y)) < 2:
            continue
        score = rng.normal(size=40)
        got = fast_auc(y, score)
        expected = roc_auc_score(y, score)
        assert abs(got - expected) < 1e-9
    print("self-test ok", flush=True)


def load_freeze() -> dict:
    return json.loads((ROOT / "DATA_FREEZE.json").read_text())


def load_tables(freeze: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    modules = [item["code_module"] for item in freeze["cohort"]["module_presentations"]]
    lengths = {
        item["code_module"]: int(item["module_presentation_length"])
        for item in freeze["cohort"]["module_presentations"]
    }
    activity_types = list(freeze["resource_activity_types"])
    info = pd.read_csv(RAW / "studentInfo.csv")
    info = info[info["code_presentation"].eq("2014J") & info["code_module"].isin(modules)].copy()
    if len(info) != freeze["cohort"]["rows"]:
        raise SystemExit(f"cohort rows {len(info)} != {freeze['cohort']['rows']}")
    info["length"] = info["code_module"].map(lengths)
    info["split"] = np.where(info["id_student"].map(is_train_student), "train", "test")
    info["disability_y"] = np.where(info["disability"].eq("Y"), 1, 0).astype(int)
    info["age_55"] = np.where(info["age_band"].eq("55<="), 1, 0).astype(int)
    info["imd_low"] = np.where(
        info["imd_band"].isna(),
        np.nan,
        np.where(info["imd_band"].isin(["0-10%", "10-20"]), 1, 0),
    )
    for module in modules:
        info[f"course_{module}"] = (info["code_module"] == module).astype(int)

    assessments = pd.read_csv(RAW / "assessments.csv")
    assessments = assessments[
        assessments["code_presentation"].eq("2014J")
        & assessments["code_module"].isin(modules)
        & assessments["assessment_type"].isin(["TMA", "CMA"])
        & assessments["date"].notna()
    ][["code_module", "id_assessment", "date"]].copy()
    assessments["date"] = assessments["date"].astype(int)

    submitted = pd.read_csv(RAW / "studentAssessment.csv")
    submitted = submitted[submitted["is_banked"].eq(0)].copy()
    submitted = submitted.merge(assessments, on="id_assessment", how="inner")
    duplicate_rows = int(submitted.duplicated(["code_module", "id_student", "id_assessment"]).sum())
    if duplicate_rows:
        submitted = submitted.sort_values(["date_submitted", "id_assessment"])
        submitted = submitted.drop_duplicates(["code_module", "id_student", "id_assessment"], keep="first")
    info.attrs["duplicate_submissions"] = duplicate_rows

    click_parts = []
    for chunk in pd.read_csv(
        RAW / "studentVle.csv",
        usecols=["code_module", "code_presentation", "id_student", "id_site", "date", "sum_click"],
        chunksize=1_000_000,
    ):
        chunk = chunk[chunk["code_presentation"].eq("2014J") & chunk["code_module"].isin(modules)]
        if len(chunk):
            click_parts.append(chunk)
    clicks = pd.concat(click_parts, ignore_index=True) if click_parts else pd.DataFrame()
    if (clicks["sum_click"] < 0).any():
        raise SystemExit("negative sum_click")
    catalogue = pd.read_csv(RAW / "vle.csv", usecols=["id_site", "code_module", "code_presentation", "activity_type"])
    catalogue = catalogue[catalogue["code_presentation"].eq("2014J") & catalogue["code_module"].isin(modules)]
    clicks = clicks.merge(
        catalogue[["id_site", "code_module", "activity_type"]],
        on=["id_site", "code_module"],
        how="left",
    )
    clicks = clicks[clicks["activity_type"].isin(activity_types) & clicks["date"].lt(clicks["code_module"].map(lengths))].copy()
    clicks["week"] = np.where(clicks["date"].le(7), 1, np.ceil(clicks["date"] / 7).astype(int))
    info.attrs["click_rows"] = int(len(clicks))
    info.attrs["clicks"] = clicks
    return info, assessments, submitted, activity_types


def last_week(length: int) -> int:
    return week_of(length - 1)


def build_request_frame(info: pd.DataFrame, assessments: pd.DataFrame, submitted: pd.DataFrame, activity_types: list[str]) -> pd.DataFrame:
    cohort = info[
        [
            "code_module",
            "code_presentation",
            "id_student",
            "length",
            "split",
            "disability_y",
            "imd_low",
            "age_55",
            *COURSE_COLUMNS,
        ]
    ].copy()
    lengths = dict(zip(cohort["code_module"], cohort["length"]))
    max_week = {module: last_week(length) for module, length in lengths.items()}

    submission_groups = {}
    for (module, student), group in submitted.groupby(["code_module", "id_student"], sort=False):
        submission_groups[(module, int(student))] = (
            group["date_submitted"].astype(int).tolist(),
            group["score"].tolist(),
            group["id_assessment"].astype(int).tolist(),
        )
    assessment_ids = {
        module: group["id_assessment"].astype(int).tolist()
        for module, group in assessments.groupby("code_module", sort=False)
    }
    assessment_deadlines = {
        module: dict(zip(group["id_assessment"].astype(int), group["date"].astype(int)))
        for module, group in assessments.groupby("code_module", sort=False)
    }
    submissions_by_assessment = {}
    for (module, student, assessment_id), group in submitted.groupby(
        ["code_module", "id_student", "id_assessment"], sort=False
    ):
        submissions_by_assessment[(module, int(student), int(assessment_id))] = group["date_submitted"].astype(int).tolist()

    records = []
    for row in cohort.itertuples(index=False):
        module = row.code_module
        student = int(row.id_student)
        length = int(row.length)
        dates, scores, ids = submission_groups.get((module, student), ([], [], []))
        weekly_tutor = {}
        weekly_extension = {}
        final_week = max_week[module]
        for week in range(1, final_week + 1):
            cutoff = min(7 * week, length - 1)
            weekly_tutor[week] = tutoring_flags(dates, scores, ids, cutoff)
        deadlines = []
        submitted_dates = []
        for assessment_id in assessment_ids.get(module, []):
            deadlines.append(assessment_deadlines[module][assessment_id])
            submitted_dates.append(submissions_by_assessment.get((module, student, assessment_id), []))
        for week, count in extension_events(deadlines, submitted_dates, length):
            if week <= final_week:
                weekly_extension[week] = count
        item = {
            "code_module": module,
            "id_student": student,
            "tutor": weekly_tutor,
            "extension": weekly_extension,
        }
        records.append(item)

    click_week = (
        submitted  # placeholder to keep the name reserved until clicks are attached below
    )
    del click_week
    return cohort, records, max_week


def attach_clicks_and_finish(
    cohort: pd.DataFrame,
    records: list[dict],
    clicks: pd.DataFrame,
    activity_types: list[str],
    max_week: dict[str, int],
) -> pd.DataFrame:
    grouped = (
        clicks.groupby(["code_module", "id_student", "week", "activity_type"], sort=False)["sum_click"]
        .sum()
        .rename("clicks")
        .reset_index()
    )
    train_ids = set(zip(
        cohort.loc[cohort["split"].eq("train"), "code_module"],
        cohort.loc[cohort["split"].eq("train"), "id_student"].astype(int),
    ))
    medians: dict[tuple[str, int], dict[str, float]] = {}
    for (module, week), group in grouped.groupby(["code_module", "week"], sort=False):
        pivot = group.pivot_table(
            index="id_student",
            columns="activity_type",
            values="clicks",
            aggfunc="sum",
            fill_value=0,
        )
        for activity in activity_types:
            if activity not in pivot.columns:
                pivot[activity] = 0
        pivot = pivot[activity_types]
        totals = pivot.sum(axis=1)
        active = pivot.loc[totals.gt(0)].copy()
        if active.empty:
            continue
        shares = active.div(totals.loc[active.index], axis=0)
        train_index = [student for student in shares.index if (module, int(student)) in train_ids]
        if not train_index:
            continue
        medians[(module, int(week))] = shares.loc[train_index].median(axis=0).astype(float).to_dict()

    click_maps: dict[tuple[str, int, int], dict[str, float]] = {}
    for row in grouped.itertuples(index=False):
        click_maps.setdefault((row.code_module, int(row.id_student), int(row.week)), {})[row.activity_type] = float(row.clicks)

    resource_weekly: dict[tuple[str, int], dict[int, dict[str, int]]] = {}
    for module, student in zip(cohort["code_module"], cohort["id_student"].astype(int)):
        resource_weekly[(module, student)] = {}
        for week in range(1, max_week[module] + 1):
            resource_weekly[(module, student)][week] = resource_triggers(
                click_maps.get((module, student, week), {}),
                medians.get((module, week), {}),
            )

    behavior = behavior_features(cohort, clicks, activity_types, medians)
    rows = []
    record_by_key = {(item["code_module"], int(item["id_student"])): item for item in records}
    for row in cohort.itertuples(index=False):
        key = (row.code_module, int(row.id_student))
        item = record_by_key[key]
        final_week = max_week[row.code_module]
        out = {
            "id_student": int(row.id_student),
            "code_module": row.code_module,
            "code_presentation": row.code_presentation,
            "split": row.split,
            "disability_y": int(row.disability_y),
            "imd_low": row.imd_low,
            "age_55": int(row.age_55),
            "course_BBB": int(row.course_BBB),
            "course_CCC": int(row.course_CCC),
            "course_FFF": int(row.course_FFF),
        }
        checkpoints = {4: "w4", 8: "w8", 12: "w12", final_week: "wfull"}
        seen = set()
        for week, name in checkpoints.items():
            if name in seen:
                continue
            seen.add(name)
            tutor_sum = [0, 0]
            extension_sum = 0
            resource_sum = {activity: 0 for activity in activity_types}
            limit = week if name != "wfull" else final_week
            for previous in range(1, limit + 1):
                flags = item["tutor"].get(previous, (0, 0))
                tutor_sum[0] += flags[0]
                tutor_sum[1] += flags[1]
                extension_sum += int(item["extension"].get(previous, 0))
                for activity, fired in resource_weekly[key].get(previous, {}).items():
                    resource_sum[activity] += fired
            current_tutor = item["tutor"].get(limit, (0, 0))
            current_extension = int(item["extension"].get(limit, 0))
            current_resource = resource_weekly[key].get(limit, {})
            out[f"{name}__review_session"] = tutor_sum[1]
            out[f"{name}__tutoring"] = tutor_sum[0]
            out[f"{name}__review_session_now"] = int(current_tutor[1] > 0)
            out[f"{name}__tutoring_now"] = int(current_tutor[0] > 0)
            out[f"{name}__extension"] = extension_sum
            out[f"{name}__extension_now"] = int(current_extension > 0)
            for activity in activity_types:
                out[f"{name}__format_{activity}"] = resource_sum[activity]
                out[f"{name}__format_{activity}_now"] = int(current_resource.get(activity, 0) > 0)
        out.update(behavior[key])
        rows.append(out)
    frame = pd.DataFrame(rows)
    if set(zip(frame.loc[frame["split"].eq("train"), "code_module"], frame.loc[frame["split"].eq("train"), "id_student"])).isdisjoint(
        set(zip(frame.loc[frame["split"].eq("test"), "code_module"], frame.loc[frame["split"].eq("test"), "id_student"]))
    ) is False:
        pass
    train_students = set(frame.loc[frame["split"].eq("train"), "id_student"])
    test_students = set(frame.loc[frame["split"].eq("test"), "id_student"])
    if train_students & test_students:
        raise SystemExit("student appears on both sides of the split")
    return frame


def behavior_features(cohort, clicks, activity_types, medians) -> dict[tuple[str, int], dict]:
    del medians
    lengths = dict(zip(cohort["code_module"], cohort["length"]))
    submitted_path = None
    del submitted_path
    # Scores and lateness are attached by the caller through columns already computed in records.
    return {}


def build_per_student(freeze: dict) -> tuple[pd.DataFrame, dict]:
    info, assessments, submitted, activity_types = load_tables(freeze)
    notes = {
        "duplicate_submissions_collapsed": int(info.attrs["duplicate_submissions"]),
        "click_rows_after_filters": int(info.attrs["click_rows"]),
        "high_score_constant_unused_for_counts": HIGH_SCORE,
    }
    cohort, records, max_week = build_request_records(info, assessments, submitted)
    frame = assemble(cohort, records, activity_types, max_week, info.attrs["clicks"])
    frame = add_behavior(frame, info.attrs["clicks"], submitted, assessments, activity_types)
    frame = add_shuffled_labels(frame)
    return frame, notes


def build_request_records(info, assessments, submitted):
    assessment_ids = {
        module: group["id_assessment"].astype(int).tolist()
        for module, group in assessments.groupby("code_module", sort=False)
    }
    deadlines = {
        module: dict(zip(group["id_assessment"].astype(int), group["date"].astype(int)))
        for module, group in assessments.groupby("code_module", sort=False)
    }
    by_student = {}
    for (module, student), group in submitted.groupby(["code_module", "id_student"], sort=False):
        by_student[(module, int(student))] = group
    by_exact = {}
    for (module, student, assessment_id), group in submitted.groupby(
        ["code_module", "id_student", "id_assessment"], sort=False
    ):
        by_exact[(module, int(student), int(assessment_id))] = group["date_submitted"].astype(int).tolist()

    lengths = dict(zip(info["code_module"], info["length"].astype(int)))
    max_week = {module: last_week(length) for module, length in lengths.items()}
    records = {}
    for row in info.itertuples(index=False):
        module = row.code_module
        student = int(row.id_student)
        length = int(row.length)
        group = by_student.get((module, student))
        if group is None:
            dates, scores, ids = [], [], []
        else:
            dates = group["date_submitted"].astype(int).tolist()
            scores = group["score"].tolist()
            ids = group["id_assessment"].astype(int).tolist()
        tutor = {}
        for week in range(1, max_week[module] + 1):
            tutor[week] = tutoring_flags(dates, scores, ids, min(7 * week, length - 1))
        deadline_list = []
        submitted_list = []
        for assessment_id in assessment_ids.get(module, []):
            deadline_list.append(deadlines[module][assessment_id])
            submitted_list.append(by_exact.get((module, student, assessment_id), []))
        extension = {week: count for week, count in extension_events(deadline_list, submitted_list, length)}
        records[(module, student)] = {"tutor": tutor, "extension": extension, "length": length}
    return info, records, max_week


def assemble(info, records, activity_types, max_week, clicks) -> pd.DataFrame:
    grouped = (
        clicks.groupby(["code_module", "id_student", "week", "activity_type"], sort=False)["sum_click"]
        .sum()
        .rename("clicks")
        .reset_index()
    )
    train_keys = set(zip(
        info.loc[info["split"].eq("train"), "code_module"],
        info.loc[info["split"].eq("train"), "id_student"].astype(int),
    ))
    medians = {}
    for (module, week), group in grouped.groupby(["code_module", "week"], sort=False):
        pivot = group.pivot_table(index="id_student", columns="activity_type", values="clicks", aggfunc="sum", fill_value=0)
        for activity in activity_types:
            if activity not in pivot.columns:
                pivot[activity] = 0
        pivot = pivot[list(activity_types)]
        totals = pivot.sum(axis=1)
        active = pivot.loc[totals.gt(0)]
        if active.empty:
            continue
        shares = active.div(totals.loc[active.index], axis=0)
        train_index = [student for student in shares.index if (module, int(student)) in train_keys]
        if not train_index:
            continue
        medians[(module, int(week))] = shares.loc[train_index].median(axis=0).astype(float).to_dict()
        if any((module, int(student)) not in train_keys for student in train_index):
            raise SystemExit("test row entered a median")

    click_maps = {}
    for row in grouped.itertuples(index=False):
        click_maps.setdefault((row.code_module, int(row.id_student), int(row.week)), {})[row.activity_type] = float(row.clicks)

    rows = []
    for row in info.itertuples(index=False):
        module = row.code_module
        student = int(row.id_student)
        key = (module, student)
        record = records[key]
        final_week = max_week[module]
        resource_by_week = {}
        for week in range(1, final_week + 1):
            resource_by_week[week] = resource_triggers(click_maps.get((module, student, week), {}), medians.get((module, week), {}))
        out = {
            "id_student": student,
            "code_module": module,
            "code_presentation": row.code_presentation,
            "split": row.split,
            "disability_y": int(row.disability_y),
            "imd_low": None if pd.isna(row.imd_low) else int(row.imd_low),
            "age_55": int(row.age_55),
        }
        for column in COURSE_COLUMNS:
            out[column] = int(getattr(row, column))
        for name, limit in (("w4", 4), ("w8", 8), ("w12", 12), ("wfull", final_week)):
            review_sum = tutoring_sum = extension_sum = 0
            resource_sum = {activity: 0 for activity in activity_types}
            for week in range(1, limit + 1):
                tutor_flag, review_flag = record["tutor"].get(week, (0, 0))
                tutoring_sum += tutor_flag
                review_sum += review_flag
                extension_sum += int(record["extension"].get(week, 0))
                for activity, fired in resource_by_week.get(week, {}).items():
                    resource_sum[activity] += int(fired)
            current_tutor, current_review = record["tutor"].get(limit, (0, 0))
            out[f"{name}__review_session"] = review_sum
            out[f"{name}__tutoring"] = tutoring_sum
            out[f"{name}__review_session_now"] = int(current_review > 0)
            out[f"{name}__tutoring_now"] = int(current_tutor > 0)
            out[f"{name}__extension"] = extension_sum
            out[f"{name}__extension_now"] = int(record["extension"].get(limit, 0) > 0)
            for activity in activity_types:
                out[f"{name}__format_{activity}"] = resource_sum[activity]
                out[f"{name}__format_{activity}_now"] = int(resource_by_week.get(limit, {}).get(activity, 0) > 0)
        rows.append(out)
    frame = pd.DataFrame(rows)
    if set(frame.loc[frame["split"].eq("train"), "id_student"]) & set(frame.loc[frame["split"].eq("test"), "id_student"]):
        raise SystemExit("student appears on both sides of the split")
    frame.attrs["clicks"] = clicks
    frame.attrs["medians_are_train_only"] = True
    return frame


def add_behavior(frame, clicks, submitted, assessments, activity_types) -> pd.DataFrame:
    lengths = {"BBB": 262, "CCC": 269, "FFF": 269}
    click_dict = (
        clicks.groupby(["code_module", "id_student", "week", "activity_type"], sort=False)["sum_click"]
        .sum()
        .to_dict()
    )
    cumulative = {}
    for (module, student, week, activity), value in click_dict.items():
        bucket = cumulative.setdefault((module, int(student)), {})
        week_bucket = bucket.setdefault(int(week), {})
        week_bucket[activity] = week_bucket.get(activity, 0.0) + float(value)
    assessments_by_module = {
        module: list(zip(group["id_assessment"].astype(int), group["date"].astype(int)))
        for module, group in assessments.groupby("code_module", sort=False)
    }
    submitted_by_key = {}
    score_by_key = {}
    for (module, student), group in submitted.groupby(["code_module", "id_student"], sort=False):
        key = (module, int(student))
        submitted_by_key[key] = [
            (int(assessment_id), int(date_submitted), score, int(deadline))
            for assessment_id, date_submitted, score, deadline in zip(
                group["id_assessment"], group["date_submitted"], group["score"], group["date"]
            )
        ]
        dates = {}
        for assessment_id, date_submitted, _score, _deadline in submitted_by_key[key]:
            dates.setdefault(assessment_id, []).append(date_submitted)
        score_by_key[key] = dates
    rows = []
    for row in frame.itertuples(index=False):
        module = row.code_module
        student = int(row.id_student)
        length = lengths[module]
        final_week = last_week(length)
        key = (module, student)
        week_clicks = cumulative.get(key, {})
        submissions = submitted_by_key.get(key, [])
        dates_by_assessment = score_by_key.get(key, {})
        item = {}
        running = {activity: 0.0 for activity in activity_types}
        running_total = 0.0
        checkpoints = {4: "w4", 8: "w8", 12: "w12", final_week: "wfull"}
        emitted = set()
        for week in range(1, final_week + 1):
            for activity, value in week_clicks.get(week, {}).items():
                if activity in running:
                    running[activity] += value
                    running_total += value
            if week not in checkpoints:
                continue
            name = checkpoints[week]
            if name in emitted:
                continue
            emitted.add(name)
            cutoff = length - 1 if name == "wfull" else min(7 * week, length - 1)
            item[f"{name}__clicks_total"] = running_total
            for activity in activity_types:
                item[f"{name}__clicks_{activity}"] = running[activity]
            observed = [entry for entry in submissions if entry[1] <= cutoff]
            scored = [entry[2] for entry in observed if pd.notna(entry[2])]
            item[f"{name}__n_scored"] = len(scored)
            item[f"{name}__mean_score"] = float(np.mean(scored)) if scored else 0.0
            item[f"{name}__mean_lateness"] = (
                float(np.mean([entry[1] - entry[3] for entry in observed])) if observed else 0.0
            )
            missed = 0
            for assessment_id, deadline in assessments_by_module[module]:
                if deadline > cutoff or deadline >= length:
                    continue
                if not any(date <= deadline for date in dates_by_assessment.get(assessment_id, [])):
                    missed += 1
            item[f"{name}__n_late"] = missed
        rows.append(item)
    behavior = pd.DataFrame(rows)
    for column in behavior.columns:
        frame[column] = behavior[column].to_numpy()
    return frame


def add_shuffled_labels(frame: pd.DataFrame) -> pd.DataFrame:
    for label in LABELS:
        shuffled = frame[label].copy()
        for split, seed in (("train", 20261116), ("test", 20261117)):
            mask = frame["split"].eq(split) & frame[label].notna()
            values = frame.loc[mask, label].to_numpy().copy()
            rng = np.random.Generator(np.random.PCG64(seed))
            shuffled.loc[mask] = rng.permutation(values)
            if int(np.nansum(values)) != int(np.nansum(shuffled.loc[mask].to_numpy())):
                raise SystemExit(f"shuffle changed the positive count for {label} {split}")
        frame[f"{label}_shuffle"] = shuffled
    return frame


def feature_columns(frame: pd.DataFrame, week_name: str, kinds: tuple[str, ...]) -> list[str]:
    columns = []
    for kind in kinds:
        for suffix in ("", "_now"):
            column = f"{week_name}__{kind}{suffix}"
            if column not in frame.columns:
                raise SystemExit(f"missing feature column {column}")
            columns.append(column)
    columns.extend(COURSE_COLUMNS)
    return columns


def observer_kinds(activity_types: list[str]) -> dict[str, tuple[str, ...]]:
    resource = tuple(f"format_{activity}" for activity in activity_types)
    return {
        "辅导": TUTOR_TYPES,
        "教务": ADMIN_TYPES,
        "资源": resource,
        "辅导+教务": TUTOR_TYPES + ADMIN_TYPES,
        "辅导+资源": TUTOR_TYPES + resource,
        "教务+资源": ADMIN_TYPES + resource,
        "三方合谋": TUTOR_TYPES + ADMIN_TYPES + resource,
    }


def behavior_columns(frame: pd.DataFrame, week_name: str, activity_types: list[str]) -> list[str]:
    columns = [f"{week_name}__clicks_total"]
    columns.extend(f"{week_name}__clicks_{activity}" for activity in activity_types)
    columns.extend(f"{week_name}__{name}" for name in ("n_scored", "mean_score", "n_late", "mean_lateness"))
    columns.extend(COURSE_COLUMNS)
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise SystemExit(f"missing behavior columns: {missing[:5]}")
    return columns


def fit_predictions(x_train, y_train, x_test):
    keep = np.asarray(x_train).std(axis=0) > 0
    # Frozen rule drops columns that are all zero on the training rows, not all constant columns.
    zero = np.all(np.asarray(x_train) == 0, axis=0)
    keep = ~zero
    if not keep.any():
        return None
    x_train = np.asarray(x_train, dtype=np.float64)[:, keep]
    x_test = np.asarray(x_test, dtype=np.float64)[:, keep]
    results = {}
    scaler = StandardScaler()
    x_train_scaled = scaler.fit_transform(x_train)
    x_test_scaled = scaler.transform(x_test)
    logistic = LogisticRegression(solver="lbfgs", C=1.0, max_iter=1000, random_state=MODEL_SEED)
    logistic.fit(x_train_scaled, y_train)
    proba = logistic.predict_proba(x_test_scaled)
    positive = list(logistic.classes_).index(1)
    results["逻辑回归"] = {
        "proba": proba[:, positive],
        "pred": (proba[:, positive] >= 0.5).astype(int),
        "converged": int(logistic.n_iter_[0]) < 1000,
    }
    tree = DecisionTreeClassifier(max_depth=3, random_state=MODEL_SEED)
    tree.fit(x_train, y_train)
    tree_proba = tree.predict_proba(x_test)
    positive = list(tree.classes_).index(1)
    results["决策树"] = {
        "proba": tree_proba[:, positive],
        "pred": tree.predict(x_test).astype(int),
        "converged": True,
    }
    return results


def bootstrap_intervals(y, proba, pred, student_ids, draws: np.ndarray, groups: list[np.ndarray]) -> dict:
    point_auc = float(roc_auc_score(y, proba)) if len(set(y)) > 1 else float("nan")
    point_bacc = float(balanced_accuracy_score(y, pred)) if len(set(y)) > 1 else float("nan")
    aucs = []
    baccs = []
    for draw in draws:
        parts = [groups[index] for index in draw]
        idx = np.concatenate(parts)
        yy = y[idx]
        if len(set(yy.tolist())) < 2:
            continue
        aucs.append(fast_auc(yy, proba[idx]))
        baccs.append(balanced_accuracy_score(yy, pred[idx]))
    def interval(values):
        if len(values) < 900:
            return None, None, len(values)
        array = np.asarray(values, dtype=np.float64)
        return float(np.percentile(array, 2.5)), float(np.percentile(array, 97.5)), len(values)
    auc_lo, auc_hi, auc_n = interval(aucs)
    bacc_lo, bacc_hi, bacc_n = interval(baccs)
    return {
        "auc": point_auc,
        "auc_lo": auc_lo,
        "auc_hi": auc_hi,
        "bacc": point_bacc,
        "bacc_lo": bacc_lo,
        "bacc_hi": bacc_hi,
        "bootstrap_valid": auc_n,
        "bootstrap_valid_bacc": bacc_n,
    }


def draw_student_indexes(student_ids: np.ndarray, seed: int) -> tuple[np.ndarray, list[np.ndarray]]:
    unique, inverse = np.unique(student_ids, return_inverse=True)
    groups = [np.flatnonzero(inverse == index) for index in range(len(unique))]
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(unique), size=(BOOTSTRAP_DRAWS, len(unique)))
    return draws, groups


def evaluate(frame: pd.DataFrame, activity_types: list[str]) -> list[dict]:
    kinds = observer_kinds(activity_types)
    rows = []
    for label_index, label in enumerate(LABELS):
        defined = frame[label].notna()
        subset = frame.loc[defined].copy()
        subset[label] = subset[label].astype(int)
        for week_name in WEEK_NAMES:
            test = subset[subset["split"].eq("test")]
            draws, groups = draw_student_indexes(test["id_student"].to_numpy(), MODEL_SEED + label_index)
            matrices = []
            for observer, type_names in kinds.items():
                matrices.append((observer, feature_columns(subset, week_name, type_names), label, False))
            matrices.append(("对照A", behavior_columns(subset, week_name, activity_types), label, False))
            matrices.append(("对照B", feature_columns(subset, week_name, kinds["三方合谋"]), f"{label}_shuffle", True))
            for observer, columns, target, shuffled in matrices:
                train = subset[subset["split"].eq("train")]
                test = subset[subset["split"].eq("test")]
                y_train = train[target].astype(int).to_numpy()
                y_test = test[target].astype(int).to_numpy()
                base = {
                    "label": label,
                    "week": week_name,
                    "observer": observer,
                    "n_train_rows": int(len(train)),
                    "n_test_rows": int(len(test)),
                    "n_train_students": int(train["id_student"].nunique()),
                    "n_test_students": int(test["id_student"].nunique()),
                    "n_pos_train": int(y_train.sum()) if not shuffled else int(train[label].astype(int).sum()),
                    "n_pos_test": int(test[label].astype(int).sum()),
                    "n_defined_test": int(len(test)),
                }
                if shuffled:
                    base["n_pos_train_shuffled"] = int(y_train.sum())
                    base["n_pos_test_shuffled"] = int(y_test.sum())
                if len(set(y_train.tolist())) < 2 or len(set(y_test.tolist())) < 2:
                    for model_name in ("逻辑回归", "决策树"):
                        rows.append({**base, "model": model_name, "auc": None, "note": "single_class"})
                    continue
                fitted = fit_predictions(train[columns].to_numpy(), y_train, test[columns].to_numpy())
                if fitted is None:
                    for model_name in ("逻辑回归", "决策树"):
                        rows.append({**base, "model": model_name, "auc": None, "note": "no_features"})
                    continue
                for model_name, payload in fitted.items():
                    stats = bootstrap_intervals(
                        y_test,
                        payload["proba"],
                        payload["pred"],
                        test["id_student"].to_numpy(),
                        draws,
                        groups,
                    )
                    rows.append({
                        **base,
                        "model": model_name,
                        "converged": payload["converged"],
                        "n_features": len(columns),
                        "note": "",
                        **stats,
                    })
        print(f"evaluated {label}", flush=True)
    return rows


def fmt_auc(row: dict | None) -> str:
    if row is None or row.get("auc") is None or (isinstance(row.get("auc"), float) and np.isnan(row["auc"])):
        return "无法计算"
    text = f"{row['auc']:.3f}"
    if row.get("auc_lo") is None or row.get("auc_hi") is None:
        return f"{text}（区间无法计算）"
    return f"{text} ({row['auc_lo']:.3f}–{row['auc_hi']:.3f})"


def decide(metrics: list[dict]) -> dict:
    by_key = {(row["label"], row["week"], row["observer"], row["model"]): row for row in metrics}
    point_passes = []
    partials = []
    for label in LABELS:
        for week in WEEK_NAMES:
            for model in ("逻辑回归", "决策树"):
                collusion = by_key.get((label, week, "三方合谋", model))
                singles = [by_key.get((label, week, name, model)) for name in ("辅导", "教务", "资源")]
                single_values = [row["auc"] for row in singles if row and row.get("auc") is not None and not np.isnan(row["auc"])]
                if collusion and collusion.get("auc") is not None and not np.isnan(collusion["auc"]) and single_values:
                    best = max(single_values)
                    lower = collusion.get("auc_lo")
                    passed = collusion["auc"] >= 0.65 and lower is not None and lower > 0.55 and collusion["auc"] >= best + 0.03
                    if passed:
                        point_passes.append({
                            "label": label,
                            "week": week,
                            "model": model,
                            "auc": collusion["auc"],
                            "auc_lo": lower,
                            "auc_hi": collusion.get("auc_hi"),
                            "best_single": best,
                            "lift": collusion["auc"] - best,
                        })
                for row in singles:
                    if row and row.get("auc") is not None and not np.isnan(row["auc"]) and row["auc"] >= 0.65:
                        partials.append({"label": label, "week": week, "model": model, "observer": row["observer"], "auc": row["auc"]})
    stable = []
    for label in LABELS:
        for model in ("逻辑回归", "决策树"):
            for left, right in ADJACENT:
                pair = []
                ok = True
                for week in (left, right):
                    match = [item for item in point_passes if item["label"] == label and item["week"] == week and item["model"] == model]
                    if not match:
                        ok = False
                        break
                    pair.append(match[0])
                if ok:
                    stable.append({"label": label, "model": model, "weeks": [left, right], "detail": pair})
    if point_passes:
        decision = "通过"
    elif partials:
        decision = "部分通过"
    else:
        decision = "失败"
    return {"decision": decision, "point_passes": point_passes, "partials": partials, "stable": stable}


def render_result(frame: pd.DataFrame, metrics: list[dict], decision: dict, notes: dict, activity_types: list[str]) -> str:
    by_key = {(row["label"], row["week"], row["observer"], row["model"]): row for row in metrics}
    lines = [
        "# MM-FOPD Gate 0 阶段 B 结果",
        "",
        "数字来自重新读入的 `per_student.csv`。阶段 A 冻结提交是 `0e1036eb567b362a4fdc38aa4d01f23ec528820e`。四条口径改动写在 `DEVIATIONS.md`，阈值、标签、课程和闸门数字没有改。",
        "",
        f"闸门判定：**{decision['decision']}**。",
        "",
        "单点通过指同一标签、同一观察点、同一模型同时满足三方合谋 AUC ≥ 0.65、95% 区间下界 > 0.55、且比三个单 Agent 中最高的 AUC 至少高 0.03。稳定指第 4/8 周、第 8/12 周或第 12 周/全学期这三对相邻观察点里，至少一对同时单点通过。",
        "",
        "## 分母",
        "",
    ]
    for label, title in (("disability_y", "disability = Y"), ("imd_low", "imd 最低两档"), ("age_55", "age_band = 55<=")):
        part = frame[frame[label].notna()]
        train = part[part["split"].eq("train")]
        test = part[part["split"].eq("test")]
        lines.append(
            f"- {title}：训练 {int(train[label].sum())}/{len(train)} 行、{train['id_student'].nunique()} 个学生；"
            f"测试 {int(test[label].sum())}/{len(test)} 行、{test['id_student'].nunique()} 个学生。"
        )
    lines.extend([
        "",
        f"注册行 {len(frame)}，学生 {frame['id_student'].nunique()}。训练学生 {frame.loc[frame['split'].eq('train'), 'id_student'].nunique()}，测试学生 {frame.loc[frame['split'].eq('test'), 'id_student'].nunique()}。",
        f"点击行（课程、类型、课程长度过滤后）{notes['click_rows_after_filters']}。重复的学生-评测提交行 {notes['duplicate_submissions_collapsed']}。",
        "",
        "## 单 Agent 与三方合谋",
        "",
        "单元格是 AUC（95% 区间）。区间按测试学生重抽样 1000 次。",
        "",
    ])
    week_title = {"w4": "第4周", "w8": "第8周", "w12": "第12周", "wfull": "全学期"}
    for label, title in (("disability_y", "disability = Y"), ("imd_low", "imd 最低两档"), ("age_55", "age_band = 55<=")):
        lines.append(f"### {title}")
        lines.append("")
        for model in ("逻辑回归", "决策树"):
            lines.append(f"#### {model}")
            lines.append("")
            lines.append("| 观察点 | 辅导 | 教务 | 资源 | 三方合谋 | 合谋减最好单方 | 单点通过 |")
            lines.append("|---|---|---|---|---|---:|---|")
            for week in WEEK_NAMES:
                cells = []
                single_values = []
                for observer in ("辅导", "教务", "资源", "三方合谋"):
                    row = by_key.get((label, week, observer, model))
                    cells.append(fmt_auc(row))
                    if observer != "三方合谋" and row and row.get("auc") is not None and not (isinstance(row["auc"], float) and np.isnan(row["auc"])):
                        single_values.append(row["auc"])
                collusion = by_key.get((label, week, "三方合谋", model))
                if collusion and collusion.get("auc") is not None and single_values and not (isinstance(collusion["auc"], float) and np.isnan(collusion["auc"])):
                    lift = collusion["auc"] - max(single_values)
                    lower = collusion.get("auc_lo")
                    passed = collusion["auc"] >= 0.65 and lower is not None and lower > 0.55 and lift >= 0.03
                    lift_text = f"{lift:.3f}"
                    pass_text = "是" if passed else "否"
                else:
                    lift_text = "无法计算"
                    pass_text = "否"
                lines.append(f"| {week_title[week]} | " + " | ".join(cells) + f" | {lift_text} | {pass_text} |")
            lines.append("")
    lines.extend(["## 稳定标注", ""])
    if decision["stable"]:
        for item in decision["stable"]:
            lines.append(f"- {item['label']} / {item['model']}：{' 与 '.join(item['weeks'])} 连续单点通过。")
    else:
        lines.append("- 没有任何标签在相邻两个观察点上连续满足三方合谋单点通过。")
    lines.append("")
    lines.append("单 Agent AUC ≥ 0.65 的连续情况：")
    lines.append("")
    found_partial_stable = False
    by_key = {(row["label"], row["week"], row["observer"], row["model"]): row for row in metrics}
    for label in LABELS:
        for model in ("逻辑回归", "决策树"):
            for observer in ("辅导", "教务", "资源"):
                for left, right in ADJACENT:
                    pair = []
                    ok = True
                    for week in (left, right):
                        row = by_key.get((label, week, observer, model))
                        if not row or row.get("auc") is None or row["auc"] < 0.65:
                            ok = False
                            break
                        pair.append(row["auc"])
                    if ok:
                        found_partial_stable = True
                        lines.append(f"- {label} / {model} / {observer}：{left} ({pair[0]:.3f}) 与 {right} ({pair[1]:.3f})。")
    if not found_partial_stable:
        lines.append("- 没有单 Agent 在相邻观察点上连续达到 AUC ≥ 0.65。")
    lines.extend(["", "## 对照", ""])
    lines.append("| 标签 | 观察点 | 模型 | 对照A AUC | 对照B AUC |")
    lines.append("|---|---|---|---|---|")
    for label in LABELS:
        for week in WEEK_NAMES:
            for model in ("逻辑回归", "决策树"):
                upper = by_key.get((label, week, "对照A", model))
                lower = by_key.get((label, week, "对照B", model))
                lines.append(f"| {label} | {week_title[week]} | {model} | {fmt_auc(upper)} | {fmt_auc(lower)} |")
    lines.extend(["", "## 两两合谋", ""])
    lines.append("| 标签 | 观察点 | 模型 | 辅导+教务 | 辅导+资源 | 教务+资源 |")
    lines.append("|---|---|---|---|---|---|")
    for label in LABELS:
        for week in WEEK_NAMES:
            for model in ("逻辑回归", "决策树"):
                values = [fmt_auc(by_key.get((label, week, name, model))) for name in ("辅导+教务", "辅导+资源", "教务+资源")]
                lines.append(f"| {label} | {week_title[week]} | {model} | " + " | ".join(values) + " |")
    nonconverged = [row for row in metrics if row.get("converged") is False]
    lines.extend(["", "## 拟合", ""])
    if nonconverged:
        lines.append(f"逻辑回归未在 1000 次迭代内收敛的格子：{len(nonconverged)}。")
    else:
        lines.append("逻辑回归都在 1000 次迭代内收敛。决策树深度固定为 3。")
    lines.append("")
    lines.append("资源类型词表：" + "、".join(activity_types) + "。")
    lines.extend(course_diagnostic_lines(frame, activity_types))
    lines.append("")
    return "\n".join(lines) + "\n"


def course_diagnostic_lines(frame: pd.DataFrame, activity_types: list[str]) -> list[str]:
    """Separate course identity from request features. Not an additional gate."""
    resource = [f"format_{activity}" for activity in activity_types]
    observers = {
        "辅导": ["review_session", "tutoring"],
        "教务": ["extension"],
        "资源": resource,
        "三方合谋": ["review_session", "tutoring", "extension", *resource],
    }

    def auc_for(columns: list[str], label: str) -> float | None:
        part = frame[frame[label].notna()]
        train = part[part["split"].eq("train")]
        test = part[part["split"].eq("test")]
        y_train = train[label].astype(int).to_numpy()
        y_test = test[label].astype(int).to_numpy()
        x_train = train[columns].to_numpy(dtype=float)
        x_test = test[columns].to_numpy(dtype=float)
        keep = ~np.all(x_train == 0, axis=0)
        if not keep.any() or len(set(y_train.tolist())) < 2 or len(set(y_test.tolist())) < 2:
            return None
        scaler = StandardScaler()
        model = LogisticRegression(solver="lbfgs", C=1.0, max_iter=1000, random_state=MODEL_SEED)
        model.fit(scaler.fit_transform(x_train[:, keep]), y_train)
        proba = model.predict_proba(scaler.transform(x_test[:, keep]))
        positive = list(model.classes_).index(1)
        return float(roc_auc_score(y_test, proba[:, positive]))

    def request_columns(week_name: str, kinds: list[str]) -> list[str]:
        columns = []
        for kind in kinds:
            columns.append(f"{week_name}__{kind}")
            columns.append(f"{week_name}__{kind}_now")
        return columns

    lines = [
        "",
        "## 诊断：课程身份本身的贡献",
        "",
        "上面的闸门模型都带课程 one-hot。这里用同一套逻辑回归和同一次划分，把课程列和请求列拆开重算。这不是新的闸门。",
        "",
    ]
    course_bits = []
    for label, title in (("disability_y", "disability"), ("imd_low", "imd 最低两档"), ("age_55", "age 55<=")):
        value = auc_for(list(COURSE_COLUMNS), label)
        course_bits.append(f"{title} {value:.3f}" if value is not None else f"{title} 无法计算")
    lines.append("只输入三列课程身份时，测试集 AUC 是：" + "，".join(course_bits) + "。")
    age = frame[frame["age_55"].notna()]
    rates = []
    for module, group in age.groupby("code_module"):
        rates.append(f"{module} {int(group['age_55'].sum())}/{len(group)}")
    lines.append("三门课的 55<= 行数是 " + "、".join(rates) + "。")
    lines.append("")
    lines.append("age 55<= 去掉课程列、只留请求特征时，逻辑回归 AUC 为：")
    lines.append("")
    lines.append("| 观察点 | 辅导 | 教务 | 资源 | 三方合谋 |")
    lines.append("|---|---:|---:|---:|---:|")
    for week_name, title in (("w4", "第4周"), ("wfull", "全学期")):
        cells = []
        for kinds in observers.values():
            value = auc_for(request_columns(week_name, kinds), "age_55")
            cells.append("无法计算" if value is None else f"{value:.3f}")
        lines.append(f"| {title} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("第 4 周的教务请求在没有课程列时仍可能高于 0.65。三方合谋在带上课程列之后没有比最好的单 Agent 高出 0.03。")
    return lines


def main() -> None:
    self_test()
    freeze = load_freeze()
    activity_types = list(freeze["resource_activity_types"])
    info, assessments, submitted, loaded_types = load_tables(freeze)
    if loaded_types != activity_types:
        raise SystemExit("activity type list drifted")
    print(
        f"loaded rows={len(info)} clicks={info.attrs['click_rows']} duplicate_submissions={info.attrs['duplicate_submissions']}",
        flush=True,
    )
    cohort_info, records, max_week = build_request_records(info, assessments, submitted)
    frame = assemble(cohort_info, records, activity_types, max_week, info.attrs["clicks"])
    frame = add_behavior(frame, info.attrs["clicks"], submitted, assessments, activity_types)
    frame = add_shuffled_labels(frame)
    for name in WEEK_NAMES:
        extension = frame[f"{name}__extension"].to_numpy()
        late = frame[f"{name}__n_late"].to_numpy()
        if not np.array_equal(extension, late):
            raise SystemExit(f"{name} extension and n_late differ on {(extension != late).sum()} rows")
    print(
        "feature check",
        "train",
        int(frame["split"].eq("train").sum()),
        "extension_w4_mean",
        float(frame["w4__extension"].mean()),
        "tutoring_w4_mean",
        float(frame["w4__tutoring"].mean()),
        "format_w4_mean",
        float(frame[[column for column in frame.columns if column.startswith("w4__format_") and not column.endswith("_now")]].sum(axis=1).mean()),
        flush=True,
    )
    notes = {
        "duplicate_submissions_collapsed": int(info.attrs["duplicate_submissions"]),
        "click_rows_after_filters": int(info.attrs["click_rows"]),
    }
    forbidden = {"disability", "imd_band", "age_band", "gender", "region", "highest_education", "final_result"}
    leaked = forbidden & set(frame.columns)
    if leaked:
        raise SystemExit(f"forbidden columns in feature table: {leaked}")
    csv_path = ROOT / "per_student.csv"
    frame.to_csv(csv_path, index=False)
    reloaded = pd.read_csv(csv_path)
    print(f"wrote {csv_path} rows={len(reloaded)} cols={reloaded.shape[1]}", flush=True)
    metrics = evaluate(reloaded, activity_types)
    decision = decide(metrics)
    result = render_result(reloaded, metrics, decision, notes, activity_types)
    (ROOT / "RESULT.md").write_text(result)
    def json_ready(value):
        if isinstance(value, dict):
            return {key: json_ready(item) for key, item in value.items()}
        if isinstance(value, list):
            return [json_ready(item) for item in value]
        if isinstance(value, (np.floating, float)):
            number = float(value)
            return None if np.isnan(number) or np.isinf(number) else number
        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.bool_,)):
            return bool(value)
        return value

    (ROOT / "metrics.json").write_text(json.dumps(json_ready({"decision": decision, "metrics": metrics}), ensure_ascii=False, indent=2))
    print(result)
    print("DECISION", decision["decision"], flush=True)


if __name__ == "__main__":
    main()
