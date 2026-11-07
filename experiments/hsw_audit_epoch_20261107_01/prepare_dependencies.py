from pathlib import Path
import hashlib,json,shutil
E=Path(__file__).resolve().parent
R=E.parents[1]/'var/results/hsw-st/audit_epoch_20261107_01/run01'
L=R/'literature'
V=E/'vendor/mpac'
if V.exists():raise SystemExit('First write only')
V.mkdir(parents=True)
rows=[]
for source,target in [('api_mb_watermark_processor.py','mb_watermark_processor.py'),
 ('api_alternative_prf_schemes.py','alternative_prf_schemes.py'),('api_normalizers.py','normalizers.py'),
 ('api_homoglyphs.py','homoglyphs.py'),('api_LICENSE.md','LICENSE.md')]:
 b=(L/source).read_bytes();(V/target).write_bytes(b)
 rows.append({'path':target,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'unaltered':True})
pin=json.loads((L/'mpac_commit.json').read_text())['sha']
(V/'SOURCE_PIN.json').write_text(json.dumps({'repository':'https://github.com/bangawayoo/mb-lm-watermarking','commit':pin,'files':rows,'license':'Apache-2.0','source_acquisition':'GitHub official Git blob API; raw host failed once'},indent=2),encoding='utf-8')
print(json.dumps({'status':'PINNED_UNCHANGED','commit':pin,'files':len(rows)}))
