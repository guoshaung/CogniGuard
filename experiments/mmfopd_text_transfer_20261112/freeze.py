"""Lock all test inputs and code after the development interface check."""
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys

from data_cases import BRIDGE_REV, CACHE, HERE, PEER_REV, ROOT, RUN, dump, read_json

SOURCE_PATHS = [
    "core/paths.py",
    "protection/common/schemas.py",
    "protection/common/text_utils.py",
    "protection/student_profile/src/fopd/profile_selector.py",
    "protection/student_profile/src/fopd/task_attention.py",
    "protection/student_profile/src/fopd/orthogonal_decoder.py",
    "protection/student_profile/src/fopd/multimodal_profile.py",
    "protection/student_profile/configs/default.yaml",
]


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def main():
    target = HERE / "freeze_manifest.json"
    if target.exists():
        raise FileExistsError(target)
    cases = read_json(RUN / "cases.local.json")
    dev = rows(RUN / "teaching_dev.local.jsonl")
    judge = rows(RUN / "judge_dev.local.jsonl")
    assert len(dev) == len(judge) == 26
    assert {r["case"] for r in dev} == {r["case"] for r in cases if r["split"] == "dev"}
    assert all(row["history_tokens"] <= 192 and len(row["indices"]) <= 3
               for trace in dev for arm, row in trace["rows"].items() if arm != "B1")
    assert all(not trace["rows"]["B0"]["wire"] and not trace["rows"]["B8"]["wire"] for trace in dev)
    assert not (RUN / "teaching_test.local.jsonl").exists()
    assert sum(j["judge"]["status"] == "OK" for j in judge) >= 20
    for path in SOURCE_PATHS:
        dest = HERE / "frozen_source" / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / path, dest)
    models = sorted((ROOT / "assets/models/qwen2.5-7b-instruct-q4_k_m-official").glob("*.gguf"))
    embed = ROOT / "assets/models/hf_cache/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    files = [*(ROOT / path for path in SOURCE_PATHS), *models,
             embed / "model.safetensors", embed / "tokenizer.json",
             *(HERE / name for name in ["data_cases.py", "experiment.py", "analyze.py", "math_reference.py", "blind_review.py", "judge_calibration.py", "replay_selected.py", "protocol_dev.md", "protocol_frozen.md", "freeze.py"]),
             RUN / "cases.local.json", RUN / "gold.local.json",
             CACHE / "llama-b12224-bin-win-vulkan-x64.zip",
             CACHE / "PeerMathDial/data/turns.jsonl",
             CACHE / "bridge/dataset/validation.json", CACHE / "bridge/dataset/test.json"]
    stats = {
        "frozen_before_first_test_generation": True,
        "code_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "model": "Qwen2.5-7B-Instruct Q4_K_M llama.cpp b12224 Vulkan",
        "peer_revision": PEER_REV,
        "bridge_revision": BRIDGE_REV,
        "python": sys.version,
        "packages": {name: importlib.metadata.version(name) for name in ["torch", "transformers", "numpy", "PyYAML"]},
        "dev": {"cases": len(dev), "actual_teacher_calls": sum(r["actual_calls"] for r in dev),
                "teacher_method_rows_ok": sum(r["teacher"]["status"] == "OK" for t in dev for r in t["rows"].values()),
                "judge_ok": sum(j["judge"]["status"] == "OK" for j in judge),
                "grader_controls_passed": sum(c["correctness_discriminated"] for c in read_json(RUN / "grader_controls.json"))},
        "sha256": {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p) for p in files},
    }
    dump(target, stats)
    print(json.dumps(stats["dev"]))


if __name__ == "__main__":
    main()
