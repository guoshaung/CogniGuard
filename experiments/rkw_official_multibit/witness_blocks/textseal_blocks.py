import json
from pathlib import Path
import time
import torch
from transformers import set_seed
from textseal import PostHocWatermarker, WatermarkConfig, ModelConfig, ProcessingConfig, EvaluationConfig
from textseal.watermarking import watermarker

root=Path(__file__).resolve().parent
# Reuse the existing checkpoint and shared tokenizer, with the upstream BF16 model-loading API.
model_path="/root/autodl-tmp/hsw-provenance/qwen05"
# Transformers 4.48 expects torch_dtype; load locally and keep TextSeal prompt and sampling unchanged.
from transformers import AutoModelForCausalLM
watermarker.load_model=lambda config: AutoModelForCausalLM.from_pretrained(config.model_name,
    local_files_only=True,torch_dtype=torch.bfloat16,device_map={"":"cuda:0"}).eval()
engine=PostHocWatermarker(watermark_config=WatermarkConfig(watermark_type="textseal", secret_key=61129),
    model_config=ModelConfig(model_name=model_path),
    processing_config=ProcessingConfig(max_gen_len=512,temperature=.8),
    evaluation_config=EvaluationConfig(enable_semantic_similarity=False,enable_rouge=False,enable_bleu=False))
set_seed(61129)
with (root/"witness_textseal.jsonl").open("x",encoding="utf8") as f, torch.inference_mode():
    for block in json.loads((root/"blocks.json").read_bytes()):
        started=time.perf_counter()
        text=engine.rephrase_with_watermark(block["text"])
        evidence=engine.evaluate_watermark(text)
        f.write(json.dumps(dict(id=block["id"],text=text,evidence=evidence,
                                tokens=engine.count_tokens(text),seconds=time.perf_counter()-started),
                           default=lambda value:value.item())+"\n")
        f.flush()
