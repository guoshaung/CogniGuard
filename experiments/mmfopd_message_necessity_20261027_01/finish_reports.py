"""Resume report-only work after a Windows GBK decoding error. No fitting/predicting."""
import ast
import datetime
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[1]


def read(name):
    return (P / name).read_text(encoding="utf8")


def load(name):
    return json.loads(read(name))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    (P / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf8")


def main():
    if (P / "POSTPROCESS_COMPLETE.json").exists():
        raise RuntimeError("No overwrite: report finalization already completed")
    validation = load("evidence_validation.json")
    assert validation["status"] == "PASS"
    lock = load("execution_lock.json")
    audit = load("audit.json")
    train = load("TRAIN_COMPLETE.json")
    assert all(sha(P / name) == digest for name, digest in lock["source_sha256"].items())
    assert all(sha(ROOT / name) == digest for name, digest in audit["sources_sha256"].items())
    assert all(sha(P / "models_LOCAL" / name) == digest for name, digest in train["model_sha256"].items())
    # Recover the existing interpretation literally; execute no earlier validation,
    # model loading, training, prediction, or development-set evaluation code.
    tree = ast.parse(read("finalize.py"))
    notes = [node.value.value for node in ast.walk(tree)
             if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
             and isinstance(node.value.value, str)
             and any(isinstance(t, ast.Name) and t.id == "note" for t in node.targets)]
    assert len(notes) == 1
    report_names = ["RESULT.md", "MEETING_ONE_PAGE.md", "REPRODUCE.md"]
    before = {name: sha(P / name) for name in report_names}
    result = read("RESULT.md")
    assert "## 最终解释：是否还需要新算法？" not in result
    seconds = load("completion.json")["runtime_seconds"]
    result = result.replace(f"总耗时{seconds:.2f}秒", f"评估驱动实跑{seconds:.2f}秒（不含前期审计、编码和报告工作）")
    result += notes[0]
    result += (f"\n全过程至证据核验约{validation['whole_session_elapsed_minutes_to_validation']:.2f}分钟，"
               "未用满预算追加训练。参见evidence_validation.json。主程序与协议未改；"
               "最终解释为既有结果的后处理。finalize.py在完成PASS核验后遇到Windows默认GBK读取报告错误；"
               "finish_reports.py显式UTF-8恢复整理，未重新拟合或预测开发数据。\n")
    (P / "RESULT.md").write_text(result, encoding="utf8")
    meeting = read("MEETING_ONE_PAGE.md").replace(
        "另评估已知共同授权预测Y_auth后的增量；",
        "已知共同授权预测Y_auth后，M4额外性别RF AUC增量0.277，95%[0.200,0.365]；M3重复结果不增加视图。")
    (P / "MEETING_ONE_PAGE.md").write_text(meeting, encoding="utf8")
    reproduce = read("REPRODUCE.md")
    reproduce += """

Post-run verification: evidence_validation.json is PASS. It verifies frozen sources,
44 saved models, all2365 actual dev messages, cached metrics, and student-isolated
TRAIN-only crossfit replay. No new fit or dev prediction was used. The1337 replay
messages are explicitly reconstructed evidence, not an original byte commitment.

The first finalize.py attempt completed validation and then failed reading RESULT.md
with Windows default GBK. The failed script is retained unchanged. Report-only recovery:

```powershell
python -B experiments/mmfopd_message_necessity_20261027_01/finish_reports.py
```

Both finalizers have no-overwrite guards; do not rerun them in the completed directory.
Interface tests passed4/4; cache_dir warning came from disabling pytest cache provider.
See postprocess_recovery.json for the retained failure and recovery record.
"""
    (P / "REPRODUCE.md").write_text(reproduce, encoding="utf8")
    now = datetime.datetime.now(datetime.timezone.utc)
    elapsed = (now - datetime.datetime.fromisoformat(load("config.json")["started_utc"])).total_seconds()
    assert elapsed < 90 * 60
    save("postprocess_recovery.json", {
        "failed_step": "finalize.py report text decoding after PASS evidence validation",
        "exception": "UnicodeDecodeError: Windows GBK codec reading UTF-8 RESULT.md",
        "recovery": "Explicit UTF-8 report-only finish_reports.py; original failed script preserved",
        "status": "RECOVERED", "utc": now.isoformat(),
        "new_fits": 0, "new_dev_predictions": 0,
        "report_sha256_before": before,
        "report_sha256_after": {name: sha(P / name) for name in report_names},
    })
    save("POSTPROCESS_COMPLETE.json", {
        "status": "COMPLETED", "utc": now.isoformat(),
        "whole_session_minutes": elapsed / 60, "fits_total": 45,
        "dev_evaluations": 1, "new_fits_postprocessing": 0,
        "new_dev_predictions_postprocessing": 0,
        "decision": "STOP_COMPLEX_SEARCH_FOR_THIS_PROXY_TASK_USE_RESULT_ONLY",
        "no_followup_queue": True, "external_student_uploads": 0,
    })
    save("manifest.json", {
        "classification": "LOCAL_ONLY_REAL_STUDENT_LOGS",
        "generated_utc": now.isoformat(),
        "files": {p.relative_to(P).as_posix(): {"sha256": sha(p), "bytes": p.stat().st_size}
                  for p in sorted(P.rglob("*")) if p.is_file()
                  and p.name != "manifest.json" and "__pycache__" not in p.parts},
        "external_uploads": 0, "contains_pseudonymized_real_student_records": True,
        "do_not_publish_wholesale": True,
    })
    manifest = load("manifest.json")
    assert all(sha(P / name) == info["sha256"] for name, info in manifest["files"].items())
    print(json.dumps({"status": "COMPLETED", "files_verified": len(manifest["files"]),
                      "whole_session_minutes": elapsed / 60, "new_fits": 0,
                      "new_dev_predictions": 0, "manifest_sha256": sha(P / "manifest.json")}, indent=2))


if __name__ == "__main__":
    main()
