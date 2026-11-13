"""Freeze R/future-T6 chapter allocation from collection metadata only."""
import hashlib
import json
from pathlib import Path

W=Path(__file__).resolve().parents[2]
O=W/'var/results/hsw-st/certinsert_eval04_20261113/stage0'


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def rank(s):
    return hashlib.sha256(('EVAL04v3|chapter|'+s).encode()).hexdigest()


def main():
    target=O/'CHAPTER_ALLOCATION.json'
    if target.exists():
        raise FileExistsError(target)
    initial=read(O/'PREFLIGHT.json')
    chapters={k:dict(v,chapter=k) for k,v in initial['remaining_chapter_metadata'].items()}
    for book in read(O/'NEW_COLLECTIONS_METADATA.json'):
        assert any('creativecommons.org/licenses/' in (x or '') for x in book['licenses'])
        for title,modules in book['chapters'].items():
            key=book['repo']+'|'+title
            if key in chapters:
                chapters[key]['modules']=sorted(set(chapters[key]['modules'])|set(modules))
            else:
                chapters[key]=dict(chapter=key,repo=book['repo'],revision=book['revision'],
                    subject='chemistry' if 'organic-chemistry' in book['repo'] else 'mathematics',modules=modules)
    # Include legacy algebra modules absent from the original 190-chapter map.
    excluded=read(W/'var/results/hsw-st/certinsert_eval_20261111_02/run01/data/EXCLUSION_FREEZE.json')['source_modules']
    used=set(excluded)
    for values in read(W/'var/results/hsw-st/certinsert_eval_20261111_02/run01/data/DOMAIN_SPLIT02.json').values():
        used.update(x['source_module'] for x in values)
    # Cross-book aliases of a T6 chapter must be allocated as one component.
    allowed={k:v for k,v in chapters.items() if not set(v['modules'])&used}
    components=[]
    remaining=set(allowed)
    while remaining:
        first=min(remaining); group={first}; mods=set(allowed[first]['modules'])
        while True:
            new={k for k in remaining if allowed[k]['repo']==allowed[first]['repo'] and mods&set(allowed[k]['modules'])}
            if new<=group:
                break
            group|=new
            mods.update(m for k in new for m in allowed[k]['modules'])
        remaining-=group
        components.append(dict(id=min(group),chapters=sorted(group),modules=sorted(mods),subject=allowed[first]['subject']))
    t6=set()
    for subject in sorted({c['subject'] for c in components}):
        pool=sorted([c for c in components if c['subject']==subject],key=lambda c:rank(c['id']))
        count=max(1,round(len(pool)*.25)) if len(pool)>1 else 0
        for c in pool[:count]:
            t6.update(c['chapters'])
    r={k:v for k,v in allowed.items() if k not in t6}
    reserved={k:v for k,v in allowed.items() if k in t6}
    rmods={(v['repo'],m) for v in r.values() for m in v['modules']}
    tmods={(v['repo'],m) for v in reserved.values() for m in v['modules']}
    assert not rmods&tmods
    obj=dict(status='METADATA_ALLOCATION_FROZEN_BEFORE_R_OR_T6_TEXT',seed='EVAL04v3|chapter',
        rule='chapter-alias components, 25% per subject reserved by SHA256 order, remaining R; no content counts or scores used',
        R_chapters=r,T6_reserved_chapter_metadata=reserved,T6_content_reads=0,
        R_unique_modules=len(rmods),T6_reserved_unique_modules=len(tmods),
        R_T6_module_intersection=0,legacy_module_exclusion_applied=True,
        note='This reserves metadata only, not T6 questions. T6 content remains unopened until stage B freeze.')
    target.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:obj[k] for k in ['R_unique_modules','T6_reserved_unique_modules','R_T6_module_intersection']}))


if __name__=='__main__':
    main()
