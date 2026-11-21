"""Check blank review materials, source fidelity and ZIP isolation; no inference."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.paths import PROJECT_ROOT, RESULTS_DIR

HERE = Path(__file__).resolve().parent
OUT = RESULTS_DIR / HERE.name
ART = PROJECT_ROOT / "artifacts" / HERE.name


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, data) -> None:
    with path.open("x", encoding="utf-8", newline="") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main() -> None:
    assert not (OUT / "MATERIAL_QA.json").exists(), "Keep past validation records; do not overwrite"
    source = load(OUT / "SOURCE_MANIFEST.json")
    for row in source["files"]:
        assert sha(Path(row["path"]).read_bytes()) == row["sha256"]
        assert sha((OUT / "source_snapshot" / Path(row["path"]).name).read_bytes()) == row["sha256"]
    cross = load(OUT / "organizer_only/blind_crosswalk.json")["packets"]
    inputs = load(OUT / "organizer_only/input_transcript_index.json")
    packet_hashes = load(OUT / "PACKET_HASHES.json")
    checks = []
    for reviewer in ("A", "B"):
        name = f"HUMAN_REVIEW_{reviewer}.md"
        raw = (OUT / name).read_bytes()
        text = raw.decode("utf-8")
        assert sha(raw) == packet_hashes[reviewer]
        assert "HUMAN_REVIEW_PENDING" in text
        assert not re.search(r"(?m)^\s*-\s*\[[xX]\]", text)
        assert not re.search(r"\b[123][PN]\b", text)
        for forbidden in ("补全 A", "补全 B", "设计判定", "E=W", "C⇒P", "organizer_only", "blind_crosswalk"):
            assert forbidden not in text, forbidden
        cards = re.split(r"^## 案例卡 ", text, flags=re.M)[1:]
        assert len(cards) == 6
        assert set(cross[reviewer]["mapping"].values()) == set(inputs["cases"])
        assert text.count("**问题2：到这里能够确定目标吗？只选一个。**") == 18
        assert text.count("**问题1：自然吗？只选一个。**") == 6
        assert text.count("**问题3：第三轮的依据是什么？**") == 6
        assert text.count("**问题4：有没有明显设计问题？") == 6
        for card in cards:
            alias = card.split("：", 1)[0]
            key = cross[reviewer]["mapping"][alias]
            family = inputs["families"][key[0]]
            turns = inputs["cases"][key]["turns"]
            quoted = [line[2:] for line in card.splitlines() if line.startswith("> ")]
            assert quoted[0] == family["target"]
            assert quoted[1:] == [t[field] for t in turns for field in ("query", "reply")]
            assert family["public_context"] in card
            for turn in turns:
                assert f"学生问{turn['agent']}：" in card
            assert card.count("填写：____") == 1
            checks.append({"reviewer": reviewer, "card": alias, "three_turns_exact": True, "public_context_exact": True, "target_is_question_not_fact": True, "responses_unfilled": True})
        with zipfile.ZipFile(ART / f"盲审包_{reviewer}.zip") as archive:
            assert set(archive.namelist()) == {name, "PACKET_VERSION.json"}
            assert archive.read(name) == raw
            version = json.loads(archive.read("PACKET_VERSION.json"))
            assert version["reviewer"] == reviewer and version["sha256"] == sha(raw)
            assert version["contains_expected_answers"] is False
            checks.append({"reviewer": reviewer, "only_own_packet_and_version_in_zip": True})
    assert cross["A"]["mapping"] != cross["B"]["mapping"]
    # Check the actual single edit in each pair, not the intended condition name.
    for group, before, after, position in (("1", "导出名单", "预览名单", 0), ("2", "未触发", "未记录", 2), ("3", "必须", "建议", 2)):
        left = inputs["cases"][group + "P"]["turns"]
        right = inputs["cases"][group + "N"]["turns"]
        for i in range(3):
            assert left[i]["agent"] == right[i]["agent"]
            assert left[i]["query"] == right[i]["query"]
            if i == position:
                assert left[i]["reply"].replace(before, after) == right[i]["reply"]
            else:
                assert left[i]["reply"] == right[i]["reply"]
        checks.append({"pair": group, "only_registered_text_change": True})
    required = ["CASE_GATE_AUDIT.md", "HUMAN_REVIEW_A.md", "HUMAN_REVIEW_B.md", "HUMAN_ADJUDICATION_TEMPLATE.md", "BASELINE_PREREGISTRATION.md", "ALGORITHM_GAP_HYPOTHESES.md", "RESULT.md", "decision.json"]
    assert all((OUT / name).is_file() for name in required)
    decision = load(OUT / "decision.json")
    assert decision["real_human_submissions"] == 0 and decision["gold_frozen"] is False
    assert decision["model_calls"] == decision["solver_calls"] == decision["algorithm_comparisons"] == 0
    write_new(OUT / "MATERIAL_QA.json", {"status": "PASS_MATERIAL_INTEGRITY_ONLY", "semantic_validity_independently_proven": False, "real_human_reviews": 0, "source_versions_unchanged": True, "checked_cards": 12, "checked_visible_prefixes": 36, "checks": checks, "required_files": required})
    paths = [p for parent in (OUT, ART, HERE) for p in parent.rglob("*") if p.is_file() and p.name != "FILE_MANIFEST.json" and "__pycache__" not in p.parts]
    write_new(OUT / "FILE_MANIFEST.json", {"version": decision["version"], "human_gold_frozen": False, "scope": "Delivery/material version lock only; manifest excludes itself", "files": [{"path": str(p.relative_to(PROJECT_ROOT)), "bytes": p.stat().st_size, "sha256": sha(p.read_bytes())} for p in sorted(paths)]})
    print(json.dumps({"output": str(OUT), "material_integrity": "PASS", "cards_checked": 12, "visible_prefixes_checked": 36, "independent_human_reviews": 0, "method_performance": "NOT_RUN", "files_hashed": len(paths)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
