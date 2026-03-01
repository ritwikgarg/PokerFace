"""
Training configuration for poker LLM fine-tuning.

All hyperparameters and paths are defined here so the training script,
eval script, and push script can share them.
"""

# ── Model ───────────────────────────────────────────────────────────────────
BASE_MODEL = "unsloth/Qwen3-8B"           # 4-bit quantized by Unsloth for fast LoRA
BASE_MODEL_FULL = "Qwen/Qwen3-8B"         # full-precision name (for model card)
MAX_SEQ_LENGTH = 4096                      # PokerBench prompts are ~500-1500 tokens

# ── Dataset ─────────────────────────────────────────────────────────────────
DATASET_HF = "RZ412/PokerBench"
PREFLOP_TRAIN_JSON = "preflop_60k_train_set_prompt_and_label.json"
POSTFLOP_TRAIN_JSON = "postflop_500k_train_set_prompt_and_label.json"
PREFLOP_TEST_JSON = "preflop_1k_test_set_prompt_and_label.json"
POSTFLOP_TEST_JSON = "postflop_10k_test_set_prompt_and_label.json"

# ── LoRA ────────────────────────────────────────────────────────────────────
LORA_R = 32
LORA_ALPHA = 32
LORA_DROPOUT = 0.0
LORA_BIAS = "none"
USE_RSLORA = False
LORA_TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj",
]

# ── Training ────────────────────────────────────────────────────────────────
LEARNING_RATE = 2e-4
LR_SCHEDULER = "cosine"
WARMUP_RATIO = 0.05
WEIGHT_DECAY = 0.01
NUM_EPOCHS = 2
BATCH_SIZE = 8
GRADIENT_ACCUMULATION_STEPS = 4          # effective batch = 32
LOGGING_STEPS = 25
SAVE_STEPS = 500
EVAL_STEPS = 500
OPTIMIZER = "adamw_8bit"
PACKING = True                           # pack short sequences for efficiency

# ── GPU (Modal) ─────────────────────────────────────────────────────────────
GPU_TYPE = "A100"                        # 40 GB; fits Qwen3-8B 4-bit + LoRA comfortably
TIMEOUT_HOURS = 4
MAX_RETRIES = 2

# ── Output ──────────────────────────────────────────────────────────────────
HF_REPO_ID = "smitvasani/poker-qwen3-8b"  # ← change to your HF username/repo
MERGED_MODEL_NAME = "poker-qwen3-8b"
SEED = 42

# ── System prompt prepended to every PokerBench instruction ─────────────────
SYSTEM_PROMPT = (
    "You are an expert poker AI trained on Game Theory Optimal (GTO) strategy "
    "for 6-handed No Limit Texas Hold'em. Analyze the game scenario and "
    "respond with ONLY the optimal action. Valid actions: fold, check, call, "
    "or a specific bet/raise amount."
)
