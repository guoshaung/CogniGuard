"""Optional MUSA/HF execution branch. No dependency import or model load until used."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from .kgw import InternalKGW
from .protocol import ModelIdentity, Task, canonical, digest


def verify_model_files(model_dir: Path, manifest: dict, identity: ModelIdentity) -> None:
    if digest(canonical(manifest)) != identity.manifest_sha256:
        raise ValueError("Model manifest identity mismatch")
    files = manifest.get("files", {})
    if not files or not any(name.endswith(".safetensors") for name in files):
        raise ValueError("Local safetensors manifest required, not a GGUF path")
    candidates = {p.name for p in model_dir.glob("*.safetensors")}
    if not candidates.issubset(files):
        raise ValueError("Unfrozen loadable safetensors candidate")
    for name, expected in files.items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name:
            raise ValueError("Unsafe manifest path")
        p = (model_dir / relative).resolve()
        p.relative_to(model_dir.resolve())
        import hashlib

        h = hashlib.sha256()
        with p.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024**2), b""):
                h.update(block)
        if h.hexdigest() != expected:
            raise ValueError("Model file hash mismatch: " + name)
    required = {"config.json", "tokenizer.json", "tokenizer_config.json"}
    if not required.issubset(files) or files["tokenizer.json"] != identity.tokenizer_sha256:
        raise ValueError("Tokenizer/config must be in the frozen model manifest")
    for name in (
        "generation_config.json",
        "special_tokens_map.json",
        "added_tokens.json",
        "vocab.json",
        "merges.txt",
    ):
        if (model_dir / name).exists() and name not in files:
            raise ValueError("Unfrozen optional tokenizer/generation file: " + name)
    if (model_dir / "adapter_config.json").exists():
        raise ValueError("An additional PEFT adapter changes model identity")
    index = model_dir / "model.safetensors.index.json"
    if index.exists():
        if index.name not in files:
            raise ValueError("Weight index must be frozen")
        referenced = set(json.loads(index.read_bytes())["weight_map"].values())
        if not referenced.issubset(files):
            raise ValueError("Unfrozen weight shard")


class MusaHFEngine:
    """Single in-process generate call with an internal KGW callback.

    FP16 is an explicitly different precision branch from R18 Q4_K_M.
    vLLM V1 batching requires a separate version-vetted adapter and is not
    silently mapped to this request callback.
    """

    def __init__(self, model_dir: Path, identity: ModelIdentity, manifest: dict, device: str):
        identity.validate()
        if identity.precision != "fp16" or device != "musa:0":
            raise ValueError("Only explicit FP16 / musa:0 branch prepared")
        verify_model_files(model_dir, manifest, identity)
        import torch
        import torch_musa  # noqa: F401  # register the actual vendor backend
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if not hasattr(torch, "musa") or not torch.musa.is_available():
            raise RuntimeError("MUSA unavailable; CUDA/CPU fallback is forbidden")
        self.torch = torch
        self.device = device
        self.identity = identity
        self._lock = threading.Lock()
        start = time.perf_counter()
        self.tokenizer = AutoTokenizer.from_pretrained(
            str(model_dir), local_files_only=True, trust_remote_code=False
        )
        config = json.loads((model_dir / "config.json").read_bytes())
        if config.get("model_type") != "qwen2" or config.get("hidden_size") != 3584:
            raise ValueError("Model config does not match Qwen2.5-7B")
        if self.tokenizer.vocab_size != 151643:
            raise ValueError("Unexpected tokenizer vocabulary")
        self.model = (
            AutoModelForCausalLM.from_pretrained(
                str(model_dir),
                local_files_only=True,
                trust_remote_code=False,
                torch_dtype=torch.float16,
                attn_implementation="eager",
                use_safetensors=True,
            )
            .to(device)
            .eval()
        )
        torch.musa.synchronize()
        self.load_seconds = time.perf_counter() - start

    def generate(self, task: Task, key: str | None) -> dict:
        # The HF reference engine serializes calls; no shared RNG/model-state races.
        with self._lock:
            return self._generate(task, key)

    def _generate(self, task: Task, key: str | None) -> dict:
        task.validate()
        if task.model != self.identity:
            raise ValueError("Worker model differs from frozen task")
        if task.method == "kgw" and (not key or digest(key.encode()) != task.key_sha256):
            raise ValueError("Frozen KGW key missing/mismatched")
        torch = self.torch
        from transformers import GenerationConfig, LogitsProcessorList

        prefix = self.tokenizer.apply_chat_template(
            task.messages, tokenize=True, add_generation_prompt=True
        )
        if len(prefix) + task.max_new_tokens > 4096:
            raise ValueError("No truncation or hidden context-window change permitted")
        processor = InternalKGW(key) if task.method == "kgw" else None
        ids = torch.tensor([prefix], dtype=torch.long, device=self.device)
        mask = torch.ones_like(ids)
        torch.manual_seed(task.seed)
        torch.musa.manual_seed_all(task.seed)
        torch.musa.reset_peak_memory_stats()
        torch.musa.synchronize()
        start = time.perf_counter()
        with torch.inference_mode():
            output = self.model.generate(
                input_ids=ids,
                attention_mask=mask,
                generation_config=GenerationConfig(),
                max_new_tokens=task.max_new_tokens,
                do_sample=False,
                num_beams=1,
                num_return_sequences=1,
                repetition_penalty=1.0,
                use_cache=True,
                logits_processor=LogitsProcessorList([processor] if processor else []),
                eos_token_id=[151643, 151645],
                pad_token_id=151643,
                return_dict_in_generate=True,
                output_scores=False,
                forced_bos_token_id=None,
                forced_eos_token_id=None,
                min_length=0,
                min_new_tokens=0,
                bad_words_ids=None,
                no_repeat_ngram_size=0,
                renormalize_logits=False,
            )
        torch.musa.synchronize()
        elapsed = time.perf_counter() - start
        returned = output.sequences[0, len(prefix) :].detach().cpu().tolist()
        body = returned[:-1] if returned and returned[-1] in (151643, 151645) else returned[:]
        if any(x in (151643, 151645) for x in body):
            raise ValueError("Unexpected interior EOS; do not silently trim generated output")
        text = self.tokenizer.decode(
            body, skip_special_tokens=False, clean_up_tokenization_spaces=False
        )
        canonical_ids = self.tokenizer.encode(text, add_special_tokens=False)
        return {
            "status": "COMPLETED",
            "method": task.method,
            "input_sha256": task.input_sha256,
            "messages_sha256": task.messages_sha256,
            "model": task.to_dict()["model"],
            "algorithm": {
                "gamma": task.gamma,
                "delta": task.delta,
                "window": task.window,
                "prf": task.prf,
                "key_sha256": task.key_sha256,
            },
            "generation": {
                "mode": "greedy",
                "seed": task.seed,
                "max_new_tokens": task.max_new_tokens,
                "num_beams": 1,
                "repetition_penalty": 1.0,
                "backend": "transformers-torch_musa-internal",
            },
            "text": text,
            "text_sha256": digest(text.encode()),
            "prompt_ids": prefix,
            "generated_ids": body,
            "returned_ids": returned,
            "prompt_tokens": len(prefix),
            "output_tokens": len(body),
            "stop_reason": "eos" if returned and returned[-1] in (151643, 151645) else "token_cap",
            "canonical_retokenization_equal": canonical_ids == body,
            "callback_calls": processor.calls if processor else 0,
            "callback_context4": processor.contexts if processor else [],
            "callback_green_sha256": processor.green_hashes if processor else [],
            "generation_seconds": elapsed,
            "load_seconds": self.load_seconds,
            "tokens_per_second": len(body) / elapsed if elapsed else None,
            "peak_musa_allocated_bytes": torch.musa.max_memory_allocated(),
            "peak_musa_reserved_bytes": torch.musa.max_memory_reserved(),
            "peak_scope": "this process torch MUSA allocator, not whole-device usage",
            "precision_changed_from_R18": True,
            "software": {
                "torch": torch.__version__,
                "numpy": __import__("numpy").__version__,
                "transformers": __import__("transformers").__version__,
            },
        }
