"""Complete synthetic evidence and isolated research code, no historical raw/private data."""
import base64
import gzip
import io
import json
import re
import tarfile
from experiments.c2rag_r35_20261029_01.common import *

def main():
    frozen()
    for n,h in read('FINAL_MANIFEST.sha256.json').items():assert sha((OUT/n).read_bytes())==h,n
    dest=RESULTS_DIR/'c2rag_r35_20261029_github_sync_02';dest.mkdir(exist_ok=False)
    files={p.relative_to(OUT).as_posix():p.read_bytes() for p in OUT.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    for p in SOURCE.iterdir():
        if p.is_file() and p.suffix in ['.py','.md']:files['isolated_experiment_code/'+p.name]=p.read_bytes()
    files['publication_attempt01/FAILURE.json']=(RESULTS_DIR/'c2rag_r35_20261029_github_sync_01/FAILURE.json').read_bytes()
    scope={'SYNTHETIC':True,'all_new_raw_replays_and_prefix_forecasts_and_solver_certificates_included':True,
        'isolated_new_research_code_and_frozen_research_baseline_included':True,'historical_stage1_raw_records_republished':False,
        'historical_record_hashes_and_sanitized_counts_only':True,'production_code_included':False,'models_credentials_or_personal_data':False,
        'external_reference_urls_in_THEORY':True,'CG_checkout_required_for_core_paths':True,'generated_pycache_excluded':True}
    files['PUBLICATION_SCOPE.json']=enc(scope)
    for n,b in files.items():
        t=b.decode('utf-8-sig')
        assert not re.search(r'(?:ghp_|github_pat_)[A-Za-z0-9_]{25,}',t),n
        banned=['c:'+separator+'users'+separator for separator in [chr(47),chr(92)]]
        assert not any(x in t.lower() for x in banned),n
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode='w') as tar:
        for n,b in sorted(files.items()):
            info=tarfile.TarInfo(n);info.size=len(b);info.mtime=0;info.mode=0o644;tar.addfile(info,io.BytesIO(b))
    archive=gzip.compress(buf.getvalue(),mtime=0);(dest/'evidence.tar.gz').write_bytes(archive)
    direct=['PROTOCOL.md','HISTORY_AUDIT.md','METHOD_MATRIX.md','RESULT.md','THEORY_AND_LIMITS.md','FAILURES_AND_LIMITATIONS.md',
        'NOVELTY_AND_DECISION.md','GROUP_MEETING.md','REPRODUCE.md','decision.json','complete_results.csv','information_bounds.csv',
        'paired_differences.csv','prediction_sensitivity.csv','forecast_distribution_quality.csv','decision_latency.csv','independent_verification.json',
        'independent_distribution_score_check.json','stage1_raw_record_audit.json','test_receipt.json','FINAL_QA.json','freeze.json','code_version.json','PUBLICATION_SCOPE.json']
    mirrors={n:files[n].decode('utf-8-sig').replace('\r\n','\n') for n in direct}
    upload={'archive_sha256':sha(archive),'archive_bytes':len(archive),'archive_members_raw_sha256':{n:sha(b) for n,b in files.items()},
        'direct_mirror_sha256':{n:sha(t.encode('utf8')) for n,t in mirrors.items()},'all_historical_files_unchanged':True,
        'archive_git_blob_sha1':hashlib.sha1(b'blob '+str(len(archive)).encode()+b'\0'+archive).hexdigest(),'publication_scope':scope}
    mirrors['UPLOAD_MANIFEST.json']=json.dumps(upload,ensure_ascii=False,indent=2)
    (dest/'UPLOAD_MANIFEST.json').write_text(mirrors['UPLOAD_MANIFEST.json'],encoding='utf8')
    parts=[]
    for offset in range(0,len(archive),750000):
        b=archive[offset:offset+750000];n=f'evidence.tar.gz.part{len(parts):02d}';(dest/n).write_bytes(b)
        parts.append({'name':n,'bytes':len(b),'sha256':sha(b)})
    mirrors['TRANSPORT_PARTS.json']=json.dumps({'parts':parts,'archive_sha256':sha(archive),'archive_bytes':len(archive),'concatenate_in_listed_order':True},indent=2)
    (dest/'text_payload.json').write_text(json.dumps(mirrors,ensure_ascii=False),encoding='utf8')
    (dest/'archive.base64').write_text(base64.b64encode(archive).decode('ascii'),encoding='ascii')
    print(json.dumps({'files':len(files),'archive_bytes':len(archive),'archive_base64_chars':len(base64.b64encode(archive)),
        'sha256':sha(archive),'parts':len(parts),'direct':len(mirrors)}))

if __name__=='__main__':main()
