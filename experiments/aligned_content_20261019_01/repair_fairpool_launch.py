from pathlib import Path
import json
P=Path(__file__).parent
s=(P/'fairpool_check.py').read_text(encoding='utf8').replace("O=P/'fairpool';","assert os.environ.get('PYTHONHASHSEED')=='20261013';O=P/'fairpool_v2';")
target=P/'fairpool_check_v2.py'
if target.exists():raise RuntimeError('no overwrite')
target.write_text(s,encoding='utf8')
(P/'fairpool/run_validity.json').write_text(json.dumps({'status':'INVALID_SEED_MISMATCH','reason':'first ingress check launched without original Python hash seed; legacy code uses hash, so differences cannot be attributed to ingress','corrected_driver':'fairpool_check_v2.py','required_hash_seed':'20261013'},indent=2),encoding='utf8')
