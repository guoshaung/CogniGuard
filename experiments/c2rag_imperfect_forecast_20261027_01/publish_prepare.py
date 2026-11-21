"""Data-only evidence sync; explicitly hash normalized mirrors and raw tar members."""
import base64
import gzip
import io
import json
import tarfile
from experiments.c2rag_imperfect_forecast_20261027_01.common import *


def main():
    deadline();frozen();manifest=read('MANIFEST.sha256.json')
    for p,h in manifest.items():assert sha((OUT/p).read_bytes())==h
    dest=RESULTS_DIR/'c2rag_imperfect_forecast_20261027_github_sync_01';dest.mkdir(exist_ok=False)
    files={p:(OUT/p).read_bytes() for p in manifest if not p.startswith('snapshot/')}
    files['MANIFEST.sha256.json']=(OUT/'MANIFEST.sha256.json').read_bytes()
    files['LICENSE_SOURCES.md']=('OpenStax College Physics2e: https://openstax.org/books/college-physics-2e/pages/7-2-kinetic-energy-and-the-work-energy-theorem\n'
       'Cached CC BY-NC-SA4.0 https://creativecommons.org/licenses/by-nc-sa/4.0/ ; attribution to OpenStax. '
       'Kinetic numerical library follows prior R32/R10 author-adapted asset; T06 uses the prior source-backed work example. '
       'Researcher synthetic demands and simulated authorization only; no real student/private teacher data. '
       'Public textbook laws are not claimed confidential or prohibited for ordinary teaching.\n').encode()
    files['PUBLICATION_SCOPE.json']=encoded({'data_evidence_only':True,'CG_source_and_snapshots_uploaded':False,
       'frozen_code_hashes_local':'freeze.json and source_code_sha256.json',
       'prior_commits':['9bb10e557698fd8ded5aaf3534cc9ffe9c2456b1','6b60c733a8d7a751734521d4c93d23fb58410dad','923b2766d82bb9a7e3b1679174d4e51915257d0a'],
       'includes_all_forecasts_traces_failures_and_repairs':True,'self_contained_code_distribution':False})
    for n,b in files.items():
        t=b.decode('utf8-sig' if False else 'utf-8-sig')
        assert not any(x in t.lower() for x in ['c:\\users\\','github_pat_','ghp_','authorization: bearer']),n
    direct=['README.md','PROTOCOL.md','RESULT.md','per_stream.csv','stratified_results.csv','paired_comparisons.csv',
       'prediction_quality_stratified.csv','decision_cost.csv','CASES.md','CASE_ATTRIBUTION.md','decision.json',
       'independent_verification.json','independent_planning_verification.json','FAILURES_AND_REPAIRS.json',
       'reporting_correction.json','PROTOCOL_IMPLEMENTATION_NOTE.md','REPRODUCE.md','LICENSE_SOURCES.md','PUBLICATION_SCOPE.json']
    mirrors={n:files[n].decode('utf-8-sig').replace('\r\n','\n') for n in direct}
    buffer=io.BytesIO()
    with tarfile.open(fileobj=buffer,mode='w') as tar:
        for n,b in sorted(files.items()):
            entry=tarfile.TarInfo(n);entry.size=len(b);entry.mtime=0;entry.mode=0o644;tar.addfile(entry,io.BytesIO(b))
    archive=gzip.compress(buffer.getvalue(),mtime=0)
    (dest/'evidence.tar.gz').open('xb').write(archive)
    upload={'archive_sha256':sha(archive),'archive_bytes':len(archive),
      'archive_members_raw_sha256':{n:sha(b) for n,b in files.items()},
      'direct_mirror_sha256':{n:sha(t.encode('utf8')) for n,t in mirrors.items()},'all_old_inputs_unchanged':True}
    # Large per-member manifest stays in archive; readable receipt links its exact bytes.
    full=encoded(upload);(dest/'UPLOAD_MANIFEST.json').write_bytes(full)
    mirrors['UPLOAD_MANIFEST.json']=full.decode('utf8')
    (dest/'text_payload.json').write_text(json.dumps(mirrors,ensure_ascii=False),encoding='utf8',newline='')
    (dest/'archive.base64').write_text(base64.b64encode(archive).decode('ascii'),encoding='ascii',newline='')
    print(json.dumps({'archive_bytes':len(archive),'members':len(files),'direct':len(mirrors),'sha256':sha(archive)}))


if __name__=='__main__':main()
