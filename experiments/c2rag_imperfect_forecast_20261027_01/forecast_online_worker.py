"""One stream/condition process receives one event-prefix at a time, never a file."""
import json
import sys
from pathlib import Path
from experiments.c2rag_imperfect_forecast_20261027_01.common import OUT
from experiments.c2rag_imperfect_forecast_20261027_01.forecast import packet

sys.stdout.reconfigure(encoding='utf8');sys.stdin.reconfigure(encoding='utf8')
blocked=[]
def audit(event,args):
    if event=='open' and isinstance(args[0],str) and str(Path(args[0]).resolve()).lower().startswith(str(OUT).lower()):
        blocked.append(str(args[0]));raise PermissionError('forecast worker cannot read evidence files')
sys.addaudithook(audit)
try:open(OUT/'events.json',encoding='utf8')
except PermissionError:pass
else:raise AssertionError('worker isolation failed')
identity=None;last=-1;prefix=[]
for line in sys.stdin:
    item=json.loads(line);now=(item['stream_id'],item['condition'])
    if identity is None:identity=now
    assert now==identity and item['step']==last+1
    if item['condition']!='prior':assert item['prefix'][:-1]==prefix;prefix=item['prefix']
    last=item['step']
    print(json.dumps(packet(item),ensure_ascii=False,separators=(',',':')),flush=True)
assert last==7
sys.stderr.write('chronological input isolation verified; forbidden file selftest blocked\n')
