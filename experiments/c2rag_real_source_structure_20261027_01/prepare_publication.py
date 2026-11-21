"""Package existing, verified data only. Does not execute or alter the audit."""
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
from core.paths import RESULTS_DIR

SOURCE=RESULTS_DIR/'c2rag_real_source_structure_20261027_01'
DEST=RESULTS_DIR/'c2rag_real_source_structure_20261027_github_sync_01'
REMOTE='CG/diagnostics/2026-10-27-c2rag-real-source-structure-01'


def main():
    manifest=json.loads((SOURCE/'MANIFEST.sha256.json').read_text(encoding='utf8'))
    for path,sha in manifest.items():
        assert hashlib.sha256((SOURCE/path).read_bytes()).hexdigest()==sha,path
    DEST.mkdir(exist_ok=False)
    public=DEST/'payload';public.mkdir()
    excluded=[];included=[]
    for path in manifest:
        normalized=path.replace('\\','/')
        if normalized.startswith(('analysis_code_snapshot/','snapshot/','r32_evidence/')):
            excluded.append({'path':normalized,'reason':'CG source snapshots stay local; R32 evidence already published at its original directory'})
            continue
        data=(SOURCE/path).read_bytes()
        # No source identifiers are student identities; scan for local personal paths/secrets.
        text=data.decode('utf8')
        assert not any(x in text.lower() for x in ['c:\\users\\','/users/guoshuang','ghp_','github_pat_','authorization: bearer'])
        dest=public/normalized;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
        included.append(normalized)
    # Preserve the original local inventory, explicitly distinct from the upload inventory.
    (public/'LOCAL_ORIGINAL_MANIFEST.sha256.json').write_bytes((SOURCE/'MANIFEST.sha256.json').read_bytes())
    (public/'LICENSE_SOURCES.md').write_text('''# Source attribution and simulated permissions

The educational examples originate in OpenStax College Algebra 2e and College Physics 2e. Cached page footers identify CC BY-NC-SA 4.0 (https://creativecommons.org/licenses/by-nc-sa/4.0/). Preserve OpenStax attribution, noncommercial use and share-alike terms for adapted textbook material. No claim that public textbook laws or text are actually confidential or prohibited for teaching.

Canonical source URLs and paragraph locators are in TASKS_AND_SOURCES.md, selected_sources.json and contracts.json. This research adapts worked examples into researcher-written subrequests and numerical representations. The access policy is entirely simulated. No real student records or private teacher documents are present. Author annotations are EXPLORATORY, not independent blind ground truth.

CG source code, model files, credentials, local environment and duplicate R32 archive are not uploaded. This is a data/evidence package, not a standalone runnable code distribution. Frozen source-code hashes identify the local implementations; R32 upstream evidence remains at ../2026-10-27-c2rag-forward-release-r32/.
''',encoding='utf8')
    (public/'PUBLICATION_SCOPE.json').write_text(json.dumps({'remote_directory':REMOTE,'label':'EXPLORATORY',
        'original_results_modified':False,'source_code_uploaded':False,'model_calls':0,'reran_experiments':False,
        'included_original_files':included,'excluded_original_files':excluded,
        'public_document_material':'OpenStax licensed text; attribution in LICENSE_SOURCES.md',
        'known_deviation':'R32 reports read before freeze; binary inputs read after primary run; no retuning',
        'original_manifest':'LOCAL_ORIGINAL_MANIFEST.sha256.json'},ensure_ascii=False,indent=2),encoding='utf8')
    # Stable tar and gzip metadata; archive contains evidence, not code or the archive itself.
    buffer=io.BytesIO()
    with tarfile.open(fileobj=buffer,mode='w',format=tarfile.PAX_FORMAT) as tar:
        for f in sorted(public.rglob('*')):
            if not f.is_file():continue
            data=f.read_bytes();entry=tarfile.TarInfo(f.relative_to(public).as_posix())
            entry.size=len(data);entry.mtime=0;entry.mode=0o644;tar.addfile(entry,io.BytesIO(data))
    archive=gzip.compress(buffer.getvalue(),mtime=0)
    (public/'evidence.tar.gz').write_bytes(archive)
    readable=['README.md','PROTOCOL.md','STRUCTURE_AUDIT.md','TASKS_AND_SOURCES.md','MINIMAL_UNSAFE.md',
              'NEXT_STEPS.md','decision.json','summary.json','FAILURES_AND_LIMITATIONS.json','R32_READ_AUDIT.md',
              'LICENSE_SOURCES.md','PUBLICATION_SCOPE.json','reporting_correction.json']
    hashes={f.relative_to(public).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(public.rglob('*')) if f.is_file()}
    upload_manifest={'sha256':hashes,'archive_members':sorted(n for n in hashes if n!='evidence.tar.gz'),
                     'direct_readable_files':readable,'archive_sha256':hashes['evidence.tar.gz'],
                     'original_local_manifest_preserved':True}
    (public/'UPLOAD_MANIFEST.json').write_text(json.dumps(upload_manifest,ensure_ascii=False,indent=2),encoding='utf8')
    payload={name:(public/name).read_text(encoding='utf8') for name in readable+['UPLOAD_MANIFEST.json']}
    (DEST/'text_payload.json').write_text(json.dumps(payload,ensure_ascii=False),encoding='utf8')
    (DEST/'archive.base64').write_text(base64.b64encode(archive).decode('ascii'),encoding='ascii')
    print(json.dumps({'directory':REMOTE,'archive_bytes':len(archive),'evidence_members':len(hashes)-1,
                      'readable_files':len(payload),'archive_sha256':hashes['evidence.tar.gz']},ensure_ascii=False))


if __name__=='__main__':main()
