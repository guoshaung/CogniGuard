"""Single-process bounded replay; no model, network, GPU, or production mutations."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
R=Path(__file__).resolve().parent
sys.path.insert(0,str(R.parents[1]))
from cryptography.fernet import Fernet, InvalidToken
from cogniguard.governance.audit import AuditLedger

VERSION="b-strong-replay-v1.0"
DELTA=50
MARKER_F="SYNTHETIC_F_7B91"
MARKER_G="SYNTHETIC_G_2D34"


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


class Authority:
    def __init__(self):
        self.version=1;self.allowed={"f":True,"g":True};self.queries=0

    def revoke(self,field):
        self.version+=1;self.allowed[field]=False

    def snapshot(self,at):
        self.queries+=1
        return {"version":self.version,"allowed":self.allowed.copy(),"issued_ms":at}


class ProfileGuard:
    def __init__(self,authority):
        self.authority=authority
        self.cache={"version":1,"allowed":{"f":True,"g":True},"issued_ms":0}
        self.installed=copy.deepcopy(self.cache)
        self.notifications=0;self.cache_operations=0

    def notify(self,version,at):
        self.notifications+=1
        if version>self.installed["version"]:
            self.installed={"version":self.authority.version,"allowed":self.authority.allowed.copy(),"issued_ms":at}
            self.cache=copy.deepcopy(self.installed);self.cache_operations+=1
        return self.installed["version"]

    def check(self,dependencies,at,query_available):
        fields=[x.split(".")[-1] for x in dependencies if x.startswith("profile.")]
        if not fields:return "ALLOW","no_profile_dependency",self.installed["version"],None
        if query_available:
            fresh=self.authority.snapshot(at)
            if fresh["version"]>=self.installed["version"]:
                self.installed=copy.deepcopy(fresh);self.cache=copy.deepcopy(fresh);self.cache_operations+=1
            source=self.installed;why="authority_query"
        else:
            # The highest installed policy cannot be replaced by an older data cache.
            source=self.installed if self.installed["version"]>self.cache["version"] else self.cache
            if any(not source["allowed"][f] for f in fields):
                return "DENY","installed_revocation",source["version"],at-source["issued_ms"]
            age=at-source["issued_ms"]
            if age>=DELTA:return "SAFE_STOP","stale_evidence",source["version"],age
            why="bounded_stale_evidence"
        if any(not source["allowed"][f] for f in fields):return "DENY","profile_revoked",source["version"],at-source["issued_ms"]
        return "ALLOW",why,source["version"],at-source["issued_ms"]


class ResourceGuard:
    @staticmethod
    def check(op,at,expiration,grace,session_id):
        if op=="send":return "ALLOW","not_resource_operation"
        if at<expiration:return "ALLOW","resource_unexpired"
        if grace and session_id=="session-existing-01" and at<15000 and op in {"submit","receipt"}:
            return "ALLOW","preauthorized_completion"
        return "DENY","resource_expired_or_scope"


class AuditVault:
    def __init__(self):
        self.ledger=AuditLedger();self.keys={};self.key_cache={};self.payload_cache={};self.encrypted={};self.error_log=[]

    def append(self,metadata,payload):
        key=Fernet.generate_key();ct=Fernet(key).encrypt(payload.encode())
        self.keys["k1"]=key;self.key_cache["k1"]=key;self.payload_cache["p1"]=payload;self.encrypted["p1"]=ct
        self.ledger.append({**metadata,"payload_digest":hashlib.sha256(payload.encode()).hexdigest()})
        return key,ct

    def recover(self,ct):
        keys=list(self.keys.values())+list(self.key_cache.values())
        for k in keys:
            try:return Fernet(k).decrypt(ct).decode()
            except InvalidToken:pass
        return None

    def erase(self):
        self.keys.clear();self.key_cache.clear();self.payload_cache.clear();self.encrypted.clear()


class Observer:
    def __init__(self):self.events=[];self.effects=[]

    def observe(self,record):
        self.events.append(copy.deepcopy(record))
        if record.get("external_effect"):self.effects.append(copy.deepcopy(record))

    def score(self,case,observed):
        expected=case["expected"]
        if len(expected)!=len(observed):return {"status":"UNKNOWN","reason":"action_count_mismatch"}
        comparisons=[]
        for want,actual in zip(expected,observed):
            comparisons.append({"op":want["op"],"expected":want["result"],"observed":actual["result"],
                                "expected_effect":want["external_effect"],"actual_effect":actual["external_effect"],
                                "matches":want["op"]==actual["op"] and want["result"]==actual["result"] and want["external_effect"]==actual["external_effect"]})
        return {"status":"PASS" if all(x["matches"] for x in comparisons) else "FAIL","comparisons":comparisons}


def run_case(c):
    auth=Authority();profile=ProfileGuard(auth);resources=ResourceGuard();vault=AuditVault();observer=Observer()
    dependencies=c["dependencies"];shape=c["object_shape"];expiration=c.get("expiration_ms",10000);grace=c.get("grace",True)
    data={"profile_f":MARKER_F} if dependencies else {"locked_paper":"SYNTHETIC_LOCKED_PAPER"}
    if shape=="derived":data={"explicit_transform":"copy_value","derived":data}
    object_id="derived-json-01" if shape=="derived" else "raw-json-01"
    data_cache={object_id:copy.deepcopy(data)}
    trace=[];observed=[]
    def record(kind,t,seq,**extra):
        row={"case_id":c["case_id"],"t_ms":t,"seq":seq,"event":kind,"task_id":c["task_id"],
             "session_id":c["session_id"],"plan_version":c["plan_version"],"object_id":object_id,
             "dependency_ids":dependencies,"policy_version":auth.version,**extra}
        trace.append(row);observer.observe(row)
    record("profile_read_and_object_created",0,-2,role="profile",object_shape=shape,content_hash=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest())
    record("initial_authorization",0,-1,role="teacher",observed_policy_version=1)
    for e in c["events"]:
        t=e["t_ms"];seq=e["seq"];kind=e["kind"]
        if kind=="revoke":
            auth.revoke(e["field"]);record("revoke_published",t,seq,role="authority",field=e["field"],published_version=auth.version)
        elif kind=="notify":
            installed=profile.notify(e["policy_version"],t);record("notify_installed",t,seq,role="teacher",received_version=e["policy_version"],installed_version=installed)
        elif kind=="notify_old":
            installed=profile.notify(e["policy_version"],t);record("old_notification_ignored",t,seq,role="teacher",received_version=e["policy_version"],installed_version=installed)
        elif kind=="restore_snapshot":
            profile.cache={"version":1,"allowed":{"f":True,"g":True},"issued_ms":0};profile.cache_operations+=1
            record("stale_cache_restored",t,seq,role="teacher",cache_issued_ms=0)
        elif kind=="old_resource_cache_hit":
            record("old_resource_cache_hit",t,seq,role="resource",cache_version=1)
        elif kind=="preauthorize":record("initial_authorization",t,seq,role="teacher",observed_policy_version=profile.installed["version"])
        elif kind=="action":
            op=e["op"];query=e.get("query_available",True)
            p_result,p_reason,p_version,age=profile.check(dependencies if op=="send" else [],t,query)
            r_result,r_reason=resources.check(op,t,expiration,grace,c["session_id"])
            causes=[x for res,x in [(p_result,p_reason),(r_result,r_reason)] if res!="ALLOW"]
            result="DENY" if "DENY" in (p_result,r_result) else "SAFE_STOP" if "SAFE_STOP" in (p_result,r_result) else "ALLOW"
            for role in (["profile","relay","teacher"] if c["path"]=="relay" else ["profile","teacher"]):
                record("agent_transfer_checked",t,seq,role=role,op=op,result=result,authorization_evidence_version=p_version,causes=causes)
                if result!="ALLOW":break
            record("tool_or_resource_check",t,seq,role="resource",op=op,result=result,resource_reason=r_reason)
            # Atomic final check and externally visible effect: no intervening user event.
            effect=result=="ALLOW"
            actual={"op":op,"result":result,"external_effect":effect,"reason":causes or [p_reason,r_reason],"authorization_evidence_version":p_version,"evidence_age_ms":age}
            observed.append(actual)
            record("atomic_final_check_and_effect",t,seq,role="teacher",**actual,effect_type=("receipt" if op=="submit" else "delivery" if op=="send" else "resource_access") if effect else None)
            vault.append({"event_type":"operation","task_id":c["task_id"],"session_id":c["session_id"],"plan_version":c["plan_version"],"object_id":object_id,"dependency_ids":dependencies,"policy_version":p_version,"op":op,"result":result},json.dumps(data_cache[object_id],ensure_ascii=False))
        else:raise ValueError(kind)
    score=observer.score(c,observed)
    return {"case_id":c["case_id"],"family":c["family"],"scenario":c["scenario"],"path":c["path"],"object_shape":shape,
            "control_of":c["control_of"],"score":score,"observed":observed,"trace":trace,
            "authority_queries":auth.queries,"notifications":profile.notifications,"cache_operations":profile.cache_operations,
            "audit_hash_chain_valid":vault.ledger.verify(),"audit_records":vault.ledger.records,
            "observer_scope":"separate diagnostic trace; not an erasure target",
            "baseline":"B_strong_replay","evidence_level":"single_process_synthetic_event_replay"}


def audit_probes():
    payload=json.dumps({"profile_f":MARKER_F},ensure_ascii=False)
    meta={"event_type":"delivery","task_id":"task-synthetic-01","session_id":"session-existing-01","plan_version":"plan-v1","object_id":"raw-json-01","policy_version":2}
    vault=AuditVault();key,cipher=vault.append(meta,payload)
    a1=vault.recover(cipher)==payload and vault.ledger.verify() and vault.ledger.records[0]["task_id"]==meta["task_id"]
    # Negative control is a deliberately separate fixture; it does not contaminate A2.
    negative=AuditVault();negative_key,negative_cipher=negative.append(meta,payload);negative_copy=bytes(negative_key);negative.erase()
    a3=Fernet(negative_copy).decrypt(negative_cipher).decode()==payload
    vault.erase()
    a2=vault.recover(cipher) is None and vault.ledger.verify() and not any([vault.keys,vault.key_cache,vault.payload_cache,vault.encrypted])
    retained=json.dumps({"ledger":vault.ledger.records,"errors":vault.error_log,"key_cache":vault.key_cache,"payload_cache":vault.payload_cache,"encrypted":vault.encrypted},ensure_ascii=False)
    a4=MARKER_F not in retained and MARKER_G not in retained and all(k in vault.ledger.records[0] for k in ("event_type","object_id","policy_version","task_id"))
    return {"A1":{"passed":a1,"meaning":"read authorized payload before erase and verify chain"},
            "A2":{"passed":a2,"meaning":"recovery fails using keys remaining in declared in-memory vault scope; chain still valid"},
            "A3":{"passed":a3,"meaning":"deliberately retained independent key copy recovers content, negative-control detector exercised"},
            "A4":{"passed":a4,"meaning":"retained enumerated stores do not contain synthetic values; metadata remains linked"},
            "scope":["active in-memory keys","key cache","payload cache","ciphertext cache","audit metadata","error log"],
            "excluded":["observer diagnostics","external recipient","disk remnants","production backups","model memory"],
            "crypto":"cryptography.Fernet","ledger":"cogniguard.governance.audit.AuditLedger",
            "limitation":"Python object deletion does not establish physical memory/disk erasure; A3 deliberately stores separate ciphertext/key in independent fixture"}


def main():
    run=R/"runs"/"replay_v1"
    assert not run.exists(),"NO_OVERWRITE_OR_RETRY"
    manifest=json.loads((R/"FREEZE_MANIFEST.json").read_text(encoding="utf-8"))
    for f in manifest["files"]:assert digest(R/f["file"])==f["sha256"],("FROZEN_FILE_CHANGED",f["file"])
    cases=[json.loads(x) for x in (R/"cases.jsonl").read_text(encoding="utf-8").splitlines()]
    main_cases=[x for x in cases if x["control_of"] is None];controls=[x for x in cases if x["control_of"] is not None]
    run.mkdir(parents=True);start=time.monotonic();records=[];aborted=None
    write(run/"run_started.json",{"baseline":VERSION,"frozen_manifest_sha256":digest(R/"FREEZE_MANIFEST.json"),"limit_seconds":1800,"case_count":len(cases)})
    for idx,c in enumerate(main_cases+controls):
        if time.monotonic()-start>=1800:aborted="TIME_LIMIT";break
        try:result=run_case(c)
        except Exception as ex:
            result={"case_id":c["case_id"],"family":c["family"],"control_of":c["control_of"],"score":{"status":"ERROR","reason":type(ex).__name__},"observed":[],"exception":str(ex)}
        records.append(result)
        with (run/"observations.jsonl").open("a",encoding="utf-8") as f:f.write(json.dumps(result,ensure_ascii=False)+"\n")
        if idx==17 and any(x["score"]["status"]!="PASS" for x in records):
            aborted="MINIMAL_GATE_FAILED";break
    audit=audit_probes();write(run/"audit_probes.json",audit)
    summary={"baseline":VERSION,"duration_seconds":time.monotonic()-start,"main_scheduled":len(main_cases),"controls_scheduled":len(controls),
             "main_executed":sum(x["control_of"] is None for x in records),"controls_executed":sum(x["control_of"] is not None for x in records),
             "passed":sum(x["score"]["status"]=="PASS" for x in records),"failed":sum(x["score"]["status"]=="FAIL" for x in records),
             "unknown_or_error":sum(x["score"]["status"] in {"UNKNOWN","ERROR"} for x in records),"aborted":aborted,
             "audit_pass":sum(v["passed"] for k,v in audit.items() if k in {"A1","A2","A3","A4"}),"audit_total":4,
             "model_calls":0,"gpu":0,"paid_api":0,"single_process_simulation":True}
    write(run/"summary.json",summary);print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=="__main__":main()
