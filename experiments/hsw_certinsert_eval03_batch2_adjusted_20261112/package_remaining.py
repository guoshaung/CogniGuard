"""Explicit safe publication allowlist; reviewer mapping and keys stay local."""
from common_adjusted import *
import shutil

def main():
    stage=sys.argv[1];dst=O/('publication_'+stage);dst.mkdir(exist_ok=False)
    def copy(p,rel):
        q=dst/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
    delivery={'P3-P4':'delivery_P3_P4','P1-expanded':'delivery_P1_expanded'}[stage]
    for p in (O/delivery).iterdir():
        if p.is_file():copy(p,p.name)
    roots=['P3','T5_prepared','T5_insertion','T5_ocr','T5_evaluation','P4'] if stage=='P3-P4' else ['P1_expanded','data_expanded','P1_unmodified_controls']
    image_records=[]
    for name in roots:
        for p in sorted((O/name).rglob('*')):
            if not p.is_file():continue
            assert not any(s in p.parts for s in ['restricted','private_review_mapping'])
            if p.suffix.lower() in ['.png','.jpg','.jpeg']:
                image_records.append(dict(path=p.relative_to(O).as_posix(),sha256=sha(p),bytes=p.stat().st_size));continue
            if p.suffix.lower() in ['.json','.jsonl','.txt','.csv','.md','.html','.log']:
                copy(p,'evidence/'+p.relative_to(O).as_posix())
    if image_records:put(dst/'OCR_RENDERED_IMAGE_HASHES.json',dict(images=image_records,note='Rendered images retained locally; deterministic renderer and OCR raw results published.'))
    names=['T5_SOURCES.json','data/T5_QUESTIONS.json','data/SOURCE_MANIFEST.json'] if stage=='P3-P4' else ['data/LEARNING_BACKGROUND.json','data/SPOOF_TARGETS.json','KEY_SELECTION_AUDIT.md','KEY_SELECTION_STRUCTURAL_DIAGNOSTIC.json','P1/POSTHOC_CAPACITY_BREAKDOWN.json']
    for name in names:copy(O/name,'inputs_and_diagnostics/'+name)
    for p in sorted(E.iterdir()):
        if p.is_file() and p.suffix in ['.py','.md','.json']:copy(p,'code_and_protocol/'+p.name)
    copy(O/'publication_P1N10_P2/LICENSES.md','LICENSES.md')
    (dst/'.gitattributes').write_text('* -text\n',encoding='utf8')
    files=[]
    for p in sorted(dst.rglob('*')):
        if p.is_file():
            b=p.read_bytes();files.append(dict(path=p.relative_to(dst).as_posix(),bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),git_blob_sha1=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()))
    put(dst/'FILE_MANIFEST.json',dict(files=files,self_excluded=True,private_review_mapping_excluded=True,keys_excluded=True))
    print(stage,len(files),sum(x['bytes'] for x in files),flush=True)

if __name__=='__main__':main()
