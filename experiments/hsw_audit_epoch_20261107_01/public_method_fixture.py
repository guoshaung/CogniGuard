"""PUBLIC NONSECURE TEST KEY ONLY. No answer generation, no private material.

Scores an UNMARKED real-author sentence to check the official public detector
interface. This is a software fixture, never a watermark effectiveness sample.
"""
import argparse,hashlib,importlib,json,os,subprocess,sys,types
from pathlib import Path
os.environ.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
sys.dont_write_bytecode=True
import torch
from transformers import AutoTokenizer

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--tokenizer-path',required=True);ap.add_argument('--textseal-source',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
 root=Path(a.textseal_source);commit=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
 assert commit=='0b76bc64013081c570b8633d3d3585e3ee9a495a'
 for name,path in [('textseal',root/'textseal'),('textseal.watermarking',root/'textseal/watermarking')]:
  package=types.ModuleType(name);package.__path__=[str(path)];package.__package__=name;sys.modules[name]=package
 config=importlib.import_module('textseal.watermarking.config');module=importlib.import_module('textseal.watermarking.detector')
 tok=AutoTokenizer.from_pretrained(a.tokenizer_path,local_files_only=True)
 key=1234567 # PUBLIC_NONSECURE_UNIT_FIXTURE; never an actual issued key.
 text='Science is based on observation and experiment—that is, on measurements.'
 cfg=config.WatermarkConfig(watermark_type='greenlist',secret_key=key,ngram=2,gamma=.25,delta=2.,after_topp=False,repeated_windows='reuse',scoring_method='v2')
 d=module.build_detector(tok,cfg,model=None);scores=d.get_scores_by_t([text],scoring_method='v2',seen_windows=set())[0]
 E=Path(__file__).resolve().parent;sys.path.insert(0,str(E/'vendor/mpac'))
 from mb_watermark_processor import WatermarkDetector
 torch.set_num_threads(2)
 mp=WatermarkDetector(vocab=list(range(152064)),gamma=.25,delta=2.,seeding_scheme=f'ff-additive_prf-2-False-{key}',
  base=4,message_length=32,code_length=32,use_position_prf=True,use_fixed_position=False,device='cpu',tokenizer=tok,normalizers=[],ignore_repeated_ngrams=True)
 ids=tok.encode(text,add_special_tokens=False)
 result=mp._score_sequence(torch.tensor(ids),message='0'*32,return_z_at_T=False,return_bit_match=False,return_green_token_mask=False,return_z_score_max=False)
 rec={'kind':'PUBLIC_NONSECURE_UNMARKED_SOFTWARE_FIXTURE','watermark_test_key':key,'not_actual_issued_key':True,
  'unmarked_text':text,'source':'OpenStax University Physics Vol1, pinned historical CC-BY4 excerpt S01; see DATA_MANIFEST.csv',
  'token_ids':ids,'greenlist_T':len(scores),'greenlist_G':float(sum(scores)),
  'MPAC_T':int(result['num_tokens_scored']),'MPAC_G':int(result['num_green_tokens']),'MPAC_top1_radix':result['pred_message'],
  'tokenizer_sha256':hashlib.sha256((Path(a.tokenizer_path)/'tokenizer.json').read_bytes()).hexdigest(),
  'TextSeal_commit':commit,'new_answer_generation':0,'private_key_or_seed_used':False,
  'not_a_detection_success_or_receiver_attribution':True}
 with Path(a.output).open('x',encoding='utf-8') as f:json.dump(rec,f,ensure_ascii=False,indent=2)
 print(json.dumps({'status':'PUBLIC_UNIT_FIXTURE_SAVED','greenlist_T':len(scores),'greenlist_G':float(sum(scores))}))
if __name__=='__main__':main()
