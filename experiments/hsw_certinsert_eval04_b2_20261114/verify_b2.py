"""Recompute aggregate outcomes from the published per-item evidence."""
import csv
import json
from collections import Counter

from pathlib import Path

HERE = Path(__file__).resolve().parent


def rows(name):
    with (HERE / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def check(count, k, n):
    assert count == {"k": k, "n": n}, (count, k, n)


def main():
    doc = rows("calibration_by_doc.csv")
    items = rows("per_item.csv")
    report = json.loads((HERE / "figure_counts.json").read_text(encoding="utf-8"))
    assert len(doc) == 893 * 3 * 2
    for gamma, methods in report["zero_hypothesis"].items():
        for mode, result in methods.items():
            data = [row for row in doc if row["gamma"] == gamma and row["mode"] == mode]
            assert len({row["id"] for row in data}) == len(data) == 893
            n = sum(int(row["keys"]) for row in data)
            check(result["not_testable"], sum(int(row["not_testable"]) for row in data), n)
            for alpha, column in [("0.001","fp_001"),("0.01","fp_01"),("0.05","fp_05")]:
                check(result["false_positive"][alpha],sum(int(row[column]) for row in data),n)
            check(result["marked_frame_fraction"],
                  sum(int(row["marked_frame_units"]) for row in data),
                  sum(int(row["frame_units_times_keys"]) for row in data))
    for label, cfg in report["configs"].items():
        gamma, maximum = label.split("/")
        data = [row for row in items if row["gamma"] == gamma and row["m_max"] == maximum]
        embedding = [row for row in data if row["kind"]=="embedding"]
        success = [row for row in embedding if row["status"]=="WATERMARKED"]
        assert len({row["id"] for row in embedding}) == len(embedding) == 300
        check(cfg["coverage"],len(success),len(embedding))
        check(cfg["certificates"],sum(row["restore_ok"]=="True" for row in success),len(success))
        assert cfg["statuses"]==Counter(row["status"] for row in embedding)
        for mode, expected in cfg["excerpts"].items():
            selected = [row for row in data if row["kind"]=="excerpt" and row["condition"]==mode]
            check(expected,sum(row["accepted"]=="True" for row in selected),len(selected))
        erased = [row for row in data if row["kind"]=="erase"]
        check(cfg["erasure"],sum(row["accepted"]=="True" for row in erased),len(erased))
        for cap, result in cfg["random"].items():
            selected = [row for row in data if row["kind"]=="attack"
                        and row["policy"]=="random" and row["condition"]==cap]
            assert len({row["id"] for row in selected}) == len(selected) == 200
            check(result["accepted"],sum(row["accepted"]=="True" for row in selected),len(selected))
        for n, modes in cfg["learning"].items():
            if modes is None:
                assert len(success)<int(n)
                continue
            for mode, result in modes.items():
                selected = [row for row in data if row["kind"]=="attack"
                            and row["policy"]=="learned_"+mode and row["condition"]==n]
                assert len({row["id"] for row in selected}) == len(selected) == 200
                check(result["accepted"],sum(row["accepted"]=="True" for row in selected),len(selected))
    eligible = [cfg for cfg in report["configs"].values() if cfg["rankable"]]
    assert report["N_rank"] == (min(50,min(cfg["coverage"]["k"] for cfg in eligible)) if eligible else None)
    if not eligible:
        assert report["selected_gamma_m_max"] is None
    print("Verified",len(doc),"calibration aggregates and",len(items),"per-item outcomes")


if __name__=="__main__":
    main()
