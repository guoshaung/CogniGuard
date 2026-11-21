"""Frozen decision constants. Do not retune after seeing stage-1 outcomes."""

B_STAR = 4.0
MU_ADVERSARIAL = 4.0
EPSILON_R = 0.18  # paper Appendix D.1 mean calibration margin, bits
N_STUDENTS = 20
TURNS_MIN = 8
TURNS_MAX = 12
TURNS_TARGET = 10
BOOTSTRAP_N = 5000
BOOTSTRAP_SEED = 20261121
# G3: prompt-arm recall of pedagogy atoms labeled NONE.
G3_RECALL_LOWER = 0.50
# If the model attacker lags the view oracle by more than this, the
# hypothesis is "无法判定" rather than "不支持".
ATTACKER_GAP = 0.15
BUDGET_RMB = 100.0
# Beijing list price, input <= 128k. qwen3.5-flash, 2026-11-21 Aliyun doc.
QWEN_FLASH_PRICE = {"in": 0.2, "out": 2.0}
# deepseek-flash peak (cache miss). Conservative gate. Official doc 2026-11-20.
DEEPSEEK_PEAK_PRICE = {"in": 2.0, "out": 8.0}
OPS = ("identity", "generalize", "substitute", "redact", "drop")
