"""Independently verify blank review workbooks and package public allowlists."""

import csv
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.paths import PROJECT_ROOT, RESULTS_DIR  # noqa: E402

SOURCE = RESULTS_DIR / "c2rag_r38_semantic_admission_20261029_01"
OUT = PROJECT_ROOT / "artifacts/c2rag_r38_blind_review_20261031_01"
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def cells(z, name):
    strings = []
    if "xl/sharedStrings.xml" in z.namelist():
        strings = ["".join(x.itertext()) for x in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("s:si", NS)]
    result = {}
    for c in ET.fromstring(z.read(name)).findall(".//s:sheetData/s:row/s:c", NS):
        node = c.find("s:v", NS)
        text = node.text if node is not None and node.text is not None else ""
        if c.get("t") == "s" and text:
            text = strings[int(text)]
        elif c.get("t") == "inlineStr":
            text = "".join(c.find("s:is", NS).itertext())
        result[c.get("r")] = {"value": text, "formula": c.find("s:f", NS)}
    return result


def main():
    checks = []

    def check(condition, name):
        checks.append({"check": name, "passed": bool(condition)})
        if not condition:
            raise AssertionError(name)

    manifest = read(SOURCE / "MANIFEST.json")
    for name, expected in manifest["files"].items():
        check(sha((SOURCE / name).read_bytes()) == expected, "frozen_source_unchanged:" + name)
    for name, expected in manifest["scripts"].items():
        check(sha((PROJECT_ROOT / name).read_bytes()) == expected, "frozen_script_unchanged:" + name)
    packet_hashes = {}
    for packet in ("A", "B"):
        folder = OUT / "outputs" / f"盲标包_{packet}"
        expected_files = {
            f"填写表_{packet}.xlsx", "先读我_填写说明.txt", "原始标注说明.md",
            "公开材料/packet.json", "公开材料/packet.md", "公开材料/annotations.csv",
            "公开材料/public_contexts/C01.json", "公开材料/public_contexts/M02.json", "公开材料/public_contexts/E01.json",
        }
        actual = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}
        check(actual == expected_files, "strict_package_allowlist:" + packet)
        for name in ("packet.json", "packet.md", "annotations.csv"):
            check((folder / "公开材料" / name).read_bytes() == (SOURCE / f"annotation_{packet}" / name).read_bytes(),
                  "original_blind_content_identical:" + packet + name)
        for a in ("C01", "M02", "E01"):
            pub = folder / "公开材料/public_contexts" / f"{a}.json"
            check(pub.read_bytes() == (SOURCE / f"annotation_{packet}/public_contexts/{a}.json").read_bytes(),
                  "original_public_prior_identical:" + packet + a)
            check(read(pub)["actual_selected_world"] == "NOT_PRESENT", "no_selected_world:" + packet + a)
        with (SOURCE / f"annotation_{packet}/annotations.csv").open(encoding="utf-8-sig", newline="") as f:
            reference = list(csv.DictReader(f))
        cases = read(SOURCE / f"annotation_{packet}/packet.json")
        by_id = {c["case_id"]: c for c in cases}
        workbook = folder / f"填写表_{packet}.xlsx"
        with zipfile.ZipFile(workbook) as z:
            book = ET.fromstring(z.read("xl/workbook.xml"))
            sheets = book.findall("s:sheets/s:sheet", NS)
            check([s.get("name") for s in sheets] == ["填写表", "填写说明", "公开先验"], "only_three_visible_sheets:" + packet)
            check(all(s.get("state", "visible") == "visible" for s in sheets), "no_hidden_sheet:" + packet)
            rels = {x.get("Id"): x.get("Target") for x in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
            targets = []
            for s in sheets:
                key = s.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                target = rels[key]
                targets.append(target.lstrip("/") if target.startswith("/") else "xl/" + target)
            form, guide = cells(z, targets[0]), cells(z, targets[1])
            for i, r in enumerate(reference, 7):
                check(form[f"A{i}"]["value"] == r["case_id"] and form[f"B{i}"]["value"] == r["prefix_turn"],
                      f"prefix_id_matches:{packet}:{i}")
                case = by_id[r["case_id"]]
                n = int(r["prefix_turn"])
                expected = "\n\n".join(f"第{t['turn']}轮  {t['agent_id']} → {t['recipient']}\n问：{t['query']}\n答：{t['reply']}" for t in case["turns"][:n])
                check(form[f"D{i}"]["value"] == expected, f"only_actual_current_prefix:{packet}:{i}")
                check(form[f"F{i}"]["value"] == "PENDING_HUMAN_REVIEW", f"pending_not_completed:{packet}:{i}")
                for col in "GHIJKLMNOPQR":
                    c = form.get(f"{col}{i}", {})
                    check(not c.get("value") and c.get("formula") is None, f"blank_truth:{packet}:{col}{i}")
            for cell in ("B4", "B5", "B6", "B7"):
                check(not guide.get(cell, {}).get("value"), "reviewer_profile_blank:" + packet + cell)
            strings = z.read("xl/sharedStrings.xml").decode() if "xl/sharedStrings.xml" in z.namelist() else ""
            check(all(x not in strings for x in ("construction_condition", "expected_leak_label", "selected_hypothesis", "source_target", "blind_crosswalk")),
                  "no_private_construction_keys:" + packet)
            check(not any(x.startswith("xl/externalLinks/") for x in z.namelist()), "no_external_workbook_links:" + packet)
        files = {name: sha((folder / name).read_bytes()) for name in sorted(actual)}
        check(len(reference) == 52, "all_52_prefixes:" + packet)
        zip_path = OUT / "outputs" / f"C2RAG_盲标包_{packet}.zip"
        with zipfile.ZipFile(zip_path, "x", compression=zipfile.ZIP_DEFLATED) as z:
            for name in sorted(actual):
                z.write(folder / name, f"盲标包_{packet}/{name}")
        with zipfile.ZipFile(zip_path) as z:
            check(z.testzip() is None, "zip_crc_valid:" + packet)
            for name, expected in files.items():
                check(sha(z.read(f"盲标包_{packet}/{name}")) == expected, "zip_byte_identity:" + packet + name)
        packet_hashes[packet] = {"zip": str(zip_path), "sha256": sha(zip_path.read_bytes()), "files": files,
                                  "histories": 24, "prefixes": 52}
    result = {"status": "PASS", "checks": len(checks), "details": checks,
              "source_manifest_sha256": sha((SOURCE / "MANIFEST.json").read_bytes()),
              "packets": packet_hashes, "human_submissions": 0,
              "human_truth_generated": False, "old_frozen_files_changed": False}
    with (OUT / "organizer_checks/PACKAGE_VERIFICATION.json").open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps({"status": result["status"], "checks": len(checks), "packets": {k: {a: b for a, b in v.items() if a != "files"} for k, v in packet_hashes.items()}}, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
