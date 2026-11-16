"""Replay EVAL-03's CPU render/OCR path with the frozen T6 registry."""
import argparse
import concurrent.futures
import json
import os
import sys

from t6_sources import HERE, OUT, ROOT, load, sha, write

LEGACY=ROOT/"experiments/hsw_certinsert_eval03_lite_20261112"
sys.path.insert(0,str(LEGACY))
import ocr_parallel as old

FINAL=OUT/"ocr"
os.environ["PADDLE_PDX_CACHE_HOME"]=str(FINAL/"pdxcache")


def worker(tasks):
    old.O=FINAL
    engine,font=old.load_engine()
    folder=FINAL/"images"
    for task in tasks:
        rid=task["record_id"]
        target=FINAL/"records"/(rid+".json")
        if target.exists():
            continue
        raw=(ROOT/task["path"]).read_bytes()
        assert sha(raw)==task["sha256"]
        row={"record_id":rid,"input_sha256":task["sha256"]}
        try:
            text,pages=old.recognize(engine,font,{"id":rid,"text":raw.decode()},folder)
            (FINAL/"texts"/(rid+".txt")).write_bytes(text.encode())
            row.update(status="COMPLETED" if text.strip() else "EMPTY",output_sha256=sha(text.encode()),
                       pages=len(pages))
        except (OSError,ValueError,RuntimeError,KeyError,AssertionError) as ex:
            row.update(status="FAILED",reason=type(ex).__name__)
        old.atomic(target,row)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--primary",action="store_true")
    args=p.parse_args()
    registry=OUT/("score_registry_primary.json" if args.primary else "score_registry.json")
    freeze=load(HERE/("T6_PRIMARY_VARIANT_FREEZE.json" if args.primary else "T6_VARIANT_FREEZE.json"))
    assert sha(registry.read_bytes())==freeze["registry_sha256"]
    chosen=load(registry)["items"]
    for endpoint in ("records","texts","images"):
        (FINAL/endpoint).mkdir(exist_ok=True,parents=True)
    remaining=[r for r in chosen if not (FINAL/"records"/(r["record_id"]+".json")).exists()]
    if remaining:
        with concurrent.futures.ProcessPoolExecutor(max_workers=2) as executor:
            list(executor.map(worker,[remaining[::2],remaining[1::2]]))
    records=[load(FINAL/"records"/(r["record_id"]+".json")) for r in chosen]
    write(FINAL/("PRIMARY_RESULT.json" if args.primary else "RESULT.json"),{"planned":len(chosen),"rows":records})


if __name__=="__main__":
    main()
