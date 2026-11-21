"""Copy an explicit sanitized evidence whitelist to a new research-sync directory."""
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from core.paths import PROJECT_ROOT, RESULTS_DIR

RUN="c2rag_openstax_real_source_dev_20261101_01"
R=RESULTS_DIR/RUN
DEST=Path(r"D:\pycharm\research-sync-1031/CG/experiments/2026-11-01-c2rag-openstax-real-source-dev-01")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(path, obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def main():
    assert not DEST.exists(), "APPEND_ONLY_PUBLICATION"
    summary=json.loads((R/"EXECUTION_SUMMARY.json").read_text(encoding="utf-8"))
    assert summary["status"]=="EXECUTED_EXPLORATORY" and summary["generation_calls"]==24
    # Final local hashes, excluding the final manifest itself, generated once.
    assert not (R/"LOCAL_FINAL_MANIFEST.json").exists()
    allfiles=[p for p in R.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    allfiles+=list((PROJECT_ROOT/"experiments"/RUN).glob("*.py"))
    final=[{"path":p.relative_to(PROJECT_ROOT).as_posix(),"bytes":p.stat().st_size,"sha256":sha(p)} for p in sorted(allfiles)]
    save(R/"LOCAL_FINAL_MANIFEST.json",{"scope":"All local evidence and experiment source, excluding this manifest itself","files":final})
    DEST.mkdir(parents=True)
    records=[]
    whitelist=["PROTOCOL.md","RESULT.md","BASELINE_COMPARISON.md","FAILURES.md","CHECKPOINT.md","decision.json",
               "LICENSE_AUDIT.md","SANITIZATION.md","SOURCE_MANIFEST.json","PREFIX_EVALUATIONS.csv","PREFIX_EVALUATIONS.json",
               "USAGE_SUMMARY.json","COMPARISON_SUMMARY.json","STATE_AUDIT.json","TEACHING_QUALITY.csv",
               "EXECUTION_SUMMARY.json","OBSERVATION_LOCK.json","TRANSLATION_CHECKS.json","CONDITION_CHECKS.json",
               "TRANSLATION_QUANTITY_UNIT_POSTCHECK.json","TRANSLATION_QUANTITY_UNIT_POSTCHECK_attempt01.json",
               "INPUT_VISIBILITY_AUDIT.json","HISTORY_PRESERVATION.json","ENVIRONMENT.json","QUESTIONS.json","PROMPTS.json",
               "ENGINEERING_CODE_LOCK.json","ENGINEERING_RECOVERY.json","PREPARATION_FAILURE_01.json","POSTPROCESS_FAILURES.json"]
    for name in whitelist:
        source=R/name
        shutil.copyfile(source,DEST/name)
        records.append({"source":source.relative_to(PROJECT_ROOT).as_posix(),"published":name,"sha256":sha(source),"transformation":"verbatim"})
    audit=(R/"TRANSLATION_AUDIT.md").read_text(encoding="utf-8")
    audit=re.sub(r"- S12：.*", "- S12：源值及初末绑定按本地冻结材料核对；本公开版去除具体输入数值，原审计文件本地保留。",audit)
    (DEST/"TRANSLATION_AUDIT.md").write_text(audit,encoding="utf-8")
    records.append({"source":"local TRANSLATION_AUDIT.md","published":"TRANSLATION_AUDIT.md","source_sha256":sha(R/"TRANSLATION_AUDIT.md"),"sha256":sha(DEST/"TRANSLATION_AUDIT.md"),"transformation":"S12 input quantities removed; no changes to conclusions"})
    (DEST/"code").mkdir()
    for source,name in [(PROJECT_ROOT/"experiments"/RUN/"run_once.py","run_once.py"),
                        (PROJECT_ROOT/"experiments"/RUN/"README.md","README.md"),
                        (R/"attempt_01_preflight_failure/run_once.py","attempt01_run_once.py")]:
        shutil.copyfile(source,DEST/"code"/name)
        records.append({"source":source.relative_to(PROJECT_ROOT).as_posix(),"published":"code/"+name,"sha256":sha(source),"transformation":"verbatim, code review copy; original project layout and local inputs required to execute"})
    freeze=json.loads((R/"FREEZE_MANIFEST.json").read_text(encoding="utf-8"))
    published_freeze={**freeze,"original_local_manifest_sha256":sha(R/"FREEZE_MANIFEST.json"),"transformation":"absolute local path to project-relative path"}
    published_freeze["files"]=[{**x,"path":Path(x["path"]).relative_to(PROJECT_ROOT).as_posix()} for x in freeze["files"]]
    save(DEST/"PUBLISHED_FREEZE_INDEX.json",published_freeze)
    save(DEST/"LOCAL_EVIDENCE_HASHES.json",{"scope":"Paths and hashes only, raw content excluded","local_manifest_sha256":sha(R/"LOCAL_FINAL_MANIFEST.json"),"files":final})
    (DEST/".gitattributes").write_text("* -text\n",encoding="ascii")
    save(DEST/"PUBLICATION_MANIFEST.json",{"run":RUN,"files":records,"raw_texts_not_published":True,"local_final_manifest_sha256":sha(R/"LOCAL_FINAL_MANIFEST.json")})
    lines=[sha(p)+"  "+p.relative_to(DEST).as_posix() for p in sorted(DEST.rglob("*")) if p.is_file()]
    (DEST/"SHA256SUMS.txt").write_text("\n".join(lines)+"\n",encoding="utf-8")
    receipt=PROJECT_ROOT/"artifacts/reports"/RUN
    receipt.mkdir(parents=True,exist_ok=False)
    save(receipt/"publication_manifest.json",{"directory":str(DEST),"files":[{"path":p.relative_to(DEST).as_posix(),"sha256":sha(p)} for p in sorted(DEST.rglob("*")) if p.is_file()]})
    print(json.dumps({"published_files":sum(p.is_file() for p in DEST.rglob("*")),"directory":str(DEST),"local_final_manifest_sha256":sha(R/"LOCAL_FINAL_MANIFEST.json")},ensure_ascii=False))


if __name__=="__main__":
    main()
