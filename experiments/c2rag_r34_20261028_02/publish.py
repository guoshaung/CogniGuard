"""Sanitized append-only research evidence package; no production source or credentials."""
import base64
import gzip
import io
import json
import re
import tarfile
from experiments.c2rag_r34_20261028_02.common import *

def main():
    frozen()
    for n,h in read('MANIFEST.sha256.json').items():assert sha((OUT/n).read_bytes())==h,n
    dest=RESULTS_DIR/'c2rag_r34_20261028_github_sync_02';dest.mkdir(exist_ok=False)
    files={p.relative_to(OUT).as_posix():p.read_bytes() for p in OUT.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    failed=RESULTS_DIR/'c2rag_r34_20261028_01'
    for p in failed.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:files['failed_run01/'+p.relative_to(failed).as_posix()]=p.read_bytes()
    files['publication_attempt01/FAILURE.json']=(RESULTS_DIR/'c2rag_r34_20261028_github_sync_01/FAILURE.json').read_bytes()
    for dirname in ['c2rag_r34_20261028_01','c2rag_r34_20261028_02']:
        src=PROJECT_ROOT/'experiments'/dirname
        for p in src.iterdir():
            if p.is_file() and p.suffix in ['.py','.md']:
                files['isolated_experiment_code/experiments/'+dirname+'/'+p.name]=p.read_bytes()
    scope={'includes_all_frozen_inputs':True,'includes_all_traces_forecasts_opt_and_independent_certificates':True,
        'includes_failed_run01_and_original_frozen_research_baseline':True,'includes_isolated_research_scripts':True,
        'production_controller_or_model_source_included':False,'raw_large_source_HTML_included':False,
        'source_material':'license, excerpts, exact cached locators/hash and public URLs in sources.json',
        'synthetic_parameters_and_golds_sanitized':True,'requires_existing_CogniGuard_checkout_for_core_paths':True,
        'generated_interpreter_pycache_excluded':True}
    files['PUBLICATION_SCOPE.json']=json.dumps(scope,ensure_ascii=False,indent=2).encode('utf8')
    for name,b in files.items():
        text=b.decode('utf-8-sig')
        assert not re.search(r'(?:ghp_|github_pat_)[A-Za-z0-9_]{25,}',text),name
        assert 'c:\\users\\' not in text.lower(),name
    buffer=io.BytesIO()
    with tarfile.open(fileobj=buffer,mode='w') as tar:
        for name,b in sorted(files.items()):
            info=tarfile.TarInfo(name);info.size=len(b);info.mtime=0;info.mode=0o644;tar.addfile(info,io.BytesIO(b))
    archive=gzip.compress(buffer.getvalue(),mtime=0)
    (dest/'evidence.tar.gz').write_bytes(archive)
    direct=['PROTOCOL.md','DATASET_AUDIT.md','METHOD_COMPARISON.md','RESULT.md','FAILURES.md','NOVELTY_GAP.md','decision.json',
        'GLOBAL_UNION_REDUCTION.md','MINIMAL_WITNESSES.md','GROUP_MEETING.md','REPRODUCE.md','HISTORY_READ_AUDIT.md','LICENSE_SOURCES.md',
        'method_summary.csv','asset_method_summary.csv','split_method_summary.csv','oracle_gaps.csv','paired_comparisons.csv',
        'prediction_quality_summary.csv','FINAL_QA.json','independent_verification.json','freeze.json','ENGINEERING_REPAIR.json',
        'REPAIR_DATA_IDENTITY.json','REPORTING_CORRECTION.json','PUBLIC_SOURCE_POLICY_BOUNDARY.json','PUBLICATION_SCOPE.json']
    mirrors={n:files[n].decode('utf-8-sig').replace('\r\n','\n') for n in direct}
    upload={'archive_sha256':sha(archive),'archive_bytes':len(archive),'archive_members_raw_sha256':{n:sha(b) for n,b in files.items()},
        'direct_mirror_sha256':{n:sha(t.encode('utf8')) for n,t in mirrors.items()},
        'archive_git_blob_sha1':__import__('hashlib').sha1(b'blob '+str(len(archive)).encode()+b'\0'+archive).hexdigest(),
        'history_untouched':True,'code_distribution_scope':scope}
    text=json.dumps(upload,ensure_ascii=False,indent=2);(dest/'UPLOAD_MANIFEST.json').write_text(text,encoding='utf8',newline='\n');mirrors['UPLOAD_MANIFEST.json']=text
    # Small transport parts permit exact pinned Contents API readback even >1MiB.
    parts=[]
    for offset in range(0,len(archive),750000):
        b=archive[offset:offset+750000];name=f'evidence.tar.gz.part{len(parts):02d}';(dest/name).write_bytes(b)
        parts.append({'name':name,'bytes':len(b),'sha256':sha(b)})
    transport={'parts':parts,'concatenation_order':'listed order','archive_bytes':len(archive),'archive_sha256':sha(archive)}
    mirrors['TRANSPORT_PARTS.json']=json.dumps(transport,indent=2)
    (dest/'TRANSPORT_PARTS.json').write_text(mirrors['TRANSPORT_PARTS.json'],encoding='utf8')
    (dest/'text_payload.json').write_text(json.dumps(mirrors,ensure_ascii=False),encoding='utf8',newline='\n')
    (dest/'archive.base64').write_text(base64.b64encode(archive).decode('ascii'),encoding='ascii')
    print(json.dumps({'archive_bytes':len(archive),'sha256':sha(archive),'files':len(files),'direct_mirrors':len(mirrors),'parts':parts}))

if __name__=='__main__':main()
