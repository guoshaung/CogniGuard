"""Zero-model config check, not text generation or a watermark effect sample."""
import json,os,sys
os.environ.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
sys.dont_write_bytecode=True
from bootstrap import R,save
save(R/'B2_CONFIG_FIXTURE_PROTOCOL.json',{'kind':'UNIT_FIXTURE_NOT_RESEARCH_TEXT','actual_model_forward_calls':0,
 'public_test_key_no_security_use':1234567,'history_public_fixture':[33,49,18,17],
 'raw_logits':'all zero float32, shape 1x152064','expected_bias_support':[0.0,2.0],
 'expected_effective_method':'binary','same_pinned_factory_and_config_as_B2':True})
import torch
from transformers import AutoTokenizer
from methods import Sampler,V
torch.set_num_threads(2)
cfg=json.loads((R/'CONFIG_FROZEN.json').read_text(encoding='utf-8'))
tok=AutoTokenizer.from_pretrained(cfg['tokenizer_path'],local_files_only=True)
s=Sampler(tok,'B2',1234567,None);g=s.sample.generator
assert g.wm_args.method=='binary' and g.delta==2 and not g.after_topp
raw=torch.zeros((1,V),dtype=torch.float32);history=torch.tensor([[33,49,18,17]],dtype=torch.long)
expected=g.green_scores(history[:,-2:],V)
actual=g.logits_processor(raw.clone(),history[:,-2:])
assert torch.equal(actual,2*expected) and set(actual.unique().tolist())=={0.,2.}
save(R/'B2_CONFIG_FIXTURE_RESULT.json',{'status':'PASS','kind':'UNIT_FIXTURE_NOT_RESEARCH_TEXT',
 'effective_method':g.wm_args.method,'bias_support':actual.unique().tolist(),'biased_count':int((actual>0).sum()),
 'finite':bool(torch.isfinite(actual).all()),'delta':2,'before_top_p':True,'public_test_key':1234567,
 'real_model_forward_calls':0,'real_generated_answers':0,'actual_per_step_raw_logit_arrays_recovered':False,
 'limits':'Verifies same pinned official bias path/config on a flat fixture; does not measure real model argmax margins or replace public scores.'})
print('B2_OFFICIAL_CONFIG_FLAT_BIAS_FIXTURE_PASS_NO_MODEL')
