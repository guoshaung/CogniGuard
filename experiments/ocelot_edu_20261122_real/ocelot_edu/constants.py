"""Frozen before the stage-1b run. Do not retune after seeing outcomes."""

B_STAR = 4.0
MU_ADVERSARIAL = 4.0
EPSILON_R = 0.18
N_STUDENTS = 20
TURNS = 10
BOOTSTRAP_N = 5000
BOOTSTRAP_SEED = 20261122
G3_RECALL_LOWER = 0.50
ATTACKER_GAP = 0.15
BUDGET_RMB = 100.0
# deepseek-flash peak, cache miss. Frozen 2026-11-22. Local Ollama calls cost 0.
DEEPSEEK_PEAK_PRICE = {"in": 2.0, "out": 8.0}
# Smoke extrapolates one paid call to this many attacker calls
# (5 arms x 5 packs x 4 coalitions x 3 samples).
ATTACK_EXTRAPOLATION_CALLS = 300
SAMPLES_PER_MODEL = 4
PROXY_MODELS = ("qwen2.5:7b", "llama3.1:8b")
DEFENDER_MODEL = "qwen2.5:7b-instruct"
SCORER_MODEL = "llama3.1:8b"
PROXY_TEMPERATURE = 0.7
PROXY_NUM_PREDICT = 768
DEFENDER_NUM_PREDICT = 512
SCORER_NUM_PREDICT = 128
ATTACKER_NUM_PREDICT = 900
MIN_QUOTE_CHARS = 4
OPS = ("identity", "generalize", "substitute", "redact", "drop")
MAIN_ARMS = ("ocelot_minus", "prompt")
DIAGNOSTIC_ARM = "cost_model_identity"
CONTROL_ARMS = ("none", "nemo")
ALL_ARMS = CONTROL_ARMS + MAIN_ARMS + (DIAGNOSTIC_ARM,)
LAYER_OF_TYPE = {
    "distinctive_expression": "表达",
    "diagnosis_to_feedback_mapping": "诊断映射",
    "ordered_private_sequence": "顺序",
}
# Observed on this machine before the run. The two tags are one blob.
QWEN_TAG_ID = "845dbda0ea48"
QWEN_BLOB = "sha256:2bada8a7450677000f678be90653b85d364de7db25eb5ea54136ada5f3933730"
ASSET_SHA256 = {
    "README.md": "d857c826e782260a6ce0b8d75cc05a31a2d37fc6c8ad8d47644389bace4a9413",
    "pedagogical_assets_v1.jsonl": "aff7100f3a0e421568c4ece00743a40be75fe533a4bc1dcec1734b6cb5320ce1",
    "public_only_baseline_v1.jsonl": "44c6c61ef7e82520670ea1e496a2b1247ea010af278113c8208fbc8b1cbc3344",
    "seed_queries_v1.jsonl": "0668247926e9791e026cc1a7aa9eee1e00e32ee4350d584f9e202301da4186b8",
    "sanity_checks.json": "c4e7813991f5ae1e788e7fc266e456b06e6edfeb8977612fcdc3dd42b8e20bba",
    "validate_assets.py": "faed511e8f802f6577539245ce89c4476ae455ad062919811a74d583b730e3b3",
    "RUN_PROMPT_DEEPSEEK.md": "ab4bbad7f5ef259d7fb444390e17cae4202d6696e5f811ff3992e0443fa5dc76",
}
# Pinned so this round cannot silently edit the frozen round-1 protocol.
ROUND1_PROTOCOL_SHA256 = "ee85ec5341d534490f9209632a4eee543223e9ecfc3f274c0797a53779a47da2"
