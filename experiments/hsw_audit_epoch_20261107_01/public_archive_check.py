"""Independently verify public signatures/bytes and MinHash scores.

No secrets, generator, execution log or query truth is needed. This does NOT
reproduce private-key watermark scores or certify a global false-accept rate.
"""
import argparse,csv,hashlib,json,re
from pathlib import Path
import numpy as np
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def minhash(raw):
 text=re.sub(r'\s+','',raw.decode('utf-8'))
 grams=sorted(set(text[i:i+3] for i in range(max(1,len(text)-2))))
 hv=np.array([int.from_bytes(hashlib.sha256(g.encode()).digest()[:4],'big') for g in grams],dtype=np.uint64)
 a=np.array([int.from_bytes(hashlib.sha256(f'R37N_MINHASH_A_{i}'.encode()).digest()[:4],'big')|1 for i in range(128)],dtype=np.uint64)
 b=np.array([int.from_bytes(hashlib.sha256(f'R37N_MINHASH_B_{i}'.encode()).digest()[:4],'big') for i in range(128)],dtype=np.uint64)
 return ((a[:,None]*hv[None,:]+b[:,None])%np.uint64(4294967291)).min(axis=1).astype(np.uint32)

def check(root):
 root=Path(root);D=root/'data/analysis_round01'
 # Source tree can also run the exact same verifier against the local round.
 if not D.exists():D=root/'analysis_round01'
 reg=json.loads((D/'REGISTER_PUBLIC.json').read_text())
 pub=Ed25519PublicKey.from_public_bytes(bytes.fromhex(reg['signature_public_key_hex']))
 for x in reg['rows']:
  canonical=json.dumps({'domain':reg['signature_protocol_domain'],'record':x['record']},ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
  pub.verify(bytes.fromhex(x['signature_ed25519_hex']),canonical)
 q=json.loads((D/'DETECTOR_QUERIES.json').read_text());g=json.loads((D/'GALLERY_PUBLIC.json').read_text())
 features={}
 for x in q+g:
  # Public filenames are IDs, not original machine absolute paths.
  path=D/('queries' if 'query_id' in x else 'gallery')/(x.get('query_id',x.get('reference_id'))+'.txt')
  assert sha(path)==x['public_sha256'];features[x['public_sha256']]=minhash(path.read_bytes())
 with (D/'FP_SCORES.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
 for x in rows:
  expected=float(np.mean(features[x['query_public_sha256']]==features[x['candidate_public_sha256']]))
  assert expected==float(x['MINHASH128_CHAR3'])
 return {'status':'PASS','public_signatures':len(reg['rows']),'public_text_files':len(q)+len(g),'MinHash_pairs':len(rows),
  'keys_or_private_traces_read':False,'semantic_model_or_watermark_scores_recomputed':False,'new_model_calls':0}

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('archive_root');args=ap.parse_args();print(json.dumps(check(args.archive_root)))
