"""Publish data-only existing evidence, with explicit raw/archive vs text hashes."""
import base64
import gzip
import io
import json
import tarfile
from experiments.c2rag_cross_question_history_20261027_02.common import OUT,PROJECT_ROOT,RESULTS_DIR,SOURCE,sha


def main():
    dest=RESULTS_DIR/'c2rag_cross_question_history_20261027_github_sync_02';dest.mkdir(exist_ok=False)
    files={}
    for f in OUT.rglob('*'):
        if not f.is_file():continue
        n=f.relative_to(OUT).as_posix()
        if n.startswith(('snapshot/','prior_evidence/')) or n=='prior_fetch_payload.json':continue
        files[n]=f.read_bytes()
    files['failed_run01/FAILURE.json']=(RESULTS_DIR/'c2rag_cross_question_history_20261027_01/FAILURE.json').read_bytes()
    files['failed_run01/code_manifest.json']=json.dumps({str(f.relative_to(PROJECT_ROOT)):sha(f.read_bytes()) for f in (PROJECT_ROOT/'experiments/c2rag_cross_question_history_20261027_01').iterdir() if f.is_file()},indent=2).encode()
    files['failed_publication01/FAILURE.json']=(RESULTS_DIR/'c2rag_cross_question_history_20261027_github_sync_01/FAILURE.json').read_bytes()
    files['LICENSE_SOURCES.md']=('OpenStax College Physics 2e, section7.2, Figure7.4 and Examples7.2–7.5. '
       'https://openstax.org/books/college-physics-2e/pages/7-2-kinetic-energy-and-the-work-energy-theorem\n\n'
       'Cached source license: CC BY-NC-SA4.0 https://creativecommons.org/licenses/by-nc-sa/4.0/ . '
       'Attribution to OpenStax retained; researcher adaptations and simulated authorization explicitly identified. '
       'Not a claim of real textbook secrecy. Public formulas remain public.\n').encode()
    files['PUBLICATION_SCOPE.json']=json.dumps({'scope':'complete data and diagnostic evidence, including failed preparation01',
       'source_code_uploaded':False,'code_hashes_local':'freeze.json and code_manifest.json',
       'model_or_gpu_calls':0,'reran_experiments_for_publication':False,
       'duplicate_upstream_evidence_omitted':'prior_evidence from pinned6b60c73; local bytes verified',
       'text_mirrors':'normalized LF; direct_mirror_sha256 explicitly differs from archive raw if line endings differ',
       'archive':'original evidence bytes unchanged; archive_members_raw_sha256 checks contents'},ensure_ascii=False,indent=2).encode()
    # Check no personal path or credential patterns in any outgoing text.
    for n,b in files.items():
        text=b.decode('utf8')
        assert not any(x in text.lower() for x in ['c:\\users\\','github_pat_','ghp_','authorization: bearer']),n
    direct=['README.md','PROTOCOL.md','INSTANCE_MAPPING.md','RESULT.md','method_summary.csv',
            'CROSS_QUESTION_WITNESSES.md','decision.json','FAILURES_AND_LIMITATIONS.json',
            'offline_references.json','independent_verification.json','LICENSE_SOURCES.md','PUBLICATION_SCOPE.json']
    # Direct mirrors have deliberately normalized newlines; hash actual outgoing bytes.
    mirrors={n:files[n].decode('utf-8-sig' if n.endswith('.csv') else 'utf8').replace('\r\n','\n') for n in direct}
    buffer=io.BytesIO()
    with tarfile.open(fileobj=buffer,mode='w') as tar:
        for n,b in sorted(files.items()):
            t=tarfile.TarInfo(n);t.size=len(b);t.mtime=0;t.mode=0o644;tar.addfile(t,io.BytesIO(b))
    archive=gzip.compress(buffer.getvalue(),mtime=0)
    (dest/'evidence.tar.gz').open('xb').write(archive)
    manifest={'archive_sha256':sha(archive),'archive_bytes':len(archive),
              'archive_members_raw_sha256':{n:sha(b) for n,b in sorted(files.items())},
              'direct_mirror_sha256':{n:sha(s.encode('utf8')) for n,s in mirrors.items()},
              'local_source_files_unchanged':True,'pinned_upstream':'6b60c733a8d7a751734521d4c93d23fb58410dad'}
    mirrors['UPLOAD_MANIFEST.json']=json.dumps(manifest,ensure_ascii=False,indent=2)
    (dest/'text_payload.json').write_text(json.dumps(mirrors,ensure_ascii=False),encoding='utf8',newline='')
    (dest/'archive.base64').write_text(base64.b64encode(archive).decode('ascii'),encoding='ascii',newline='')
    print(json.dumps({'archive_bytes':len(archive),'members':len(files),'direct_files':len(mirrors),'sha256':sha(archive)}))


if __name__=='__main__':main()
