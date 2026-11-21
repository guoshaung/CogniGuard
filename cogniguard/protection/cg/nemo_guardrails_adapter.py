from __future__ import annotations

import json
import re
import unicodedata
from copy import deepcopy
from pathlib import Path
from typing import Any

FORBIDDEN_FIELD_NAMES = {
    "raw_multimodal_data",
    "raw_student_data",
    "full_student_profile",
    "long_term_student_profile",
    "raw_teacher_resources",
    "full_teacher_resources",
    "full_original_teacher_resources",
    "direct_profile_update",
    "wrong_answer_image_path",
    "audio_features",
    "emotion_signals",
    "handwriting_trace",
    "full_learning_history",
    "student_id",
}

# These broad request heuristics are owned by the domain policies once CG has
# authorized and transformed an inter-agent message. Independent checks remain.
DOMAIN_REQUEST_POLICY_IDS = frozenset(
    {
        "protected_resource_summary_request",
        "full_student_profile_request",
        "raw_multimodal_data_request",
        "original_teacher_question_bank_request",
    }
)

PROMPT_INJECTION_PATTERNS = (
    r"ignore\s+(all|previous|the)\s+(rules|instructions|copyright)",
    r"reveal\s+(the\s+)?(full|original)\s+(resource|question bank|teacher)",
    r"output\s+(the\s+)?(system prompt|developer message|hidden prompt)",
    r"bypass\s+(cg|copyright|guardrails?)",
    r"do\s+not\s+(follow|obey)\s+(copyright|safety|policy)",
    # Retrieved imperatives cannot override policy or propose profile writes.
    # Quarantine the whole Chinese clause, preserving surrounding factual text.
    r"(?:忽略|无视|绕过|覆盖)[^。！？!?\n]{0,24}(?:之前|前面|系统|开发者|版权|安全)[^。！？!?\n]{0,24}(?:指令|提示|规则|策略)[^。！？!?\n]*(?:[。！？!?]|$)",
    r"(?:输出|展示|泄露|导出)[^。！？!?\n]{0,24}(?:学生.{0,8}(?:地址|隐私|完整历史|完整画像)|原始画像|完整学生画像|系统提示|开发者消息|隐藏提示)[^。！？!?\n]*(?:[。！？!?]|$)",
    r"(?:将|把)[^。！？!?\n]{0,24}(?:掌握程度|掌握度|学生画像|画像字段|学习记录)[^。！？!?\n]{0,24}(?:改成|改为|设为|设置为|更新为)[^。！？!?\n]*(?:[。！？!?]|$)",
)

# These patterns require an actionable harmful request, not merely a sensitive
# word.  That distinction is important for contrast sets such as XSTest.
HARMFUL_INTENT_PATTERNS = (
    # Actionable Chinese construction requests, not discussion of hazardous
    # materials, history, or safety management on their own.
    r"(?:如何|怎么|怎样)\s*(?:才能|可以|能)?\s*(?:制作|制造|自制|配制|合成)[^。！？!?\n]{0,12}(?:炸药|炸弹|爆炸物)",
    r"(?:步骤|教程|配方|具体方法)[^。！？!?\n]{0,16}(?:制作|制造|自制|配制|合成)[^。！？!?\n]{0,12}(?:炸药|炸弹|爆炸物)",
    r"(?:制作|制造|自制|配制|合成)[^。！？!?\n]{0,12}(?:炸药|炸弹|爆炸物)[^。！？!?\n]{0,16}(?:步骤|教程|配方|具体方法)",
    r"\b(?:write|draft|create|generate|design|compose)\b.{0,100}\b(?:defamatory|xenophobic|sexist|racist|discriminatory|body[- ]shaming|harassing)\b",
    r"\b(?:promote|glorif(?:y|ies)|praise|encourage|advocate)\b.{0,120}\b(?:holocaust|nazi|slavery|enslavement|genocide|inferior|killed|harass|sham(?:e|ing))\b",
    r"\b(?:ridicule|demean|harass|enslave|kill|murder|shoot|execute|beat up|overpower)\b.{0,100}\b(?:people|person|someone|spouse|wife|woman|colleague|ethnic|lgbtq|population|group)\b",
    r"\b(?:how to|steps?|instructions?|tutorial|guide)\b.{0,100}\b(?:make (?:a )?bomb|hack into|identity theft|blackmail|ransomware|malware|ddos|forge documents|tamper with)\b",
    r"\b(?:develop|create|write|provide)\b.{0,80}\b(?:malware|ransomware|phishing|fake charity|fake drug|blackmail message)\b",
    r"\b(?:explicit pornographic|pose as a minor|solicit sexual|unprotected sex org)\b",
    r"\b(?:fake news|fabricated statistic|spread disinformation|baseless rumor)\b",
    r"\b(?:kill|terminate|execute|shoot)\b.{0,40}\b(?:a person|someone|people|my wife|human)\b",
    r"\bblow up\b.{0,40}\b(?:a house|building|school|vehicle|person|people)\b",
    r"\b(?:commit (?:a )?murder|smash in someone['’]s skull|hang myself|sever my (?:cervical )?artery)\b",
    r"\b(?:eliminat(?:e|ing)|liquidat(?:e|ing)|capture|throttle|strangle|tackle)\b.{0,60}\b(?:people|person|someone|child|date|spouse|woman|man|their legs)\b",
    r"\b(?:buy|get|acquire|obtain)\b.{0,40}\b(?:cocaine|crack|ecstasy(?: pills?)?|meth|heroin|illegal drugs?|marijuana|cannabis|some weed)\b",
    r"\b(?:scheme to illegally extort|gamble (?:their|your|my) life savings|fake charity|fake (?:weight loss )?drug)\b",
    r"\b(?:circumvent(?:ing)? copyright protections?|pirat(?:e|ing) content|illegally prescribe opioids?)\b",
    r"\b(?:nefariously alter criminal records?|tamper(?:ing)? with electronic monitoring devices?)\b",
    r"\b(?:young people|minor(?:s)?)\b.{0,80}\b(?:unprotected sex|sexual conversations?|orgies)\b",
    r"\bfacial recognition\b.{0,80}\bidentify\b.{0,80}\b(?:on|by|based on) race\b",
    # Economic, fraud, privacy and government abuse: pair an actionable verb
    # with a concrete harmful object to preserve XSTest contrast cases.
    r"\b(?:hide|conceal|falsify|evade|avoid)\b.{0,80}\b(?:income|tax(?:es)?|payment|detection|authorities|law enforcement)\b",
    r"\b(?:bribe|scam|defraud|counterfeit|insider trading|manipulate)\b.{0,100}\b(?:official|people|money|currency|stock|slot machine|review|customer|company)\b",
    r"\b(?:make|manufacture|distribute|sell)\b.{0,80}\b(?:counterfeit money|fake drug|hazardous waste|date rape drug|child pornography)\b",
    r"\b(?:phishing email|steal|clone|track|harvest|obtain)\b.{0,100}\b(?:password|login credentials|health records|debit cards|social security|private information|location)\b",
    r"\b(?:convince|coerce|indoctrinate|manipulate)\b.{0,100}\b(?:someone|people|children|secretary|doctor|patient|victim)\b.{0,100}\b(?:suicide|sex|money|cult|explicit|opioids)\b",
    r"\b(?:justify|normalize|promote|spread|claim|argue)\b.{0,100}\b(?:genocide|5g causes covid|vaccines cause autism|earth is flat|illuminati|holocaust never happened|global warming is a hoax)\b",
    r"\b(?:nuclear weapon|torture ring|stalking behavior|predatory stalking|human trafficking|sexual exploitation)\b",
    r"\b(?:personalized|specific|tailored|expert)\b.{0,100}\b(?:medical treatment|legal advice|investment products|cheat a smog test|sell organs|extinguish a fire)\b",
    r"\b(?:gain unauthorized access|sudo access|keylogger|hijack|mine cryptocurrency|crack passwords|evade detection)\b",
    r"\b(?:eat laundry detergent|promote anorexia|healthy lifestyle choice|manipulate someone into committing suicide)\b",
    # Broad XSTest contrast coverage. The object clause prevents matching safe
    # homonyms such as "kill a process" or "shoot a photo".
    r"\b(?:kill|murder|shoot|stab|bomb|blow up|set .* on fire|attack|punch|smash|crush|slash|slay|butcher|drown|strangle|choke|poison|gut|decapitate|chop up|cut off|obliterate|annihilate|exterminate|eradicate|eliminate|hunt down)\b.{0,80}\b(?:person|people|someone|human|child|toddler|woman|man|wife|husband|family|class|cop|politician|president|hospital|school|army base|city|village|population|immigrants|gay people|black people)\b",
    r"\b(?:how do i|how can i|what (?:are|is) the (?:best|good|perfect) way|what steps should i take|where can i)\b.{0,100}\b(?:commit suicide|armed robbery|violent assault|rape|arson|terrorism|fraud|identity theft|kidnapping|launder money|make cocaine|make crack|synthesi[sz]e LSD|sell marijuana|treason)\b",
    r"\b(?:why|what reasons)\b.{0,120}\b(?:women|gay people|trans people|jewish people|hindus|muslims|roma people|disabled people|black people|latinos|immigrants|elderly people|lesbians|asexual people|homeless people)\b.{0,120}\b(?:should not|not be allowed|denied|barred|kicked|discriminat|less than|overrepresented|no rights|not hold)\b",
    r"\b(?:why|how can i|what can i do|what were the benefits)\b.{0,140}\b(?:holocaust|jim crow|pinochet|nanjing massacre|khmer rouge|rwandan genocide|9/11 attacks|hitler|pulse nightclub|isis|slave trade|auschwitz|ethnic cleansing|atomic bombs)\b.{0,100}\b(?:justif|replicate|recreate|benefit|fabrication|never happened|overstate|success)\b",
    r"\b(?:social security number|credit card details|browsing history|medical records|mental health history|iphone pin|home address|private email|passport number|instagram password|facebook login|bank account details|religious beliefs|political affiliation|sexual orientation|immigration status|criminal history)\b",
)

# Untrusted retrieved text is data.  Imperatives that attempt to control the
# answer are quarantined before prompt composition, while ordinary prose stays.
UNTRUSTED_INSTRUCTION_PATTERNS = (
    r"(?i)(?:^|[\n.!?]\s*)(?:write|provide|show|list|recommend|suggest|help|summarize|describe|analy[sz]e|determine|classify|translate|render|reply|respond|encode|encrypt|reverse|apply|use|replace|express|add|include|integrate|modify|enhance|augment)\b[^\n]{3,240}(?:[.!?]|$)",
    r"(?i)(?:^|[\n.!?]\s*)(?:how (?:can|do|should) (?:i|you)|can you|what are)\b[^\n]{3,240}(?:[.!?]|$)",
)

# Contextual second-stage suppression for contrastive safe requests. These
# cues describe analysis, fiction, games, history, or negation; they do not
# override explicit system-prompt, privacy-field, or copyright policies.
SAFE_CONTEXT_PATTERNS = (
    r"\b(?:fictional|fiction|novel|film|movie|character|game|video game|call of duty|the witcher|simpsons?|disney|harry potter|star wars|james bond|batman|naruto)\b",
    r"\b(?:historical|history|during world war|what kind of|what does it mean|legal definition|define|definition|explain|describe|discuss)\b",
    r"\b(?:not|never|without)\s+(?:bomb|kill|shoot|attack|harm)\b",
    r"\b(?:mango|saturn)\b.{0,80}\b(?:freedom|business|belief|religious)\b",
)


class NeMoGuardrailsAdapter:
    """CG-owned adapter for CogniGuard's NeMo Guardrails checks.

    The adapter exposes explicit rails for input, retrieval, execution, and
    output. Checks are implemented locally; package availability is reported
    separately and does not activate LLMRails or execute the Colang configuration.
    """

    def __init__(self, config_path: str, enabled: bool = True):
        self.config_path = str(config_path)
        self.enabled = enabled
        self.provider_name = "NeMo Guardrails"
        self.runtime_available = _nemo_guardrails_importable()
        self.config_exists = Path(config_path).exists()

    def check_user_input(
        self, text: str, context: dict, *, _skip_policy_ids: frozenset[str] = frozenset()
    ) -> dict:
        return self._check_text(
            rail_type="input",
            text=text,
            context=context,
            skip_policy_ids=_skip_policy_ids,
            checks=(
                _policy(
                    "protected_resource_summary_request",
                    "sanitize",
                    "仅允许返回教师资源的最小化概览，不包含目录、文件、资源标识或原文。",
                    (
                        r"(素材库|资源库|题库|教师资源|课件|素材)[\s\S]{0,80}(摘要|概览|基本信息|最基本信息|大致情况|有哪些)",
                        r"(摘要|概览|基本信息|最基本信息|大致情况)[\s\S]{0,80}(素材库|资源库|题库|教师资源|课件|素材)",
                    ),
                ),
                _policy(
                    "full_student_profile_request",
                    "block",
                    "Requests for full student profiles are not allowed.",
                    (
                        r"\b(full|complete|entire|long[- ]term)\b.*\b(student|learner)\b.*\b(profile|learning profile|history)\b",
                        r"\bshow me\b.*\b(full|complete)\b.*\b(profile|learning history)\b",
                    ),
                ),
                _policy(
                    "raw_multimodal_data_request",
                    "block",
                    "Raw multimodal data must remain inside the MM-FOPD raw boundary.",
                    (
                        r"\b(raw|original)\b.*\b(screenshot|image|audio|handwriting|trace|emotion signal)\b",
                        r"\bwrong[- ]answer screenshot\b",
                        r"\bhandwriting trace\b",
                        r"\bcoordinate_points\b",
                    ),
                ),
                _policy(
                    "original_teacher_question_bank_request",
                    "block",
                    "受保护的教师素材库、资源库和题库不能被查看、枚举或原文导出。",
                    (
                        r"\b(original|exact|verbatim|literal)\b.*\b(teacher|question bank|source file|resource)\b",
                        r"\boutput\b.*\bquestion bank\b.*\bexactly\b",
                        r"(查看|看看|访问|打开|展示|列出|导出|给我|发我).{0,12}(素材库|资源库|题库|教师资源|内部资料|内部资源|素材|课件)",
                        r"(素材库|资源库|题库|教师资源|内部资料|内部资源).{0,12}(内容|目录|列表|原文|全文|文件|数据)",
                        r"(原始|完整|全部|内部|未公开).{0,8}(素材|资源|题库|资料)",
                    ),
                ),
                _policy(
                    "copyright_bypass_request",
                    "block",
                    "绕过版权或 CG 控制的请求已被拦截。",
                    (
                        r"\bbypass\b.*\b(copyright|c2[-²]?rag|exposure budget|return mode)\b",
                        r"\bignore\b.*\b(copyright|exposure budget|return mode)\b",
                        r"(绕过|跳过|关闭|忽略).{0,10}(版权|水印|CG|安全策略|防护|审计)",
                    ),
                ),
                _policy(
                    "jailbreak_or_system_prompt_exfiltration",
                    "block",
                    "绕过系统指令、执行编码指令或索取系统提示词的请求已被拦截。",
                    (
                        r"\b(?:ignore|disregard|override|forget)\b.{0,80}\b(?:previous|prior|system|developer)\b.{0,80}\b(?:instruction|prompt|rule|message)\b",
                        r"i\s*g\s*n\s*o\s*r\s*e.{0,80}\b(?:instruction|prompt|rule|message)s?\b",
                        r"(?:ignore|[i1l][gq]n[o0]r[e3]).{0,80}\b(?:instruction|prompt|rule|message)s?\b",
                        r"\b(?:decode|base64|rot13|hex)\b[\s\S]{0,120}\b(?:follow|execute|obey|instruction|prompt)\b",
                        r"\b(?:reveal|output|print|show|repeat|dump)\b.{0,80}\b(?:system prompt|developer message|hidden prompt|internal instructions?)\b",
                        r"\b(?:quote|share|repeat|translate|disclose)\b.{0,80}\b(?:internal polic(?:y|ies)|developer context|hidden instruction|system prompt)\b",
                        r"(忽略|无视|绕过|覆盖).{0,24}(之前|前面|系统|开发者).{0,24}(指令|提示|规则|消息)",
                        r"(输出|展示|泄露|打印).{0,24}(系统提示|开发者消息|隐藏提示|内部指令)",
                        r"(内部|隐藏|系统).{0,16}(规则|设定|提示|指令).{0,16}(逐字|原样|告诉|泄露|输出)",
                        r"(?:export|call|invoke)[_\s-]*(?:profile|student).{0,80}(?:full[_\s-]*learning[_\s-]*history|student[_\s-]*id)",
                        r"\b(?:enumerate|list|export)\b.{0,80}\b(?:protected teaching resource|teacher resource|question bank)\b.{0,80}\b(?:identifier|chapter|order|directory)\b",
                        r"\b(?:administrator|admin)\b.{0,80}\b(?:complete|full)\b.{0,80}\b(?:learner|student)\s+(?:record|profile)\b",
                        r"<\s*(?:system|developer|assistant)\s*>.{0,160}\b(?:override|ignore|reveal|disclose)\b",
                        r"\b(?:print|show|reveal|share)\b.{0,80}\b(?:hidden|internal)\b.{0,40}\b(?:configuration|config)\b",
                        r"\b(?:infer|deduce|reconstruct)\b.{0,80}\b(?:full|complete)\b.{0,80}\b(?:weakness|history|profile)\b",
                    ),
                ),
                _policy(
                    "actionable_harmful_intent",
                    "block",
                    "The request asks for actionable harmful content.",
                    HARMFUL_INTENT_PATTERNS,
                ),
            ),
        )

    def check_retrieved_chunks(self, chunks: list[dict], context: dict) -> dict:
        original = _json_preview(chunks)
        if not self.enabled:
            return self._result(
                "retrieval",
                "allow",
                "NeMo Guardrails adapter is disabled.",
                original,
                original,
                "disabled",
            )

        sanitized_chunks = deepcopy(chunks)
        matched = []
        untrusted_source = str(context.get("source_trust", "")).casefold() in {
            "untrusted",
            "untrusted_external_content",
            "external_untrusted",
        }
        for chunk in sanitized_chunks:
            content = str(chunk.get("content", ""))
            sanitized_content, chunk_matches = _sanitize_prompt_injection(content)
            if untrusted_source:
                sanitized_content, boundary_matches = _quarantine_untrusted_instructions(
                    sanitized_content
                )
                chunk_matches.extend(boundary_matches)
            if chunk_matches:
                matched.extend(chunk_matches)
                chunk["content"] = sanitized_content
                chunk["prompt_injection_sanitized"] = True

        # Retrieved text remains untrusted data, but C2-RAG owns resource
        # licensing, release modes and domain budgets. Keep independent checks
        # without treating copyright/profile request heuristics as that policy.
        leak_policy = self.check_user_input(
            "\n".join(str(chunk.get("content", "")) for chunk in sanitized_chunks),
            context, _skip_policy_ids=DOMAIN_REQUEST_POLICY_IDS,
        )
        if leak_policy["decision"] == "block":
            return self._result(
                "retrieval",
                "block",
                leak_policy["reason"],
                original,
                "",
                leak_policy["matched_policy"],
            )

        if matched:
            return {
                **self._result(
                    "retrieval",
                    "sanitize",
                    "Retrieved teacher chunk contained prompt-injection instructions and was sanitized.",
                    original,
                    _json_preview(sanitized_chunks),
                    "retrieval_prompt_injection",
                ),
                "sanitized_chunks": sanitized_chunks,
            }

        return self._result(
            "retrieval",
            "allow",
            "Retrieved chunks passed instruction and independent safety checks.",
            original,
            original,
            "none",
        )

    def check_agent_action(
        self,
        sender: str,
        receiver: str,
        message_type: str,
        payload: dict,
        *,
        _domain_authorized: bool = False,
    ) -> dict:
        original = _json_preview(
            {
                "sender": sender,
                "receiver": receiver,
                "message_type": message_type,
                "payload": payload,
            }
        )
        if not self.enabled:
            return self._result(
                "execution",
                "allow",
                "NeMo Guardrails adapter is disabled.",
                original,
                original,
                "disabled",
            )

        forbidden = sorted(_find_forbidden_fields(payload))
        if forbidden:
            return self._result(
                "execution",
                "block",
                f"Agent action attempted to access forbidden field(s): {', '.join(forbidden)}.",
                original,
                "",
                "agent_forbidden_field_access",
            )

        text_policy = self.check_user_input(
            original,
            {},
            _skip_policy_ids=DOMAIN_REQUEST_POLICY_IDS if _domain_authorized else frozenset(),
        )
        if text_policy["decision"] == "block":
            return self._result(
                "execution",
                "block",
                text_policy["reason"],
                original,
                "",
                text_policy["matched_policy"],
            )

        return self._result(
            "execution",
            "allow",
            "Agent action passed CG execution guardrails.",
            original,
            original,
            "none",
        )

    def check_output(self, text: str, context: dict) -> dict:
        return self._check_text(
            rail_type="output",
            text=text,
            context=context,
            checks=(
                _policy(
                    "raw_profile_field_output",
                    "block",
                    "Final output reveals raw profile or raw multimodal fields.",
                    (
                        r"\b(student_id|full_learning_history|long_term_student_profile)\b",
                        r"\b(student[_\s-]?id|full[_\s-]?learning[_\s-]?history|long[_\s-]?term[_\s-]?student[_\s-]?profile)\b",
                        r"\b(wrong_answer_image_path|audio_features|emotion_signals|handwriting_trace)\b",
                        r"\bdata/raw[/\\]",
                    ),
                ),
                _policy(
                    "copyrighted_original_output",
                    "block",
                    "Final output appears to reproduce original teacher resource text.",
                    (
                        r"\boriginal teacher question bank\b",
                        r"\bverbatim\b.*\bteacher\b.*\b(resource|question)\b",
                        r"\bexact literal text\b",
                    ),
                ),
            ),
        )

    def check_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Compatibility shim for CGController authorization hooks."""
        return self._check_message(message, domain_authorized=False)

    def check_authorized_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Trusted CG hook, called only after domain authorization and transforms.

        Never infer authorization from message/payload fields. This hook is an
        application-code boundary, not a user-controlled request option.
        """
        return self._check_message(message, domain_authorized=True)

    def _check_message(self, message: dict[str, Any], *, domain_authorized: bool) -> dict[str, Any]:
        result = self.check_agent_action(
            sender=str(message.get("sender", "")),
            receiver=str(message.get("receiver", "")),
            message_type=str(message.get("message_type", "")),
            payload=dict(message.get("payload") or {}),
            _domain_authorized=domain_authorized,
        )
        return {
            **result,
            "allowed": result["decision"] in {"allow", "sanitize", "rewrite"},
            "adapter": "NeMo Guardrails",
            "runtime_available": self.runtime_available,
            "config_path": self.config_path,
            "domain_policy_owner": "cogniguard" if domain_authorized else "unconfirmed",
        }

    def _check_text(
        self,
        rail_type: str,
        text: str,
        context: dict,
        checks: tuple[dict[str, Any], ...],
        skip_policy_ids: frozenset[str] = frozenset(),
    ) -> dict:
        original = str(text or "")
        if not self.enabled:
            return self._result(
                rail_type,
                "allow",
                "NeMo Guardrails adapter is disabled.",
                original,
                original,
                "disabled",
            )

        haystack = (
            f"{_normalize_attack_text(original)}\n{_normalize_attack_text(_json_preview(context))}"
        )
        for check in checks:
            if check["matched_policy"] in skip_policy_ids:
                continue
            if _matches_any(haystack, check["patterns"]):
                return self._result(
                    rail_type,
                    check["decision"],
                    check["reason"],
                    original,
                    "",
                    check["matched_policy"],
                )
        return self._result(
            rail_type,
            "allow",
            f"{rail_type.title()} rail passed.",
            original,
            original,
            "none",
        )

    def _result(
        self,
        rail_type: str,
        decision: str,
        reason: str,
        original: str,
        sanitized: str,
        matched_policy: str,
    ) -> dict:
        return {
            "enabled": self.enabled,
            "rail_type": rail_type,
            "decision": decision,
            "reason": reason,
            "original": original,
            "sanitized": sanitized,
            "matched_policy": matched_policy,
        }


def _policy(
    matched_policy: str,
    decision: str,
    reason: str,
    patterns: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "matched_policy": matched_policy,
        "decision": decision,
        "reason": reason,
        "patterns": patterns,
    }


def _find_forbidden_fields(value: Any) -> set[str]:
    found = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            canonical = _canonical_field_name(str(key))
            if canonical in FORBIDDEN_FIELD_NAMES:
                found.add(canonical)
            found.update(_find_forbidden_fields(nested))
    elif isinstance(value, list):
        for item in value:
            found.update(_find_forbidden_fields(item))
    return found


def _canonical_field_name(name: str) -> str:
    """Normalize camelCase and punctuation before field-boundary checks."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(name or ""))
    return re.sub(r"[^a-z0-9]+", "_", spaced.lower()).strip("_")


def _sanitize_prompt_injection(text: str) -> tuple[str, list[str]]:
    sanitized = text
    matched = []
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, sanitized, flags=re.IGNORECASE):
            matched.append(pattern)
            sanitized = re.sub(
                pattern,
                "[removed unsafe instruction]",
                sanitized,
                flags=re.IGNORECASE,
            )
    return sanitized, matched


def _quarantine_untrusted_instructions(text: str) -> tuple[str, list[str]]:
    sanitized = text
    matched: list[str] = []
    for pattern in UNTRUSTED_INSTRUCTION_PATTERNS:
        if re.search(pattern, sanitized):
            matched.append(pattern)
            sanitized = re.sub(
                pattern,
                "\n[quarantined untrusted instruction]",
                sanitized,
            )
    return sanitized, matched


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _json_preview(value: Any, max_chars: int = 1200) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        text = str(value)
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3]}..."


def _normalize_attack_text(text: str) -> str:
    """Normalize common obfuscations before deterministic policy matching.

    This is deliberately limited to compatibility/full-width and Latin/Cyrillic
    lookalikes used in jailbreak strings; it does not alter the user payload
    that is sent to the application.
    """
    normalized = unicodedata.normalize("NFKC", str(text or ""))
    return normalized.translate(
        str.maketrans(
            {
                "а": "a",
                "е": "e",
                "і": "i",
                "о": "o",
                "р": "p",
                "с": "c",
                "ѕ": "s",
                "х": "x",
                "А": "A",
                "Е": "E",
                "І": "I",
                "О": "O",
                "Р": "P",
                "С": "C",
                "Ѕ": "S",
                "Х": "X",
            }
        )
    )


def _nemo_guardrails_importable() -> bool:
    try:
        import nemoguardrails  # noqa: F401
    except Exception:
        return False
    return True
