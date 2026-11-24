"""Publish manually evidenced core-fact retention for the local CPU smoke."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import mean

from build import HERE, ROOT, write

DEFAULT = ROOT / "var/results/hsw-st/provenance_20261124/model_smoke_05b"
THERMO = tuple(f"physics-01:f{i}" for i in (1,2,3))
MATH = tuple(f"math-01:f{i}" for i in (1,2,3))
RC = tuple(f"physics-05:f{i}" for i in (1,2,3))
STAT = tuple(f"statistics-04:f{i}" for i in (1,2,3))

# Each decision was checked against the saved text. Physics-05:f3 concerns V_C at
# one time constant. It is misbound to RC after summary even though 6.32 survives.
REVIEW = {
    (1,1):(THERMO,(),(),"All three facts copied byte-for-byte."),
    (1,2):(THERMO,(),(),"900 J, 250 J and 650 J persist with unchanged bulk energy and correct state/process distinction."),
    (1,3):(THERMO,(),(),"Model returned the preceding summary byte-for-byte."),
    (1,4):(THERMO,(),(),"Uses joules in place of J. Conditions and both thermodynamic conclusions persist."),
    (1,5):(THERMO[:1],(),(),"Only heat, work and unchanged bulk-energy conditions survive. The 650 J result and state/process explanation are absent."),
    (2,1):(MATH+RC+STAT,(),(),"All nine core facts copied byte-for-byte."),
    (2,2):(RC[:2]+STAT,(RC[2],),(),"All shelving facts absent. Summary says RC is 6.32 V and calls unrelated evidence combinations of resistors."),
    (2,3):(RC[:2]+STAT,(RC[2],),(),"Retains the prior source omissions and the erroneous statement that RC is about 6.32 V."),
    (2,4):(RC[:2]+STAT,(RC[2],),(),"Model returned the preceding light rewrite with only leading-space differences."),
    (2,5):((RC[1],),(),(RC[0],),"Retains RC≈4 s for the 4 mF circuit, while the 1000-ohm context and initially uncharged condition are absent. Uniform waiting-time facts no longer appear."),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in-dir",type=Path,default=DEFAULT)
    args = parser.parse_args()
    model_dir = args.in_dir
    rows = [json.loads(line) for line in (model_dir/"hops.jsonl").read_text(encoding="utf8").splitlines()]
    assert len(rows) == len(REVIEW)
    by_hop = []
    for row in rows:
        key = (row["chain_id"],row["hop"])
        retained, changed, partial, evidence = REVIEW[key]
        total = 3*len(row["input_source_ids"])
        by_hop.append(dict(chain_id=key[0],hop=key[1],transform=row["transform"],
                           retained_fact_ids=retained, altered_fact_ids=changed, partial_fact_ids=partial,
                           retained_source_ids=sorted({s.split(":f")[0] for s in retained}),
                           fact_fidelity=len(retained)/total,evidence=evidence,
                           input_source_ids=row["input_source_ids"],input_release_ids=row["input_release_ids"],
                           output_sha256=hashlib.sha256(row["text"].encode()).hexdigest(),
                           seconds=row["seconds"],
                           text_quality="MATERIAL_ERROR" if changed else "UNDERSTANDABLE_EXCERPT"))
    write(model_dir/"review.json",by_hop)
    generated = [r for r in rows if r["output_tokens"]]
    write(model_dir/"summary.json",dict(
        chains=2,steps=10,model_calls=len(generated),gpu_hours=0,paid_api_calls=0,
        total_model_call_seconds=sum(row["seconds"] for row in generated),
        mean_model_call_seconds=mean(row["seconds"] for row in generated),
        output_tokens=sum(row["output_tokens"] for row in generated),
        endpoint_fidelity={str(h):[r["fact_fidelity"] for r in by_hop if r["hop"]==h] for h in (1,3,5)},
        relay_quality_counts=dict(Counter(row["text_quality"] for row in by_hop)),
        manual_review="Codex read all ten outputs. Retained means a core fact persists with a correct bound quantity and interpretation. Partial facts are excluded.",
    ))


if __name__=="__main__":
    main()
