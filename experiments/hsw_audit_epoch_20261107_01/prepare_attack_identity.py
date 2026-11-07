"""Read-only identity for OPTIONAL different-model attack, never a 3B issuer fallback.

No model loads, new weight download, API generation or prospective task retries.
Main C0/B2/B3 stay 7B. The attack branch cannot consume unfinished main slots.
"""
import hashlib,json,struct,urllib.request
from pathlib import Path
from bootstrap import R,save,digest
model=Path('D:/pycharm/CogniGuard/assets/models/qwen2.5-3b-instruct-q4_k_m.gguf')
D=R/'attack_preparation';D.mkdir()
metadata={};wanted={'general.name','general.architecture','general.file_type','tokenizer.ggml.tokens','tokenizer.ggml.merges','tokenizer.ggml.pre','tokenizer.chat_template','tokenizer.ggml.eos_token_id'}
with model.open('rb') as f:
 def uint(fmt):return struct.unpack('<'+fmt,f.read(struct.calcsize(fmt)))[0]
 def string(keep=True):
  n=uint('Q')
  if keep:return f.read(n).decode('utf-8')
  f.seek(n,1)
 def value(kind,keep):
  formats={0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
  if kind==8:return string(keep)
  if kind==9:
   sub=uint('I');n=uint('Q')
   if not keep and sub in formats:f.seek(n*struct.calcsize(formats[sub]),1);return None
   values=[value(sub,keep) for _ in range(n)]
   return values if keep else None
  return uint(formats[kind])
 assert f.read(4)==b'GGUF';version=uint('I');tensor_count=uint('Q');count=uint('Q')
 for _ in range(count):
  name=string();kind=uint('I');v=value(kind,name in wanted)
  if name in wanted:metadata[name]=v
cfg=json.loads((R/'CONFIG_FROZEN.json').read_text(encoding='utf-8'))
hf=json.loads((Path(cfg['tokenizer_path'])/'tokenizer.json').read_text(encoding='utf-8'))
tokens=metadata['tokenizer.ggml.tokens'];vocab={**hf['model']['vocab'],**{t['content']:t['id'] for t in hf['added_tokens']}}
mismatch=[i for s,i in vocab.items() if i>=len(tokens) or tokens[i]!=s]
merges=[' '.join(x) if isinstance(x,list) else x for x in hf['model']['merges']]
same_merges=merges==metadata.get('tokenizer.ggml.merges')
local_sha=digest(model);remote=None;network_error=None
try:
 url='https://huggingface.co/api/models/Qwen/Qwen2.5-3B-Instruct-GGUF?blobs=true'
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'HSW-readonly-identity-audit'}),timeout=25) as response:
  raw=response.read(2_000_000);remote=json.loads(raw)
 save(D/'OFFICIAL_MODEL_METADATA.json',remote)
 item=next(x for x in remote['siblings'] if x['rfilename']==model.name)
 official_sha=item['lfs']['sha256']
 license_url='https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/raw/'+remote['sha']+'/LICENSE'
 with urllib.request.urlopen(license_url,timeout=25) as response:license_text=response.read(100_000).decode('utf-8')
 save(D/'MODEL_LICENSE.txt',license_text)
except Exception as exc:network_error=type(exc).__name__;official_sha=None
status='IDENTITY_AND_TOKEN_MAP_PASS' if not mismatch and same_merges and official_sha==local_sha and network_error is None else 'ATTACK_IDENTITY_UNCONFIRMED'
save(D/'IDENTITY.json',{'status':status,'role':'optional attack only; main issuers remain 7B','model_path':str(model),'model_sha256':local_sha,
 'official_weight_sha256_matches':official_sha==local_sha,'official_revision':remote.get('sha') if remote else None,
 'license_tag':remote.get('cardData',{}).get('license_name') if remote else None,'network_error_type':network_error,
 'HF_token_ids_compared':len(vocab),'token_mismatch_count':len(mismatch),'first_mismatch_IDs':mismatch[:3],
 'merges_identical':same_merges,'GGUF_vocab_size':len(tokens),'GGUF_name':metadata.get('general.name'),
 'GGUF_pretokenizer':metadata.get('tokenizer.ggml.pre'),'GGUF_version':version,'tensors':tensor_count,
 'new_model_loads':0,'new_weight_downloads':0,'main_method_or_RAM_guard_changed':False})
save(D/'CHAT_TEMPLATE.json',{'template':metadata.get('tokenizer.chat_template'),'tokenizer_path':cfg['tokenizer_path'],'requires_successful_token_map_check_before_use':True})
print(json.dumps({'status':status,'token_mismatches':len(mismatch),'same_merges':same_merges,'weight_identity':official_sha==local_sha,'no_generation':True}))
