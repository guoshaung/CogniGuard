"""将教学草稿改写为带 KGW 水印的回答（HF）或通过 API 改写（无 logits 水印）。"""

from __future__ import annotations

import inspect
import os
import re
from typing import Any

import httpx
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig, LogitsProcessorList

from content_fidelity import (
    build_extra_system_constraints,
    fidelity_violations,
    parse_fidelity,
)
from semantic_protector import (
    PlaceholderMap,
    normalize_placeholder_tokens,
    placeholders_intact,
    protect_spans,
    restore_spans,
)
from watermark_logits_processor import KGWLogitsProcessor

# 最小改动 + KGW：自由改写易破坏公式/占位符且稀释统计水印；应用「顺连接词、保骨架」
REWRITE_SYSTEM = (
    "你是中文教学文本编辑，只做「最小改动润色」。\n"
    "对方发来的正文里可能含占位符 <FORMULA_n>、<TERM_n>、<NUM_n>（含尖括号），必须逐字原样保留，"
    "禁止改成 NUM_n、禁止漏尖括号、禁止重排占位符前后公式。\n"
    "【最小改动规则】\n"
    "· 整体结构、论证顺序与原文一致；仅允许替换少量连接词（如因此↔所以、此外↔另外），不要改写成代码说明体；\n"
    "· 禁止用反引号 ` 包裹中文或公式；禁止「表达式 `…`」这种 Markdown；\n"
    "· 禁止重新推算、改写或编造任何等式与数值；若原文已有 Δ=…、根为… 等，必须与原文结论一致；\n"
    "· 禁止客服话术（当然可以、请提供、以下是）；禁止 ### 标题与多轮对话。\n"
    "输出：一段连续正文，从第一句就是教学内容。"
)


def _strip_instruction_echo(text: str) -> str:
    """去掉模型从提示里抄回来的前缀/标记行。"""
    t = text.strip()
    # 整段前缀（常见回声）
    lead = [
        r"^在下面这段文字上做轻度改写[^。\n]*[。\n]+",
        r"^在上面这段文字[^。\n]*[。\n]+",
        r"^在上面的段落中作轻度修改[^。\n]*[。\n]+",
        r"^【待改写正文】\s*",
        r"^【你的输出】[^\n]*\n*",
        r"^直接从这里开始输出改写结果[^\n]*\n*",
        r"^【您的输入】\s*",
        r"^【您的输出】\s*",
        r"^【修改前文】\s*",
        r"^【修改后文】\s*",
    ]
    # 与旧版提示完全一致的回声整句（模型常整段照抄）
    t = re.sub(
        r"^在下面这段文字上做轻度改写（换连接词、理顺句子），不要改变知识点与结论。\s*",
        "",
        t,
        flags=re.MULTILINE,
    )
    t = re.sub(
        r"^在上面这段文字上进行轻度改写[^。\n]*。\s*",
        "",
        t,
        flags=re.MULTILINE,
    )
    for _ in range(5):
        changed = False
        for p in lead:
            nt = re.sub(p, "", t, flags=re.MULTILINE)
            if nt != t:
                t = nt.strip()
                changed = True
        if not changed:
            break
    # 去掉仅含标记/说明的短行
    drop_sub = (
        "【待改写",
        "【你的输出",
        "【您的输入",
        "【您的输出",
        "【修改前文",
        "【修改后文",
        "直接从这里开始输出",
        "换连接词、理顺句子",
        "不要改变知识点与结论",
    )
    lines_out: list[str] = []
    for ln in t.split("\n"):
        s = ln.strip()
        if not s:
            lines_out.append(ln)
            continue
        if len(s) < 100 and any(x in s for x in drop_sub):
            continue
        lines_out.append(ln)
    return "\n".join(lines_out).strip()


def _extra_eos_token_ids(tok: Any) -> list[int]:
    """Qwen 等 Chat 模型应在 <|im_end|> 处结束，否则会续写伪 user 轮（JSONL 里 user\\n你能…）。"""
    out: list[int] = []
    # 仅使用单 token 的特殊符作 eos；多片段如 <|im_start|>user 不能可靠当作一个 id
    for s in ("<|im_end|>", "<|endoftext|>"):
        try:
            tid = tok.convert_tokens_to_ids(s)
            if isinstance(tid, int) and tid >= 0 and getattr(tok, "unk_token_id", None) != tid:
                out.append(tid)
        except Exception:
            pass
    return list(dict.fromkeys(out))


def _truncate_multiturn_leakage(text: str) -> str:
    """截断模型误续写的「下一轮对话」、Markdown 教案模板等。"""
    t = text
    markers = [
        "\nuser\n",
        "\nUser\n",
        "\nUSER\n",
        "\nassistant\n",
        "<|im_start|>",
        "<|im_end|>",
        "user\n你能",
        "user\n你",
        "\n你能给我一个",
        "\n你能详细",
        "\n我需要知道",
        "\n能举个例子吗",
    ]
    cut = len(t)
    for m in markers:
        i = t.find(m)
        if i != -1 and i > 30:
            cut = min(cut, i)
    if cut < len(t):
        t = t[:cut].strip()

    lines: list[str] = []
    for ln in t.split("\n"):
        s = ln.strip()
        if re.match(r"^user\s*$", s, re.I):
            break
        if s.lower() == "user":
            break
        if re.match(r"^###\s*(用户输入|我的答案|修改后|解答步骤|方法|示例|输入|输出)", s):
            break
        if s in ("---", "***"):
            continue
        lines.append(ln)
    t = "\n".join(lines).strip()
    # 去掉行末粘连的 user…
    t = re.sub(r"\s*user\s*[\n]?你能[^。]{0,80}", "", t, flags=re.IGNORECASE)
    return t


def _strip_service_fluff(text: str) -> str:
    """去掉客服式套话段落（小模型常见「当然可以！…请提供…」）。"""
    t = text.strip()
    # 连续剥离开头的空话块（多轮执行）
    fluff_line = re.compile(
        r"^(当然可以|没问题|好的|行|可以|嗯|您好)[!！。…,\s，]*\s*$|"
        r"^(以下是|这是|下面是)(改写后|修改后)?[的]?(正文|内容|回答|版本)?[：:\s]*\s*$|"
        r"^请提供[^。]{0,40}[。！!]?\s*$|"
        r"^好的?[，,]?\s*(请继续|请提供|还需要).*",
        re.IGNORECASE,
    )
    for _ in range(8):
        lines = t.split("\n")
        if not lines:
            break
        # 删除开头的空行与纯套话行
        while lines and (not lines[0].strip() or fluff_line.match(lines[0].strip())):
            lines.pop(0)
        t = "\n".join(lines).strip()
        # 段落级：首段全是短句套话则弃整段
        paras = re.split(r"\n\s*\n", t, maxsplit=1)
        if len(paras) >= 2:
            first, rest = paras[0], paras[1]
            fs = first.strip()
            if fs and len(fs) < 200 and (
                re.search(r"请提供|继续提供|上下文|要求细节|改写后的正文", fs)
                or re.match(r"^(当然可以|好的|没问题)[!！。…]?(\s|$)", fs)
            ):
                t = rest.strip()
                continue
        break

    # 全文前缀：一整串空话标题
    t = re.sub(
        r"^(当然可以|没问题|好的)[!！。…\s]*\n+"
        r"(这里是改写后的正文[：:\s]*\n*)?"
        r"(\n*)?",
        "",
        t,
        flags=re.MULTILINE,
    )
    return t.strip()


def _looks_like_rewrite_garbage(text: str) -> bool:
    """判断模型是否几乎没在教学改写（便于触发低温重试）。"""
    s = text.strip()
    if len(s) < 25:
        return True
    bad = (
        "请提供",
        "请继续",
        "上下文",
        "要求细节",
        "修改的具体内容",
        "我将为您",
        " Terminal ",
        "TermNum",
        "TIERING",
    )
    hits = sum(1 for b in bad if b in s)
    if hits >= 2:
        return True
    if any(s.startswith(p) for p in ("当然可以", "好的，请", "没问题，请")):
        return len(s) < 120
    return False


def _collapse_repeated_blocks(text: str) -> str:
    """去掉连续重复的同一段落（模型车轱辘）。"""
    parts = text.split("\n\n")
    out: list[str] = []
    for p in parts:
        k = p.strip()
        if k and out and k == out[-1].strip():
            continue
        out.append(p)
    return "\n\n".join(out).strip()


def _strip_inline_backticks(text: str) -> str:
    """去掉模型滥用成对 `…` 当强调（含中文、短公式）；占位符 normalize 在其后进行。"""
    return re.sub(r"`([^`\n]{1,120})`", r"\1", text)


def postprocess_model_rewrite(text: str, pmap: PlaceholderMap) -> str:
    t = _truncate_multiturn_leakage(text)
    t = _strip_instruction_echo(t)
    t = _strip_service_fluff(t)
    t = _collapse_repeated_blocks(t)
    t = _strip_inline_backticks(t)
    t = normalize_placeholder_tokens(t, pmap)
    return t.strip()


def _dtype_from_str(s: str):
    if s == "float16":
        return torch.float16
    if s == "bfloat16":
        return torch.bfloat16
    return torch.float32


def rewrite_with_openai(
    protected_draft: str,
    base_url: str,
    api_key: str,
    model: str,
    temperature: float,
    top_p: float,
    max_new_tokens: int,
) -> str:
    key = api_key or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    if not key:
        raise ValueError("OpenAI 兼容接口需要 api_key 或环境变量 DEEPSEEK_API_KEY / OPENAI_API_KEY")
    base = base_url.rstrip("/")
    url = base + "/chat/completions" if base.endswith("/v1") else base + "/v1/chat/completions"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": REWRITE_SYSTEM},
            {"role": "user", "content": (protected_draft or "").strip() or "（无正文）"},
        ],
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_new_tokens,
    }
    with httpx.Client(timeout=120.0) as client:
        r = client.post(url, headers={"Authorization": f"Bearer {key}"}, json=body)
        r.raise_for_status()
        data = r.json()
    return (data["choices"][0]["message"]["content"] or "").strip()


def rewrite_with_hf(
    protected_draft: str,
    model_name: str,
    device: str,
    dtype_str: str,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
    wm_key: str,
    gamma: float,
    delta: float,
    window_size: int,
    use_kgw: bool,
    repetition_penalty: float = 1.08,
    extra_system: str = "",
) -> tuple[str, Any]:
    model, tok = get_or_load_hf(model_name, device, dtype_str)

    user_body = (protected_draft or "").strip() or "（无正文）"
    sys_msg = REWRITE_SYSTEM + (("\n\n" + extra_system.strip()) if extra_system.strip() else "")
    messages = [
        {"role": "system", "content": sys_msg},
        {"role": "user", "content": user_body},
    ]
    if tok.pad_token_id is None:
        tok.pad_token_id = tok.eos_token_id

    attention_mask = None
    if hasattr(tok, "apply_chat_template") and tok.chat_template:
        template_kwargs = {
            "add_generation_prompt": True,
            "return_tensors": "pt",
            "return_dict": True,
            "enable_thinking": False,
        }
        try:
            encoded = tok.apply_chat_template(messages, **template_kwargs)
        except TypeError:
            template_kwargs.pop("enable_thinking", None)
            try:
                encoded = tok.apply_chat_template(messages, **template_kwargs)
            except TypeError:
                template_kwargs.pop("return_dict", None)
                encoded = tok.apply_chat_template(messages, **template_kwargs)
        # Transformers 5.x 常返回 BatchEncoding，generate 需要 Tensor
        if isinstance(encoded, torch.Tensor):
            input_ids = encoded
        else:
            input_ids = encoded["input_ids"]
            attention_mask = encoded.get("attention_mask")
    else:
        plain = sys_msg + "\n\n" + user_body
        encoded = tok(plain, return_tensors="pt")
        input_ids = encoded.input_ids
        attention_mask = encoded.get("attention_mask")

    dev = next(model.parameters()).device
    input_ids = input_ids.to(dev)
    if attention_mask is not None:
        attention_mask = attention_mask.to(dev)
    lp_list = LogitsProcessorList()
    if use_kgw and delta != 0:
        lp_list.append(
            KGWLogitsProcessor(
                vocab_size=tok.vocab_size,
                gamma=gamma,
                delta=delta,
                key=wm_key,
                window_size=window_size,
            )
        )

    eos_ids: list[int] = []
    if tok.eos_token_id is not None:
        eos_ids.append(int(tok.eos_token_id))
    for x in _extra_eos_token_ids(tok):
        if x not in eos_ids:
            eos_ids.append(x)

    with torch.no_grad():
        gen_kw: dict[str, Any] = {
            "max_new_tokens": min(max_new_tokens, 384),
            "do_sample": temperature > 0,
            "logits_processor": lp_list,
            "pad_token_id": tok.eos_token_id,
            "repetition_penalty": repetition_penalty,
        }
        if attention_mask is not None:
            gen_kw["attention_mask"] = attention_mask
        if len(eos_ids) > 1:
            gen_kw["eos_token_id"] = eos_ids
        elif eos_ids:
            gen_kw["eos_token_id"] = eos_ids[0]
        if temperature > 0:
            gen_kw["temperature"] = temperature
            gen_kw["top_p"] = top_p
        out = model.generate(input_ids, **gen_kw)
    gen = out[0][input_ids.shape[1] :]
    text = tok.decode(gen, skip_special_tokens=True).strip()
    return text, tok


_HF_CACHE: dict[str, tuple[Any, Any]] = {}


def get_or_load_hf(model_name: str, device: str, dtype_str: str) -> tuple[Any, Any]:
    key = f"{model_name}|{device}|{dtype_str}"
    if key not in _HF_CACHE:
        tok = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        dt = _dtype_from_str(dtype_str)
        # 避免权重已缓存后仍去 Hub 拉 generation_config.json（国内/代理/SSL 易失败）
        sig = inspect.signature(AutoModelForCausalLM.from_pretrained)
        dtype_kw: dict[str, Any] = {"dtype": dt} if "dtype" in sig.parameters else {"torch_dtype": dt}
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            **dtype_kw,
            device_map="auto" if device == "cuda" else None,
            trust_remote_code=True,
            generation_config=GenerationConfig(),
        )
        if device == "cpu":
            model = model.to("cpu")
        _HF_CACHE[key] = (model, tok)
    return _HF_CACHE[key]


def _rewrite_token_budget(mm: dict[str, Any]) -> int:
    return int(mm.get("rewrite_max_new_tokens") or mm.get("max_new_tokens", 256))


def rewrite_sample(
    draft_answer: str,
    terms: list[str],
    formulas: list[str],
    numbers: list[str],
    cfg: dict[str, Any],
    ablation: str,
    question: str = "",
) -> dict[str, Any]:
    """返回 watermarked 文本、tokenizer（可能为 None）、占位符映射与状态。"""
    ablation = (ablation or "full").lower()
    use_kgw = ablation in ("full", "kgw_only")
    use_protect = ablation in ("full", "protect_only", "no_watermark")

    pmap: PlaceholderMap | None = None
    if use_protect:
        protected, pmap = protect_spans(draft_answer, terms, formulas, numbers)
    else:
        protected = draft_answer
        pmap = PlaceholderMap()

    provider = (cfg.get("model") or {}).get("provider", "huggingface")
    mm = cfg.get("model") or {}
    fc = parse_fidelity(cfg)

    failed_ph = False
    raw_gen = ""
    tok_out = None
    fidelity_violations_last: list[str] = []
    used_draft_fallback = False
    rewrite_attempts_used = 0

    hf_name = mm.get("local_model_name", "Qwen/Qwen2.5-3B-Instruct")
    tok_budget = _rewrite_token_budget(mm)
    wm_cfg = cfg.get("watermark") or {}
    wm_key = wm_cfg.get("key", "demo_secret_key")
    gamma = float(wm_cfg.get("gamma", 0.25))
    delta_kgw = float(wm_cfg.get("delta", 2.0)) if use_kgw else 0.0
    window_size = int(wm_cfg.get("window_size", 4))
    top_p = float(mm.get("top_p", 0.9))
    base_temp = float(mm.get("rewrite_temperature", mm.get("temperature", 0.55)))
    rp_base = float(mm.get("repetition_penalty", 1.06))
    extra_constraints = build_extra_system_constraints(question, draft_answer, terms)

    if provider == "openai":
        raw_gen = rewrite_with_openai(
            protected,
            mm.get("openai_base_url", "https://api.deepseek.com"),
            str(mm.get("openai_api_key") or ""),
            mm.get("openai_model", "deepseek-chat"),
            float(mm.get("rewrite_temperature", mm.get("temperature", 0.5))),
            top_p,
            tok_budget,
        )
        raw_gen = postprocess_model_rewrite(raw_gen, pmap)
        rewrite_attempts_used = 1
        if use_protect and pmap and (pmap.terms or pmap.formulas or pmap.numbers):
            if not placeholders_intact(raw_gen, pmap):
                raw_gen = rewrite_with_openai(
                    protected,
                    mm.get("openai_base_url", "https://api.deepseek.com"),
                    str(mm.get("openai_api_key") or ""),
                    mm.get("openai_model", "deepseek-chat"),
                    float(mm.get("rewrite_temperature", mm.get("temperature", 0.35))),
                    float(mm.get("top_p", 0.85)),
                    tok_budget,
                )
                raw_gen = postprocess_model_rewrite(raw_gen, pmap)
                rewrite_attempts_used = 2
            if not placeholders_intact(raw_gen, pmap):
                failed_ph = True
        restored_pre = restore_spans(raw_gen, pmap) if use_protect else raw_gen
        if fc.enabled:
            fidelity_violations_last = fidelity_violations(
                restored_pre, draft_answer, question, terms, fc
            )
            if (
                fidelity_violations_last
                and "concept_drift" in fidelity_violations_last
                and fc.fallback_to_draft_on_drift
            ):
                restored_pre = draft_answer
                raw_gen = draft_answer
                used_draft_fallback = True
                fidelity_violations_last = []
    else:

        def hf_once(temp: float, extra_sys: str, mtoks: int, rpen: float) -> tuple[str, Any]:
            return rewrite_with_hf(
                protected,
                hf_name,
                mm.get("device", "cuda"),
                mm.get("dtype", "float16"),
                mtoks,
                temp,
                top_p,
                wm_key,
                gamma,
                delta_kgw,
                window_size,
                use_kgw,
                rpen,
                extra_system=extra_sys,
            )

        n_attempts = fc.max_attempts if fc.enabled else 1
        viol: list[str] = []
        for attempt in range(n_attempts):
            rewrite_attempts_used = attempt + 1
            extra_sys = extra_constraints if (fc.enabled and attempt >= 1) else ""
            if attempt == 0:
                temp = base_temp
            elif attempt == 1:
                temp = min(base_temp + 0.12, 0.42)
            elif attempt == 2:
                temp = min(base_temp + 0.24, 0.52)
            elif attempt == 3:
                temp = 0.46
            else:
                temp = min(0.56, base_temp + 0.32)
            rpen = rp_base + 0.02 * attempt

            raw_gen, tok_out = hf_once(temp, extra_sys, tok_budget, rpen)
            raw_gen = postprocess_model_rewrite(raw_gen, pmap)

            if _looks_like_rewrite_garbage(raw_gen):
                rg2, tok_out = hf_once(0.0, extra_sys, min(tok_budget, 220), rpen + 0.06)
                raw_gen = postprocess_model_rewrite(rg2, pmap)

            if use_protect and pmap and (pmap.terms or pmap.formulas or pmap.numbers):
                if not placeholders_intact(raw_gen, pmap):
                    rg2, tok_out = hf_once(0.0, extra_sys, tok_budget, rpen + 0.08)
                    raw_gen = postprocess_model_rewrite(rg2, pmap)

            restored_try = restore_spans(raw_gen, pmap) if use_protect else raw_gen
            if not fc.enabled:
                viol = []
                break
            viol = fidelity_violations(restored_try, draft_answer, question, terms, fc)
            if not viol:
                break

        if fc.enabled and viol == ["too_similar_to_draft"]:
            temp_b = min(base_temp + 0.38, 0.58)
            raw_gen, tok_out = hf_once(temp_b, extra_constraints, tok_budget, rp_base + 0.03)
            raw_gen = postprocess_model_rewrite(raw_gen, pmap)
            if use_protect and pmap and (pmap.terms or pmap.formulas or pmap.numbers):
                if not placeholders_intact(raw_gen, pmap):
                    rg2, tok_out = hf_once(0.0, extra_constraints, tok_budget, rp_base + 0.1)
                    raw_gen = postprocess_model_rewrite(rg2, pmap)
            rewrite_attempts_used += 1

        if use_protect and pmap and (pmap.terms or pmap.formulas or pmap.numbers):
            if not placeholders_intact(raw_gen, pmap):
                failed_ph = True

        restored_pre = restore_spans(raw_gen, pmap) if use_protect else raw_gen
        fidelity_violations_last = (
            fidelity_violations(restored_pre, draft_answer, question, terms, fc) if fc.enabled else []
        )
        if (
            fc.enabled
            and fidelity_violations_last
            and "concept_drift" in fidelity_violations_last
            and fc.fallback_to_draft_on_drift
        ):
            restored_pre = draft_answer
            raw_gen = draft_answer
            used_draft_fallback = True
            fidelity_violations_last = [
                x for x in fidelity_violations_last if x != "concept_drift"
            ]
            failed_ph = False

    restored = restored_pre

    return {
        "watermarked_answer": restored,
        "raw_model_output": raw_gen,
        "placeholder_map": pmap,
        "tokenizer": tok_out,
        "failed_placeholder_check": failed_ph,
        "use_protect": use_protect,
        "use_kgw": use_kgw,
        "fidelity_violations": fidelity_violations_last,
        "used_draft_fallback": used_draft_fallback,
        "rewrite_attempts_used": rewrite_attempts_used,
    }
