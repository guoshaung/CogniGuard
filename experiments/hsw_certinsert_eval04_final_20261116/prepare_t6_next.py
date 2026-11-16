"""Freeze replay inputs at the T6 stage boundaries."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from t6_sources import HERE, OUT, ROOT, load, sha, write


def h(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def union():
    ledger=OUT/"stage_c_embedding/verified.local.jsonl"
    result=load(HERE/"T6_EMBED_RESULT.json")
    listed=load(HERE/"T6_BASELINE_UNION.json")
    assert h(ledger)==result["local_ledger_sha256"]==listed["verifier_ledger_sha256"]
    evidence=[json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    accepted={r["id"]:{name:a["success"] for name,a in r["arms"].items()}
              for r in evidence if any(a["success"] for a in r["arms"].values())}
    assert accepted=={r["id"]:r["success"] for r in listed["sources"]}
    assert len(evidence)==result["planned"]==200
    e=ROOT/"var/results/hsw-st/certinsert_eval_20261111_01/run01"
    old=ROOT/"var/results/hsw-st/english_replication_20261110_01/e1_guarded"
    src=ROOT.parents[1]/"CogniGuard/var/results/hsw_gpu0_deploy_20261102_r21/kgw_ref"
    mask=e/"restricted/UNIGRAM_GREEN.json"
    sources=[HERE/"T6_BASELINE_UNION.json",HERE/"T6_EMBED_RESULT.json",HERE/"t6_model_arms.py",
             e/"EVAL_FREEZE.json",e/"PUBLIC_TOKENIZER_VALIDATION.json",mask]
    dev=load(e/"EVAL_FREEZE.json")
    assert h(dev["server"])==dev["server_sha256"]
    published=load(ROOT/"var/results/hsw-st/certinsert_eval03_lite_20261112/run01/batch02/FREEZE.json")
    key=h(old/"frozen_comparison09/restricted/kgw_key.txt")
    assert key==published["key_sha256"] and h(mask)==published["unigram_mask_sha256"]
    write(HERE/"T6_MODEL_ARMS_FREEZE.json",{"planned":len(accepted),
          "files_sha256":{p.relative_to(ROOT).as_posix():h(p) for p in sources},
          "kgw_key_sha256":key,"platform":"frozen EVAL03 Qwen runtime",
          "kgw_reference_sha256":{p.name:h(p) for p in src.glob("*.py")},
          "compression_ratio":.7,"same_inputs":["KGW","Unigram"],"source":"verified success union only"})


def variants(primary):
    name="score_registry_primary.json" if primary else "score_registry.json"
    dest="T6_PRIMARY_VARIANT_FREEZE.json" if primary else "T6_VARIANT_FREEZE.json"
    path=OUT/name
    items=load(path)["items"]
    assert all(h(ROOT/r["path"])==r["sha256"] for r in items)
    codes=("t6_registry.py","t6_metrics.py","t6_ocr.py","t6_frequency.py")
    write(HERE/dest,{"registry_sha256":h(path),"planned":dict(Counter(r["method"] for r in items)),
                     "code_sha256":{name:h(HERE/name) for name in codes},
                     "crop_policy":"first/middle/last100 and first/middle200 when available",
                     "ocr":"EVAL03 CPU reuse","planned_compressions":len(items)})


def p1(primary):
    folder=OUT/"frequency"/("primary" if primary else "all")
    manifest=load(folder/"manifest.json")
    assert h(folder/"inputs.local.json")==manifest["inputs_sha256"]
    write(HERE/("T6_P1_PRIMARY_FREEZE.json" if primary else "T6_P1_FREEZE.json"),{
        "attack_manifest_sha256":h(folder/"manifest.json"),
        "attack_inputs_sha256":manifest["inputs_sha256"],"conditions":manifest["conditions"],
        "planned":manifest["planned"],"before_attack_score":True})


def postmark():
    path=OUT/"postmark/CALIBRATION.json"
    result=load(path)
    assert len(result["items"])==893
    assert result["empirical_fp"]*100<=result["scorable"]
    write(HERE/"T6_POSTMARK_GATE.json",
          {"calibration_sha256":h(path),"threshold":result["threshold"],
           "empirical_fp":result["empirical_fp"],"scorable":result["scorable"],
           "planned_insertion":200,"strictly_greater":True})


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("step",choices=("union","variants","p1","postmark"))
    ap.add_argument("--primary",action="store_true")
    a=ap.parse_args()
    if a.step in ("variants","p1"):
        globals()[a.step](a.primary)
    else:
        globals()[a.step]()


if __name__=="__main__":
    main()
