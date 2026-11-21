"""Post-run accounting and source-separated audits; never used as an online method."""
import csv
import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.paths import RESULTS_DIR

R = RESULTS_DIR / "c2rag_openstax_real_source_dev_20261101_01"


def read(name):
    return json.loads((R/name).read_text(encoding="utf-8"))


def save(name, value):
    (R/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    assert (R/"EXECUTION_SUMMARY.json").exists(), "WAIT_FOR_RUN_COMPLETION"
    assert not (R/"POSTPROCESS_COMPLETED.json").exists(), "DO_NOT_OVERWRITE_POSTPROCESS"
    transcript=[json.loads(s) for s in (R/"TRANSCRIPT.jsonl").read_text(encoding="utf-8").splitlines()]
    raw = read("EVALUATIONS_RAW.json")
    gold = read("PRIVATE_SOURCE_GOLD.json")
    rows=[]
    labels={}
    state_integrity_through_prefix = {}
    complete_state = True
    for t in range(1,7):
        p = R/("states/P%02d.json"%t)
        complete_state = complete_state and p.exists() and bool(read("states/P%02d.json"%t)["update_valid"])
        state_integrity_through_prefix[t] = complete_state
    for turn in range(1,7):
        for method in ["B1-L","B3","B1-S"]:
            e=next((v for v in raw if v["prefix"]==turn and v["method"]==method),None)
            row={"prefix":turn,"method":method,"run_status":"NOT_RUN_UNSUPPORTED","model_label":None,
                 "final_energy_nJ":None,"source_numeric_match":None,"source_T_comparison":None,
                 "evidence_quotes_exact":None,"input_tokens":None,"output_tokens":None,"seconds":None,
                 "update_valid":None,"update_input_tokens":None,"update_output_tokens":None,"update_seconds":None,
                 "state_complete_through_prefix":None,
                 "independent_human_gold":False,"raw_output_sha256":None}
            if e is not None:
                pred=e.get("parsed")
                valid=bool(e["complete"] and isinstance(pred,dict) and pred.get("label") in {"ENTAILED","REFUTED","UNKNOWN","MATERIAL_UNCLEAR"})
                row.update(run_status="OK" if valid else "INVALID_OR_INCOMPLETE_OUTPUT",model_label=pred.get("label") if isinstance(pred,dict) else None,
                           input_tokens=e["input_tokens"],output_tokens=e["output_tokens"],seconds=e["seconds"],
                           raw_output_sha256=hashlib.sha256(e["content"].encode()).hexdigest())
                if valid:
                    value=pred.get("final_energy_nJ")
                    row["final_energy_nJ"]=value
                    row["source_numeric_match"]=abs(float(value)-gold["final_energy_source_rounded_nJ"])<=0.15 if isinstance(value,(float,int)) and not isinstance(value,bool) else None
                    row["source_T_comparison"]={"ENTAILED":"COMPATIBLE_WITH_SOURCE","REFUTED":"CONTRADICTS_SOURCE","UNKNOWN":"NO_SOURCE_CLAIM","MATERIAL_UNCLEAR":"NO_SOURCE_CLAIM"}[pred["label"]]
                    quotes=pred.get("evidence",[])
                    checks=[]
                    for q in quotes:
                        t=q.get("turn") if isinstance(q,dict) else None
                        s=q.get("quote") if isinstance(q,dict) else None
                        checks.append(type(t) is int and 1<=t<=turn and isinstance(s,str) and bool(s) and
                                      (s in transcript[t-1]["answer"] or s in transcript[t-1]["question"]))
                    row["evidence_quotes_exact"]=bool(checks) and all(checks)
                    labels[turn,method]=pred["label"]
                if method=="B3":
                    for k in ["update_valid","update_input_tokens","update_output_tokens","update_seconds"]:
                        row[k]=e[k]
                    row["state_complete_through_prefix"] = state_integrity_through_prefix[turn]
                    if row["run_status"] == "OK" and not state_integrity_through_prefix[turn]:
                        row["run_status"] = "INCOMPLETE_STATE_AFTER_UPDATE_FAILURE"
            rows.append(row)
    with (R/"PREFIX_EVALUATIONS.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    save("PREFIX_EVALUATIONS.json",rows)
    agreement=[]
    for t in range(1,7):
        a,b=labels.get((t,"B1-L")),labels.get((t,"B3"))
        agreement.append({"prefix":t,"B1-L":a,"B3":b,"disagree":a!=b if a and b else None})
    usage={}
    for row in read("CALL_LEDGER.json"):
        kind="teaching" if row["id"].startswith("T") else "B3_update" if row["id"].startswith("B3_UPDATE") else "B3_judgment" if row["id"].startswith("B3_") else "B1-L"
        bucket=usage.setdefault(kind,{"calls":0,"input_tokens":0,"output_tokens":0,"seconds":0.0,"non_eos_calls":0})
        bucket["calls"]+=1
        for k in ["input_tokens","output_tokens","seconds"]:
            bucket[k]+=row.get(k) or 0
        bucket["non_eos_calls"]+=row.get("stop_type")!="eos"
    save("USAGE_SUMMARY.json",usage)
    # Persistence and evidence checks are representation diagnostics, not a new inference method.
    states=[]
    prev={"facts":[],"rules":[],"unresolved":[]}
    for t in range(1,7):
        p=R/("states/P%02d.json"%t)
        if not p.exists():
            continue
        s=read("states/P%02d.json"%t)
        persisted=all(s["state"][k][:len(prev[k])]==prev[k] for k in prev)
        quotes=s["quote_checks"]
        states.append({"prefix":t,"update_valid":s["update_valid"],"previous_entries_preserved":persisted,
                       "fact_count":len(s["state"]["facts"]),"rule_count":len(s["state"]["rules"]),"unresolved_count":len(s["state"]["unresolved"]),
                       "quote_records":len(quotes),"exact_quote_count":sum(bool(q["exact_in_current_turn"]) for q in quotes),
                       "matching_turn_count":sum(bool(q["turn_matches"]) for q in quotes)})
        prev=s["state"]
    save("STATE_AUDIT.json",states)
    # Independent exact arithmetic on the explicitly identified, author-reviewed visible premises.
    # This does NOT automatically interpret NL, establish an independent gold, or count as B1-S.
    q2,q4,q6=[transcript[t-1]["answer"] for t in [2,4,6]]
    premise_checks={"q2_initial_C": "20.0" in q2 and "pF" in q2,"q2_initial_V":"40.0" in q2,
                    "q4_kappa":"2.1" in q4,"q4_isolated_full_fill":"断开" in q4 and "完全填满" in q4,
                    "q6_capacitance_relation":"C_1 = \\kappa C_0" in q6,
                    "q6_charge_invariant":"保持不变" in q6,"q6_energy_law":"CV^2" in q6}
    ratio=Fraction(1)/Fraction("2.1")
    initial=Fraction("20.0")*Fraction("40.0")**2/Fraction(2)/1000
    final=initial/Fraction("2.1")
    # Visible incorrect derived statement is retained, never silently treated as the true U0.
    claimed_initial=Fraction("1.6")/1000
    save("LOCAL_MATHEMATICAL_AUDIT.json",{
        "classification":"AUTHOR_REVIEWED_PREMISES_PLUS_INDEPENDENT_EXACT_ARITHMETIC_NOT_B1S",
        "premise_checks":premise_checks,"supporting_qualitative_witness_turns":[4,6],
        "qualitative_ratio_exact":str(ratio),"T_supported_by_this_subset":ratio<Fraction(1,2),
        "drop_turn4_counterexamples_kappa":["3/2","3"],"drop_turn4_ratios":[str(Fraction(2,3)),str(Fraction(1,3))],
        "drop_turn6":"No delivered relation fixing energy ratio from dielectric constant remains in this two-turn subset; UNKNOWN under frozen public priors",
        "numeric_support_subset_turns":[2,4,6],"correct_initial_energy_nJ":str(initial),"computed_final_energy_nJ":str(final),
        "matches_source_rounded":abs(float(final)-gold["final_energy_source_rounded_nJ"])<=0.15,
        "actual_Q2_claimed_initial_energy_nJ":str(claimed_initial),"claim_over_correct_initial":str(claimed_initial/initial),
        "whole_history_numeric_reconstruction":"CONFLICTED: exact numerical witness requires rejecting Q2 incorrect arithmetic; do not call unconditional consistent full-history recovery",
        "independent_human_review":False})
    original=read("FREEZE_MANIFEST.json")
    repair=read("ENGINEERING_CODE_LOCK.json")
    integrity=[]
    for f in original["files"]:
        actual=digest(f["path"])
        known_repair=Path(f["path"]).name=="run_once.py" and actual==repair["repaired_sha256"] and f["sha256"]==repair["original_sha256"]
        integrity.append({"path":f["path"],"original_unchanged":actual==f["sha256"],"known_pre_generation_interface_repair":known_repair,"valid":actual==f["sha256"] or known_repair})
    save("INTEGRITY_CHECK.json",{"all_valid":all(v["valid"] for v in integrity),"files":integrity,"transcript_matches_observation_lock":digest(R/"TRANSCRIPT.jsonl")==read("OBSERVATION_LOCK.json")["transcript_sha256"]})
    save("COMPARISON_SUMMARY.json",{"agreement":agreement,"usage":usage,"state_audit":states,
         "independent_human_gold":False,"accuracy":None,"one_asset_only":True,
         "source_numeric_match_is_not_text_entailment":True})
    save("POSTPROCESS_COMPLETED.json",{"models_called":0,"solver_model":"Python Fraction exact arithmetic only","rows":len(rows),"frozen_method_inputs_unchanged":all(v["valid"] for v in integrity)})
    print(json.dumps({"agreement":agreement,"usage":usage,"states":states},ensure_ascii=False))


if __name__=="__main__":
    main()
