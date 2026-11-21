"""Check audit encryption against an actual synthetic P1 file receipt."""
import importlib.util
import json
from pathlib import Path

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OLD = ROOT / "experiments/cg_dynamic_problem_validation_20261105_03"
spec = importlib.util.spec_from_file_location("rec", ROOT / "experiments/cg_base_acceptance_20261105_01/replay_with_receiver.py")
rec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rec)


def main():
    out = HERE / "runs/v1"
    out.mkdir(parents=True, exist_ok=False)
    cases = [json.loads(line) for line in (OLD / "cases.jsonl").read_text(encoding="utf-8").splitlines()]
    case = next(c for c in cases if c["case_id"] == "P1")
    receipt_path = out / "P1_receipt.jsonl"
    decisions = rec.execute(case, rec.Receiver(receipt_path))
    observed = rec.observe(case, decisions, receipt_path)
    receipts = [json.loads(line) for line in receipt_path.read_text(encoding="utf-8").splitlines()]
    assert observed["status"] == "PASS" and len(receipts) == 1
    value = "SYNTHETIC_F_7B91"
    payload = json.dumps({"profile_f":value})
    metadata = {"event_type":"delivery", "task_id":case["task_id"], "session_id":case["session_id"],
                "plan_version":case["plan_version"], "object_id":"synthetic-profile-f",
                "policy_version":"synthetic-v1", "case_id":receipts[0]["case_id"]}
    vault = rec.old.AuditVault()
    vault.append(metadata, payload)
    ciphertext = vault.encrypted["p1"]
    a1 = vault.recover(ciphertext) == payload and vault.ledger.verify() and vault.ledger.records[0]["case_id"] == receipts[0]["case_id"]
    control = rec.old.AuditVault()
    k, c = control.append(metadata, payload)
    held_key = bytes(k)
    del k
    control.erase()
    a3 = Fernet(held_key).decrypt(c).decode() == payload
    vault.erase()
    a2 = vault.recover(ciphertext) is None and vault.ledger.verify() and not any((vault.keys, vault.key_cache, vault.payload_cache, vault.encrypted))
    retained = json.dumps({"records":vault.ledger.records, "errors":vault.error_log,
                           "keys":vault.keys, "key_cache":vault.key_cache,
                           "payload_cache":vault.payload_cache, "ciphertexts":vault.encrypted})
    a4 = value not in retained and all(k in vault.ledger.records[0] for k in ("task_id","object_id","policy_version"))
    report = {"A1":a1,"A2":a2,"A3":a3,"A4":a4,
              "receiver":receipt_path.name,"scope":"in-process vault stores and audit metadata only",
              "excluded":["external recipient copies","disk remnants","backups","model memory"]}
    (out / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
