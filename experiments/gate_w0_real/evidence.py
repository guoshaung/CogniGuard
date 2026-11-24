"""Export detector results into Claude's pe-0.1 interface."""
import argparse
import hashlib
from pathlib import Path
import sys

from evaluate import HERE, corpora, jsonl, norm, read, rows


def pe(artifact, holder, method, sources, issuances, units, scores, conflict, *, policy=0, observed=0):
    status = "content_verified" if units else "inconclusive"
    fingerprint = hashlib.sha256(f"{artifact}|{holder}|{method}".encode()).hexdigest()
    return dict(
        schema_version="pe-0.1", evidence_id=fingerprint, artifact_id=artifact,
        holder_principal_id=holder, evidence_type={
            "kbpw":"knowledge_bound_watermark", "joint":"watermark_knowledge",
            "minhash":"fingerprint",
        }.get(method,"retrieval"), candidate_issuance_ids=sorted(issuances),
        matched_knowledge_units=sorted(units), confidence=1.0 if units else 0.0,
        verification_status=status, trusted_event_id=None, event_sender_principal_id=None,
        policy_version=policy, model_and_detector_version=f"w0-real-065bb82/{method}",
        observed_at=observed, extra=dict(evidence_origin="text_inference",
            candidate_source_ids=sorted(sources), match_scores=scores, score_semantics="method_native",
            conflict_status="carrier_content_mismatch" if conflict else "none",
            resolution="UNKNOWN" if not units else "content_match",
            issuance_resolution="UNKNOWN" if not issuances else "candidate_only",
            holder_binding="caller_supplied_simulation_id"))


def export(folder):
    catalog,_ = corpora()
    facts = {s["source_id"]:s["units"] for s in catalog}
    public = {r["artifact_id"]:r["text"] for r in rows(folder/"public_fragments.jsonl")}
    result=[]
    for prediction in rows(folder/"predictions.jsonl"):
        aid = prediction["artifact_id"]
        text = " "+norm(public[aid])+" "
        # Similarity selects candidates. The holdings update requires a complete,
        # exact normalized statement from the authorized reference catalog.
        units = []
        for sid in prediction["sources"]:
            for f in facts[sid]:
                if any(" "+norm(f[key])+" " in text for key in ("text","light","strong")):
                    if prediction["method"] not in ("kbpw","joint") or f["fact_id"] in prediction["facts"]:
                        units.append((sid,f["fact_id"].rsplit(":",1)[-1]))
        result.append(pe(aid,"fragment-pilot-holder",prediction["method"],prediction["sources"],
            prediction["candidate_issuance_ids"],units,
            {"source":prediction["scores"],"issuance":prediction["release_scores"]},prediction["conflict"]))
    jsonl(folder/"provenance_evidence.jsonl",result)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--contract",type=Path,required=True)
    p.add_argument("--folder",type=Path,default=HERE/"results")
    a=p.parse_args()
    sys.path.insert(0,str(a.contract.resolve()))
    from cogniguard.governance.provenance_evidence import ProvenanceEvidence, trusted_event_credits
    export(a.folder)
    records=[ProvenanceEvidence.from_dict(r) for r in rows(a.folder/"provenance_evidence.jsonl")]
    assert not trusted_event_credits(records)
    assert all(not set(r.extra)&{"truth","gold","scoring_cases"} for r in records)
    print("Validated evidence:",len(records))


if __name__=="__main__":
    main()
