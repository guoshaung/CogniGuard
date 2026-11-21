"""Generate the complete frozen case schedule and expected outcomes before replay."""
import hashlib
import itertools
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
R=Path(__file__).resolve().parent
OUT=R/"cases.jsonl"


def case(cid, family, scenario, events, expected, **kwargs):
    return {"case_id":cid,"family":family,"scenario":scenario,"task_id":"task-synthetic-01",
            "session_id":"session-existing-01","plan_version":"plan-v1","path":"direct",
            "object_shape":"raw","dependencies":["profile.f"],"events":events,
            "expected":expected,"control_of":None,"policy_version":"v1.0",**kwargs}


def rev(t=10, field="f", seq=1, notice=10, query=True, old_after=False):
    events=[{"t_ms":t,"seq":seq,"kind":"revoke","field":field,"policy_version":2},
            {"t_ms":notice,"seq":30,"kind":"notify","field":field,"policy_version":2}]
    if old_after:
        events.append({"t_ms":notice+1,"seq":30,"kind":"notify_old","field":field,"policy_version":1})
    return events


def act(t=20, op="send", seq=50, query=True):
    return {"t_ms":t,"seq":seq,"kind":"action","op":op,"query_available":query}


def expected(result, op="send"):
    return {"op":op,"result":result,"external_effect":result=="ALLOW"}


def main():
    assert not OUT.exists() and not (R/"FREEZE_MANIFEST.json").exists(), "NO_OVERWRITE"
    cases=[]
    def add(cid,f,scenario,events,res,**kwargs):
        cases.append(case(cid,f,scenario,events,[expected(x,y) for x,y in res],**kwargs))
    add("P1","profile","no revocation",[act()],[('ALLOW','send')])
    add("P2","profile","read then revoke before send",rev()+[act()],[('DENY','send')])
    add("P3","profile","initial authorization then revoke before atomic send",[{"t_ms":5,"seq":1,"kind":"preauthorize"}]+rev()+[act()],[('DENY','send')])
    add("P4","profile","send before revoke; later send",[act(5)]+rev()+[act(20)],[('ALLOW','send'),('DENY','send')])
    add("P5","profile","revoke unrelated g",rev(field="g")+[act()],[('ALLOW','send')])
    add("P6","profile","derived and cached object",rev()+[act()],[('DENY','send')],object_shape="derived")
    add("E1","exam","valid normal read",[act(5000,"read_locked")],[('ALLOW','read_locked')],dependencies=[])
    add("E2","exam","authorized existing session completion",[act(12000,"submit")],[('ALLOW','submit')],dependencies=[])
    add("E3","exam","new session at expiration",[act(10000,"new_session")],[('DENY','new_session')],dependencies=[])
    add("E4","exam","new material during completion window",[act(12000,"read_new")],[('DENY','read_new')],dependencies=[])
    add("E5","exam","submission at hard deadline",[act(15000,"submit")],[('DENY','submit')],dependencies=[])
    add("E6","exam","no preauthorized completion",[act(12000,"submit")],[('DENY','submit')],dependencies=[],grace=False)
    add("V1","version","instant notification",rev(t=0,notice=0)+[act(1)],[('DENY','send')])
    add("V2","version","stale under bound and authority offline",rev(t=0,notice=100)+[act(49,query=False)],[('ALLOW','send')])
    add("V3","version","stale exactly at bound and authority offline",rev(t=0,notice=100)+[act(50,query=False)],[('SAFE_STOP','send')])
    add("V4","version","new policy installed but data cache old",rev(t=0,notice=0)+[act(1)],[('DENY','send')])
    add("V5","version","old allow notification arrives after revocation",rev(t=0,notice=0,old_after=True)+[act(2)],[('DENY','send')])
    add("V6","version","restore old cache and no fresh query",[{"t_ms":0,"seq":1,"kind":"restore_snapshot"}]+rev(t=0,seq=2,notice=200)+[act(100,query=False)],[('SAFE_STOP','send')])
    assert len(cases)==18
    for path, shape in itertools.product(("direct","relay"),("raw","derived")):
        for j,(rt,rs) in enumerate([(1100,1),(1001,1),(1000,11),(1000,9),(999,1),(900,1)]):
            cid=f"XP-{path}-{shape}-{j+1}"
            add(cid,"profile","timing permutation",rev(t=rt,seq=rs,notice=rt)+[act(1000,seq=10)],[("ALLOW" if j<3 else "DENY","send")],path=path,object_shape=shape)
        for j,t in enumerate([9999,10000,10001,14999,15000,15001]):
            add(f"XE-{path}-{shape}-{j+1}","exam","T/D boundary",[act(t,"submit")],[("ALLOW" if j<4 else "DENY","submit")],path=path,object_shape=shape,dependencies=[])
        for j,t in enumerate([0,49,50,51,99,101]):
            add(f"XV-{path}-{shape}-{j+1}","version","notification delayed 2Δ; authority online",rev(t=0,seq=1,notice=100)+[act(t,seq=50,query=True)],[('DENY','send')],path=path,object_shape=shape)
    for family in ("cross_profile_exam","cross_profile_delay","cross_exam_cache"):
        for ordering in (0,1):
            if family=="cross_profile_exam":
                events=rev(t=10000-ordering,notice=10000-ordering)+[act(12000,"send"),act(12001,"submit")]
                res=[('DENY','send'),('ALLOW','submit')]
            elif family=="cross_profile_delay":
                events=rev(t=4900-ordering,notice=5100)+[act(5000,"send"),act(5001,"read_locked")]
                res=[('DENY','send'),('ALLOW','read_locked')]
            else:
                events=[{"t_ms":10000-ordering,"seq":1,"kind":"old_resource_cache_hit"},act(12000,"read_new"),act(12001,"submit")]
                res=[('DENY','read_new'),('ALLOW','submit')]
            add(f"XC-{family}-{ordering+1}","cross",family,events,res,path="relay",object_shape="derived")
    assert len(cases)==96
    # Paired control changes a single declared event/fault; no resampling.
    controls=[]
    for main in cases:
        events=main["events"]
        if main["family"]=="exam" or main["scenario"]=="cross_exam_cache":
            c={**main,"case_id":"CTRL-"+main["case_id"],"control_of":main["case_id"],"expiration_ms":100000,
               "expected":[expected("ALLOW",x["op"]) for x in main["expected"]],"control_change":"expiration moved beyond observation"}
        elif any(e["kind"]=="revoke" for e in events):
            c={**main,"case_id":"CTRL-"+main["case_id"],"control_of":main["case_id"],
               "events":[e for e in events if e["kind"] not in {"revoke","notify","notify_old"}],
               "expected":[expected("ALLOW",x["op"]) for x in main["expected"]],"control_change":"revoke and its notification removed"}
            # With no event, unavailable authority may still use the original evidence only inside Δ.
            for a in c["events"]:
                if a["kind"]=="action" and not a.get("query_available",True) and a["t_ms"]>=50:
                    c["expected"]=[expected("SAFE_STOP",x["op"]) for x in c["expected"]]
        else:
            continue
        controls.append(c)
    assert len(controls)<=96
    allcases=cases+controls
    for c in allcases:c["events"]=sorted(c["events"],key=lambda e:(e["t_ms"],e["seq"]))
    OUT.write_text("".join(json.dumps(c,ensure_ascii=False,sort_keys=True)+"\n" for c in allcases),encoding="utf-8")
    paths=[R/"SPEC.md",R/"BASELINE.md",R/"README.md",R/"freeze_cases.py",R/"run_replay.py",OUT]
    hashes=[{"file":p.name,"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"bytes":p.stat().st_size} for p in paths]
    (R/"FREEZE_MANIFEST.json").write_text(json.dumps({"version":"v1.0","main":96,"minimal":18,"expansion":72,"cross":6,"paired_controls":len(controls),"files":hashes},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"main":96,"minimal":18,"expansion":72,"cross":6,"controls":len(controls),"freeze_manifest_sha256":hashlib.sha256((R/"FREEZE_MANIFEST.json").read_bytes()).hexdigest()}))


if __name__=="__main__":main()
