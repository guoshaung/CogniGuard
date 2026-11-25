import sys,json,torch
from pathlib import Path
sys.path.insert(0,'upstream')
from transformers import AutoModel,AutoTokenizer
from model_utils import RewardModel
from gen_utils import split_sentence
from utils import process_token_list
torch.set_num_threads(3)
tok=AutoTokenizer.from_pretrained('tokenizer',local_files_only=True)
tok.pad_token=tok.eos_token
dev=torch.device('cuda:0')
m=RewardModel(AutoModel.from_pretrained('decoder',local_files_only=True,torch_dtype=torch.bfloat16),tok).to(dev).eval()
m.v_head.load_state_dict(torch.load('upstream/ckpt/WatermarkDecoder-v_head.pt',weights_only=True))
with torch.inference_mode(),open('witness_propagation_scored.jsonl','x') as out:
 for line in Path('witness_propagation_raw.jsonl').read_text().splitlines():
  r=json.loads(line)
  windows=[]
  for paragraph in r['text'].split('\n\n'):
   sentences=split_sentence(paragraph)
   for i in range(len(sentences)-1):
    ids=[tok(s.strip(),return_tensors='pt').input_ids[0] for s in sentences[i:i+2]]
    if not all(len(v) for v in ids):continue
    x,mask=process_token_list(tok,ids,dev)
    scores=m.forward_value(x,mask,prompt_length=1)['chosen_end_scores'].float().tolist()
    windows.append(dict(sentences=sentences[i:i+2],scores=scores,signed_margin=(scores[0]-scores[1])/2))
  r['windows']=windows
  r['speed_code_windows']=sum(w['scores'][0]>0 and w['scores'][1]<=0 and w['signed_margin']>1.3288845486111112 for w in windows)
  out.write(json.dumps(r)+'\n')
