"""Read-only inventory and byte preservation; no imports of application code."""
import os, sys, json, hashlib, platform, subprocess, shutil
from pathlib import Path
from datetime import datetime, timezone
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
OLD=[Path('D:/cg-knowledge-assets-stage0-v2-20261018_01'),Path('D:/cg-knowledge-assets-diagnostic-20261018_01'),Path('D:/cg-knowledge-assets-review-20261018')]
SKIP={'.git','.venv','.venv-langgraph','node_modules','__pycache__','.cache','.tmp','.pytest_cache','.ruff_cache','.idea','.playwright-mcp','models','checkpoints'}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def files(root):
    for base,dirs,names in os.walk(root):
        dirs[:]=[d for d in dirs if d not in SKIP and Path(base,d).resolve()!=OUT]
        for name in names:
            p=Path(base,name)
            if p.suffix not in {'.pyc','.zip','.mp4','.png','.jpg','.jpeg','.pdf','.pth','.pt','.bin'} and p.name not in {'.env','.env.local'}:
                yield p
def snapshot():
    # Scope to the exact historic 1047-file evidence set plus current source,
    # tracked work and original diagnostic packages; avoid unrelated caches.
    old_manifest=json.loads((OLD[0]/'var/results/frozen_manifest.json').read_bytes())
    candidates={ROOT/p for p in old_manifest['source_files_sha256']}
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode('utf-8').split('\0')
    candidates.update(ROOT/p for p in tracked if p)
    for name in ['core','backend','protection','configs','experiments/c2rag_v3','experiments/cgc_propagation_v3']:
        candidates.update(p for p in files(ROOT/name) if p.suffix in {'.py','.json','.yaml','.yml','.md'})
    for r in OLD:candidates.update(files(r))
    return {str(p):digest(p) for p in sorted(candidates) if p.is_file() and p.suffix not in {'.mp4','.png','.jpg','.pdf','.pt','.pth','.bin'} and p.name!='.env'}
def save(name,value):
    with (OUT/name).open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
if __name__=='__main__':
    if sys.argv[1]=='before':
        save('preservation_before.json',snapshot())
        status=subprocess.check_output(['git','status','--porcelain=v1','-z'],cwd=ROOT)
        (OUT/'git_status_before.bin').write_bytes(status)
        agents=[]
        for r in [ROOT,ROOT/'experiments',OUT]:
            if (r/'AGENTS.md').exists():agents.append(str(r/'AGENTS.md'))
        env={'utc':datetime.now(timezone.utc).isoformat(),'root':str(ROOT),'platform':platform.platform(),'python':sys.version,'executable':sys.executable,'disk_free':shutil.disk_usage(ROOT).free,'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'git_status_entries':len([x for x in status.split(b'\0') if x]),'agents_files':agents,'cpu_count':os.cpu_count(),'old_roots':[str(r) for r in OLD]}
        save('environment_raw.json',env)
        print(json.dumps(env))
    else:
        before=json.loads((OUT/'preservation_before.json').read_text(encoding='utf-8'))
        missing=[p for p in before if not Path(p).exists()]
        changed=[p for p,h in before.items() if Path(p).exists() and digest(Path(p))!=h]
        result={'files_verified':len(before),'changed':changed,'missing':missing,'unchanged':not changed and not missing}
        save('preservation_after.json',result);print(json.dumps(result))
