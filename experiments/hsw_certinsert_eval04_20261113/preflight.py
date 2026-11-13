"""Chapter metadata inventory only. Never opens future T6 document contents."""
import collections
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

W=Path(__file__).resolve().parents[2]
E=Path(__file__).resolve().parent
R=W/'var/results/hsw-st'
BASE=R/'certinsert_eval03_lite_20261112/run01'
OUT=R/'certinsert_eval04_20261113/stage0'


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tag(e):
    return e.tag.split('}')[-1]


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    target=OUT/'PREFLIGHT.json'
    if target.exists():
        raise FileExistsError(target)
    inv_path=BASE/'SOURCE_INVENTORY.json'
    inv=read(inv_path)
    chapters=dict(inv['chapters'])
    extra=[read(W/'experiments/hsw_certinsert_eval03_lite_20261112/ADDITIONAL_STEM_SOURCE_FREEZE.json')['source']]
    extra+=read(W/'experiments/hsw_certinsert_eval03_lite_20261112/ADDITIONAL_SOURCE_FREEZE_02.json')['sources']
    collections_meta=[]
    for source in extra:
        path=Path(source['path'])
        assert sha(path)==source['sha256']
        root=ET.parse(path).getroot()
        parents={c:p for p in root.iter() for c in p}
        for node in root.iter():
            if tag(node)!='module':
                continue
            chain=[]; parent=parents.get(node)
            while parent is not None:
                if tag(parent)=='subcollection':
                    chain.append(next((''.join(c.itertext()).strip() for c in parent if tag(c)=='title'),'UNTITLED'))
                parent=parents.get(parent)
            if not chain:
                continue
            key=source['repo']+'|'+'/'.join(reversed(chain))
            chapters.setdefault(key,dict(repo=source['repo'],revision=source['revision'],
                subject=source['repo'].replace('osbooks-',''),modules=[]))['modules'].append(node.get('document'))
        collections_meta.append(dict(path=str(path),sha256=sha(path)))
    t4=read(BASE/'materials02/DISJOINTNESS.json')
    adjusted=W/'experiments/hsw_certinsert_eval03_batch2_adjusted_20261112'
    t5=read(adjusted/'DATA_FREEZE.json')
    blocked=set(inv['excluded_chapter_ids'])|set(t4['T4_chapters'])|set(t5['T5_chapters'])
    # Alias books can share modules; propagate chapter exclusion across them.
    while True:
        excluded_modules={(ch['repo'],m) for k,ch in chapters.items() if k in blocked for m in ch['modules']}
        expanded=blocked|{k for k,ch in chapters.items() if any((ch['repo'],m) in excluded_modules for m in ch['modules'])}
        if expanded==blocked:
            break
        blocked=expanded
    available={k:v for k,v in chapters.items() if k not in blocked}
    # Background JSON is historical data, not T6; read metadata and hash only.
    bg_path=BASE/'batch02_adjusted/data/P6_BACKGROUND.json'
    bg=read(bg_path)
    assert len(bg)==500
    bg_modules={(x['source']['id'].split('|',1)[0],x['source']['id'].split('|',1)[1]) for x in bg}
    possible_background_chapters=[k for k,ch in available.items() if any((ch['repo'],m) in bg_modules for m in ch['modules'])]
    generation_path=adjusted/'T5_GENERATION_FREEZE.json'
    generation=read(generation_path)
    baseline_path=R/'certinsert_eval_20261111_01/run01/EVAL_FREEZE.json'
    baseline=read(baseline_path)
    models={k:v for k,v in baseline.items() if '3b' in k.lower() or 'scor' in k.lower()}
    result=dict(status='METADATA_ONLY_NOT_STAGE0_COMPLETE',T6_content_reads=0,
        total_known_chapters=len(chapters),excluded_chapters=len(set(chapters)&blocked),
        available_chapters=len(available),available_by_subject=dict(collections.Counter(x['subject'] for x in available.values())),
        remaining_chapter_metadata=available,excluded_chapter_ids=sorted(blocked),
        background500_sha256=sha(bg_path),background500_possible_shared_chapters=possible_background_chapters,
        background_dedup_pending=True,R_materialized_documents=0,R_generated_documents=0,
        corpus_shortage_established=False,additional_openstax_catalog_not_exhausted=True,
        chapter_allocation_not_frozen=True,T5_generation_model=generation['model'],
        T5_parts=generation['parts'],scoring_model_metadata=models,
        metadata_input_hashes={str(p.relative_to(W)):sha(p) for p in [inv_path,
            BASE/'materials02/DISJOINTNESS.json',adjusted/'DATA_FREEZE.json',generation_path,baseline_path]},
        collections_meta=collections_meta,
        pending=['Resolve pre-score ranking and L-star selection rules',
                 'Reserve disjoint future T6 chapter IDs before parsing any new source contents',
                 'Inventory source documents and 300 independent generation questions on R-only chapters',
                 'Identify CPU NLI checkpoint and exact EVAL03 3B scorer'])
    target.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf8')
    print(json.dumps({k:result[k] for k in ['status','total_known_chapters','excluded_chapters','available_chapters','available_by_subject','scoring_model_metadata']},ensure_ascii=False))


if __name__=='__main__':
    main()
