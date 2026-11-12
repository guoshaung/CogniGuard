from initialize import *
import shutil,re

def main():
 report=O/'batch01_delivery';assert (report/'INDEPENDENT_COUNTS_VALIDATION.json').exists()
 dst=O/'publication02/batch01';dst.mkdir(parents=True,exist_ok=False)
 def copy(p,rel):
  q=dst/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
 for p in report.iterdir():
  if p.is_file():copy(p,p.name)
 for p in E.iterdir():
  if p.is_file() and p.suffix in ['.py','.md','.json']:copy(p,'code_and_protocol/'+p.name)
 # Complete own evidence except secrets, redundant source downloads, transient logs and reports.
 allowed=['materials02','prepared_batch1','outputs','records','scoring_recovery01','evaluation_batch1','key_stress','ocr']
 for name in allowed:
  for p in (O/name).rglob('*'):
   if not p.is_file() or p.suffix in ['.log','.tmp'] or '__pycache__' in p.parts:continue
   copy(p,'evidence/'+p.relative_to(O).as_posix())
 for name in ['SOURCE_INVENTORY.json','SOURCE_FETCH_RESULT.json','ADDITIONAL_LICENSE_AUDIT_02.json','STATISTICS_LICENSE_AUDIT.json','PRE_MODEL_FAILURE_RECOVERY.json','BATCH1_COMPUTE_CHECKPOINT.json','FAILURES.md','GPU_USAGE.jsonl','SCORING_LEDGER.jsonl']:
  p=O/name
  if p.exists():copy(p,'evidence/'+name)
 sources=read(O/'materials02/T4.json')+read(O/'materials02/IN_DOMAIN.json');paths={x['source']['raw_path']:x['source'] for x in sources};sm=[]
 for p,s in paths.items():
  src=Path(p);rel='sources/'+s['id']+'.cnxml';copy(src,rel);sm.append(dict(path=rel,sha256=sha(src),url=s['url'],revision=s['revision'],license=s['license']))
 for p in (O/'new_collections').glob('*2023*.xml'):copy(p,'sources/collections/'+p.name)
 extra=read(E/'ADDITIONAL_STEM_SOURCE_FREEZE.json')['source'];copy(Path(extra['path']),'sources/collections/statistics.xml')
 put(dst/'SOURCE_MANIFEST.json',sm)
 (dst/'LICENSES.md').write_text('''# Sources and reuse

OpenStax / Rice University, pinned Contemporary Mathematics, Introductory Statistics and Astronomy CNXML editions. Attribution, original authors and version metadata remain in source CNXML and collection files. Collection license: CC BY4.0, https://creativecommons.org/licenses/by/4.0/. SOURCE_MANIFEST.json gives exact official repository URL/revision/hash for every used module. Current NC-SA editions were not used. Text rendering, experimental insertions, crops and OCR are explicitly derived transformations; not representations of original textbook text quality.
''',encoding='utf8')
 (dst/'REPRODUCTION.md').write_text('''# Reproduction boundaries

Run `python code_and_protocol/verify_counts_batch1.py .` from this folder to independently recompute every count cell from per_item.csv. Remove or relocate the prior validation output before re-running this write-once verifier; do not alter source evidence.

Actual texts, OCR pages/outputs, score records, quality locks and source references are included. Private watermark keys and diagnostic key bytes are withheld. Hash commitments are included. Full secret-key reselection requires owner-controlled keys; count recomputation and reported p-value recomputation from public selected lists do not establish independent key recovery. Model weights, virtual environments and compiled scoring binaries are not redistributed. Code references the pre-existing CogniGuard environment; exact frozen model/config hashes appear in protocol files. No claim of turnkey model reproduction from hashes alone.

Batch01 contains no7B generation. T4_paired100 and in_domain_1000 are legacy schema labels: actual paired60 and background91 paragraphs/77 examples. T5, KGW, Unigram, compress70 cells are NOT_RUN/null. Clinical/scientific semantic quality is not certified by mechanical anchor equality. No human labels fabricated.
''',encoding='utf8')
 (dst/'.gitattributes').write_text('* -text\n',encoding='utf8')
 # Scan for live secrets without printing their values.
 keypath=W/'var/results/hsw-st/english_replication_20261110_01/e1_guarded/development_round01/restricted/key.bin';secret=keypath.read_bytes();bad=[]
 for p in dst.rglob('*'):
  if not p.is_file():continue
  bb=p.read_bytes()
  if 'restricted' in p.relative_to(dst).parts or secret in bb or secret.hex().encode() in bb or re.search(rb'sk-[A-Za-z0-9_-]{24,}',bb) or re.search(rb'(?m)^-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\r?$',bb):bad.append(p.relative_to(dst).as_posix())
 assert not bad,('REDACTION_FAILURE_PATHS_ONLY',bad)
 put(dst/'REDACTION_CHECK.json',dict(PASS=True,private_keys_uploaded=False,model_weights_uploaded=False,raw_diagnostic_key_bytes_uploaded=False,notes='Selected public word lists and key hash commitments retained; secrets never logged.'))
 files=[]
 for p in sorted(dst.rglob('*')):
  if p.is_file():
   bb=p.read_bytes();files.append(dict(path=p.relative_to(dst).as_posix(),bytes=len(bb),sha256=hashlib.sha256(bb).hexdigest(),git_blob_sha1=hashlib.sha1(b'blob '+str(len(bb)).encode()+b'\0'+bb).hexdigest()))
 put(dst/'FILE_MANIFEST.json',dict(files=files,bytes=sum(r['bytes'] for r in files),self_excluded=True));print('package',len(files),'files',round(sum(r['bytes'] for r in files)/1048576,1),'MiB')
if __name__=='__main__':main()
