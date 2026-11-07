"""Whitelist-only safe publication. Does not stage/push or copy secrets/weights."""
import argparse,hashlib,json,re,shutil,subprocess
from pathlib import Path
from bootstrap import W,E,R,save,digest
from secrets_store import read
ap=argparse.ArgumentParser();ap.add_argument('--round',required=True);ap.add_argument('--destination',required=True);a=ap.parse_args()
D=R/('analysis_'+a.round);delivery=R/('delivery_'+a.round);dest=Path(a.destination)
assert dest.resolve().is_relative_to(Path('D:/pycharm/research-sync-worktrees/hsw-audit-epoch-20261107-01').resolve())
assert not dest.exists(),'New snapshot publication only; no silent replacement'
dest.mkdir(parents=True)
def copy(src,rel):
 out=dest/rel;out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,out)
for p in E.rglob('*'):
 if p.is_file() and p.suffix.lower() in {'.py','.md','.json','.c'} and '__pycache__' not in p.parts and p.name!='ISOLATION.md':
  copy(p,Path('code')/p.relative_to(E))
for p in delivery.iterdir():
 if p.is_file():copy(p,p.name)
for name in ['PROTOCOL.md','RELATED_WORK.md','METHOD_AUDIT.md','LICENSES.md','ISSUANCE_AND_KEY_LIFECYCLE.md','BASELINE_CALIBRATION_PLAN.md']:
 copy(E/name,name)
iso=json.loads((R/'WORKTREE_CHECK.json').read_text())
save(dest/'ISOLATION_PUBLIC.json',{k:iso[k] for k in ['task','actual_root','branch','HEAD','isolation_difference','result_root','original_worktree_research_files_written','GPU_calls','paid_API_calls']})
copy(E/'DATA_MANIFEST.csv','history/DATA_MANIFEST_PREPARATION.csv')
# Necessary native adapter source only, not the old archive/DLL/model/environment.
legacy=Path('D:/pycharm/CogniGuard/var/results/hsw_copyright_transfer01_20261106')
for src,rel in [(legacy/'engine/bridge.c','native/bridge.c'),(legacy/'engine/native_adapter.py','native/native_adapter.py'),
 (legacy/'engine/build.json','native/BUILD_ORIGINAL.json'),(legacy/'textseal_audit/official_sampler.py','textseal_adapter/official_sampler.py'),
 (Path('D:/pycharm/CogniGuard/var/results/hsw_r37n_necessity_20261103/fingerprints.py'),'fingerprints/fingerprints_readonly_used.py')]:
 copy(src,Path('readonly_dependency_sources')/rel)
rootfiles=['ADMISSION_PROBE.json','COMPONENT_TEST.json','CONFIG_FROZEN.json','ENGINE_READONLY_REUSE.json','freeze.json',
 'GENERATION_CODE_FREEZE.json','HISTORY_REMOTE_LOCAL_COMPARISON.json','KEY_AND_RNG_COMMITMENTS.json','MODEL_IDENTITY.json',
 'PUBLIC_DECODER_v2.json','PUBLIC_EVALUATION_FREEZE.json','S1_LIFECYCLE_TEST.json','TASKS_FROZEN.json','LIFECYCLE_V2_REGRESSION.json',
 'PUBLIC_METHOD_FIXTURE.json','RESOURCE_WAIT_USER_DIRECTIVE.json','GENERATION_PUBLIC_ALIGNMENT.json']
for name in rootfiles:
 p=R/name
 if p.exists():copy(p,Path('data')/name)
for p in (R/'inputs').glob('*'):
 if p.name.endswith('_frozen.txt') or p.name in {'DATA_MANIFEST_FROZEN.json','SOURCE_QUALITY_LOCK.json','SOURCE_PREPARATION_FAILED_01.json','SOURCE_FETCH.json'}:
  copy(p,Path('data/inputs')/p.name)
for name in ['physics_LICENSE','physics_README.md']:
 copy(R/'literature'/name,Path('sources_and_licenses')/name)
for name in ['LICENSE','NOTICE']:
 src=Path('D:/pycharm/CogniGuard/var/cache/hsw_transfer_textseal_0b76bc6')/name
 if src.exists():copy(src,Path('sources_and_licenses')/('TextSeal_'+name))
snapshot=json.loads((delivery/'RUN_SNAPSHOT.json').read_text());actual=set(snapshot['included_actual_task_ids'])
for tid in actual:
 for name in ['request.json','result.json','trace.jsonl','public.txt','FAILURE.json']:
  p=R/'raw'/tid/name
  if p.exists():copy(p,Path('data/raw')/tid/name)
for p in (R/'reviews').glob('*QUALITY_LOCK*.json'):
 data=json.loads(p.read_text());included=[r for r in data.get('rows',[]) if r['task_id'] in actual]
 if included:save(dest/'data/reviews'/p.name,{**data,'rows':included})
for p in D.rglob('*'):
 if p.is_file() and p.suffix.lower() in {'.json','.jsonl','.csv','.txt'}:
  copy(p,Path('data')/D.name/p.relative_to(D))
copy(R/'private'/f'{a.round}_QUERY_TRUTH.json',Path('data')/D.name/'EVALUATION_TRUTH.json')
# Restrict ledger to the immutable first two closed stages for round01 snapshot.
ledger=[json.loads(l) for l in (R/'RUN_MANIFEST.jsonl').read_text().splitlines()]
if a.round=='round01':
 cutoff=next(i for i,r in enumerate(ledger) if r['event']=='STAGE_EXIT' and r.get('phase')=='s2')+1
 ledger=ledger[:cutoff]
save(dest/'data/RUN_MANIFEST_AT_SNAPSHOT.jsonl',''.join(json.dumps(r)+'\n' for r in ledger))
for p in R.glob('generation_*'):
 if p.is_dir() and (p/'EXITED.json').exists():
  rec=json.loads((p/'EXITED.json').read_text())
  if a.round=='round01' and p.name not in {'generation_probe_01','generation_s2_01'}:continue
  copy(p/'EXITED.json',Path('data')/p.name/'EXITED.json')
for name in ['fingerprint_round01.log','fingerprint_round01_v2.log','watermark_round01.log','null_stress.log','alignment_postscore.log']:
 p=R/'logs'/name
 if p.exists():copy(p,Path('data/logs')/name)
copy(R/'score_fingerprints_failed_v1.py','history/score_fingerprints_failed_v1.py')
(dest/'.gitattributes').write_text('* -text\n',encoding='utf-8',newline='\n')
save(dest/'PUBLICATION_SCOPE.json',{'kind':'PARTIAL_CHECKPOINT_NOT_WHOLE_EXPERIMENT_COMPLETION','round':a.round,
 'snapshot_included_actual_task_ids':sorted(actual),'publication_does_not_interrupt_current_generator':True,
 'private_keys_seeds_DPAPI_models_env_papers_full_chapter_XML_excluded':True,
 'raw_public_texts_are_CC_BY4_derivatives_with_possible_provisional_quality_errors':True,
 'actual_watermark_scores_require_controlled_historical_detector_keys_for_recompute':True,
 'public_MinHash_and_signatures_can_be_recomputed_without_secrets':True})
# Scan actual local secret values in memory, never print them or copy DPAPI blobs.
secret=read(R/'private/RUN_SECRETS.dpapi');sign=read(R/'private/ISSUER_SIGNING.dpapi')
def leaves(o):
 if isinstance(o,dict):
  return [v for x in o.values() for v in leaves(x)]
 if isinstance(o,list):return [v for x in o for v in leaves(x)]
 return [str(o)]
values=leaves(secret)+leaves(sign)+[str(x) for x in read(R/'private/NULL_DETECTOR_KEYS.dpapi')['null_keys']]
bad=[]
for p in dest.rglob('*'):
 if not p.is_file():continue
 assert p.suffix.lower() not in {'.dpapi','.dat','.dll','.gguf','.safetensors','.pdf','.env','.sqlite3'}
 text=p.read_text(encoding='utf-8-sig')
 if re.search(r'\bsk-[A-Za-z0-9_-]{20,}',text):bad.append(str(p.relative_to(dest)))
 for v in values:
  if len(v)>=7 and re.search(r'(?<![A-Za-z0-9])'+re.escape(v)+r'(?![A-Za-z0-9])',text):
   bad.append(str(p.relative_to(dest)));break
assert not bad,'SECRET_SCAN_FAILED filenames only: '+json.dumps(sorted(set(bad)))
files={p.relative_to(dest).as_posix():digest(p) for p in dest.rglob('*') if p.is_file()}
save(dest/'SHA256_MANIFEST.json',{'self_excluded':True,'files':files})
save(R/('PUBLICATION_'+a.round+'.json'),{'destination':str(dest),'safe_payload_files':len(files)+1,
 'payload_bytes':sum(p.stat().st_size for p in dest.rglob('*') if p.is_file()),'actual_secret_scan':'PASS','secret_values_printed':False})
print(json.dumps({'status':'SAFE_CHECKPOINT_PACKAGED','files':len(files)+1,'destination':str(dest)}))
