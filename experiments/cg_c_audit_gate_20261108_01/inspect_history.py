"""Read-only inventory; never import or run historical experiments."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    dest = HERE / 'history_inventory.json'
    if dest.exists():
        raise FileExistsError(dest)
    names = ['cg_dynamic_problem_validation_20261105_01',
             'cg_dynamic_problem_validation_20261105_02',
             'cg_dynamic_problem_validation_20261105_03',
             'cg_base_acceptance_20261105_01',
             'cg_dynamic_audit_receiver_20261105_01',
             'cg_dynamic_receiver_completion_20261105_01',
             'cg_dynamic_framework_probe_20261105_01',
             'cg_dynamic_integrated_execution_20261105_01']
    inv = {'python': sys.version, 'root': str(ROOT), 'files': [], 'freeze_checks': [],
           'receipts': [], 'missing_receipts': [], 'old_summaries': {}, 'git': {}}
    for key, args in [('root',['rev-parse','--show-toplevel']),('branch',['branch','--show-current']),
                      ('head',['rev-parse','HEAD']),('status',['status','--porcelain']),
                      ('worktrees',['worktree','list','--porcelain'])]:
        inv['git'][key] = subprocess.check_output(['git', '-C', str(ROOT), *args]).decode('utf8')
    for name in names:
        base = ROOT/'experiments'/name
        if not base.exists():
            continue
        for p in sorted(base.rglob('*')):
            if p.is_file() and p.suffix in {'.py','.md','.json','.jsonl'} and '__pycache__' not in p.parts:
                inv['files'].append({'path': str(p.relative_to(ROOT)), 'bytes': p.stat().st_size, 'sha256':sha(p)})
    f = ROOT/'experiments/cg_dynamic_integrated_execution_20261105_01/FROZEN_SHA256.json'
    for row in json.loads(f.read_text('utf8')):
        p = Path(row['Path'])
        inv['freeze_checks'].append({'path':str(p),'expected':row['Hash'].lower(),
                                    'actual':sha(p) if p.exists() else None,
                                    'matches': p.exists() and sha(p)==row['Hash'].lower()})
    for rel in ['cg_dynamic_integrated_execution_20261105_01/runs/v2/results.json',
                'cg_dynamic_receiver_completion_20261105_01/runs/v1/results.json',
                'cg_dynamic_audit_receiver_20261105_01/runs/v1/results.json']:
        p = ROOT/'experiments'/rel
        data = json.loads(p.read_text('utf8'))
        rows = data if isinstance(data,list) else data.get('results',[])
        inv['old_summaries'][rel] = {'records':len(rows), 'statuses': {s:sum(r.get('status')==s for r in rows) for s in ['PASS','FAIL','UNKNOWN']}}
        if 'receiver_completion' in rel:
            for r in rows:
                receipt = p.parent / r['receipt']
                if not receipt.exists():
                    inv['missing_receipts'].append(str(receipt))
                    continue
                persisted=[json.loads(x) for x in receipt.read_text('utf8').splitlines()]
                expected=[(r['case_id'],i,d['op']) for i,d in enumerate(r['decisions']) if d['decision']=='ALLOW' and not d['receiver_error']]
                actual=[(x['case_id'],x['action_index'],x['op']) for x in persisted]
                inv['receipts'].append({'case_id':r['case_id'],'path':str(receipt.relative_to(ROOT)),
                                        'rows':len(persisted),'matches_decision_keys':sorted(expected)==sorted(actual),
                                        'sha256':sha(receipt)})
    dest.write_text(json.dumps(inv,ensure_ascii=False,indent=2)+'\n','utf8')
    print(json.dumps({'files':len(inv['files']),'freeze_match':sum(r['matches'] for r in inv['freeze_checks']),
                      'freeze_total':len(inv['freeze_checks']),'receipt_files':len(inv['receipts']),
                      'receipt_match':sum(r['matches_decision_keys'] for r in inv['receipts']),
                      'missing':len(inv['missing_receipts']),'summaries':inv['old_summaries']},ensure_ascii=False))

if __name__=='__main__':
    main()
