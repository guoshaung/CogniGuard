"""Read-only artifact/hash/countermodel verification; never executes methods."""
import hashlib
import json
from core.paths import PROJECT_ROOT
from experiments.c2rag_real_source_structure_20261027_01.analyze import OUT
from experiments.c2rag_real_source_structure_20261027_01.report import verify_countermodels


def main():
    def read(n):return json.loads((OUT/n).read_text(encoding='utf8'))
    manifest=read('MANIFEST.sha256.json')
    for rel,expected in manifest.items():
        assert hashlib.sha256((OUT/rel).read_bytes()).hexdigest()==expected,rel
    for rel,expected in read('freeze.json')['sha256'].items():
        assert hashlib.sha256((PROJECT_ROOT/rel).read_bytes()).hexdigest()==expected,rel
    for rel,expected in read('source_hashes_before.json').items():
        assert hashlib.sha256((PROJECT_ROOT/rel).read_bytes()).hexdigest()==expected,rel
    receipt=read('r32_evidence/evidence_receipt.json')
    assert hashlib.sha256((OUT/'r32_evidence/evidence.tar.gz').read_bytes()).hexdigest()==receipt['archive_sha256']
    t=read('contracts.json');m=read('math_certificates.json')['results']
    checks=verify_countermodels(t,m)
    summary=read('summary.json')
    assert len(t)==len(summary)==12
    assert sum(x['legal_schedules'] for x in summary)==len(read('release_combinations.json'))==236
    assert all(not x['horn_math_disagreements'] for x in summary)
    assert all(x['engine_reference_disagreements']==0 for x in summary)
    print(json.dumps({'files_hash_verified':len(manifest),'frozen_inputs_and_source_unchanged':True,
                      'r32_archive_remote_receipt_matches':True,**checks},ensure_ascii=False))


if __name__=='__main__':main()
