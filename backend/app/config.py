from __future__ import annotations

"""
Central configuration: model registry, Modal GPU tiers, play styles, and defaults.

Models are split into two categories:
  - open_source: HuggingFace models deployed on Modal GPUs (enabled by default)
  - api:         Proprietary API models like GPT-4o, Claude (disabled until keys are configured)

The frontend uses short model aliases (baseLLM field). FRONTEND_MODEL_MAP translates
those to the canonical backend model keys used for inference.
"""

# ── GPU tiers available on Modal ────────────────────────────────────────────
MODAL_GPU_TIERS = {
    "T4":    {"vram_gb": 16,  "description": "Budget GPU, good for <=7B models"},
    "L4":    {"vram_gb": 24,  "description": "Mid-range, good for <=13B quantized"},
    "A10G":  {"vram_gb": 24,  "description": "Strong mid-range, good for <=13B models"},
    "A100":  {"vram_gb": 40,  "description": "High-end, required for 30B+ models"},
    "A100-80GB": {"vram_gb": 80, "description": "Top tier, required for 70B models"},
    "H100":  {"vram_gb": 80,  "description": "Fastest available, ideal for 70B+"},
}

# ── Play styles (matches frontend PLAY_STYLES exactly) ─────────────────────
PLAY_STYLES = {
    "tight-aggressive": {
        "label": "Tight-Aggressive (TAG)",
        "description": "Plays few hands, bets aggressively when in",
        "prompt_injection": (
            "You play a tight-aggressive style. Be selective with starting hands "
            "but bet and raise aggressively when you enter a pot. Fold weak holdings "
            "without hesitation."
        ),
        "traits": {"aggression": 0.8, "patience": 0.8, "bluff_frequency": 0.3},
    },
    "loose-aggressive": {
        "label": "Loose-Aggressive (LAG)",
        "description": "Plays many hands, applies constant pressure",
        "prompt_injection": (
            "You play a loose-aggressive style. Enter many pots and apply relentless "
            "pressure with bets and raises. Keep opponents guessing and off-balance."
        ),
        "traits": {"aggression": 0.9, "patience": 0.3, "bluff_frequency": 0.6},
    },
    "tight-passive": {
        "label": "Tight-Passive (Rock)",
        "description": "Plays few hands, rarely raises",
        "prompt_injection": (
            "You play a tight-passive style. Only enter pots with strong hands and "
            "prefer to check and call rather than bet or raise. Avoid confrontation "
            "unless you have a premium holding."
        ),
        "traits": {"aggression": 0.2, "patience": 0.9, "bluff_frequency": 0.1},
    },
    "loose-passive": {
        "label": "Loose-Passive (Calling Station)",
        "description": "Plays many hands, mostly calls",
        "prompt_injection": (
            "You play a loose-passive style. You like to see flops with many hands "
            "and mostly call rather than raise. You are curious about what the next "
            "card will bring."
        ),
        "traits": {"aggression": 0.2, "patience": 0.3, "bluff_frequency": 0.15},
    },
}

# ── Frontend model keys → backend canonical model key ──────────────────────
# The frontend sends these real model names in the baseLLM field.
# Each maps to itself (identity) so resolve_frontend_model() is a no-op,
# but the map is kept so VALID_FRONTEND_MODEL_KEYS stays in sync.
FRONTEND_MODEL_MAP = {
    "mistral-7b-instruct":   "mistral-7b-instruct",
    "llama-3.1-8b-instruct": "llama-3.1-8b-instruct",
    "devstral-small-24b":    "devstral-small-24b",
    "qwen3.5-27b":           "qwen3.5-27b",
}

# Frontend display metadata served by /api/models/selectable
FRONTEND_MODELS = [
    {"value": "mistral-7b-instruct",   "label": "Mistral 7B Instruct",   "description": "Fast & capable 7B model (Mistral AI) — Free",           "cost": 0},
    {"value": "llama-3.1-8b-instruct", "label": "Llama 3.1 8B Instruct", "description": "Compact instruct model with 128K context (Meta)",        "cost": 50},
    {"value": "devstral-small-24b",    "label": "Devstral Small 24B",    "description": "Agentic coding model with 256K context (Mistral)",       "cost": 100},
    {"value": "qwen3.5-27b",           "label": "Qwen 3.5 27B",          "description": "Latest 27B with native reasoning (Alibaba)",             "cost": 200},
]

# Internal-only model key for the house agent (not user-selectable).
# This is the GTO fine-tuned model that plays against users in every room.
HOUSE_AGENT_MODEL = "poker-qwen3-8b"

VALID_FRONTEND_MODEL_KEYS = set(FRONTEND_MODEL_MAP.keys())

# ── Model Registry ──────────────────────────────────────────────────────────
SUPPORTED_MODELS = {

    # ── House agent (internal only — NOT user-selectable) ──────────────────
    "poker-qwen3-8b": {
        "type": "open_source",
        "enabled": True,
        "internal": True,
        "provider": "huggingface",
        "hf_repo_id": "smitvasani/poker-qwen3-8b",
        "display_name": "Poker Qwen3 8B (House Agent)",
        "parameter_count": "8B",
        "recommended_gpu": "A100-40GB",
        "max_temperature": 1.0,
        "context_window": 4096,
        "description": "Qwen3-8B fine-tuned on PokerBench 560k GTO scenarios. Used as the house agent.",
    },

    # ── Open-source (HuggingFace) — DEFAULT ─────────────────────────────────
    "mistral-7b-instruct": {
        "type": "open_source",
        "enabled": True,
        "provider": "huggingface",
        "hf_repo_id": "mistralai/Mistral-7B-Instruct-v0.3",
        "display_name": "Mistral 7B Instruct",
        "parameter_count": "7B",
        "recommended_gpu": "A100-40GB",
        "max_temperature": 2.0,
        "context_window": 32768,
        "description": "Fast and capable 7B instruction-tuned model from Mistral AI.",
    },
    "llama-3.1-8b-instruct": {
        "type": "open_source",
        "enabled": True,
        "provider": "huggingface",
        "hf_repo_id": "meta-llama/Llama-3.1-8B-Instruct",
        "display_name": "Llama 3.1 8B Instruct",
        "parameter_count": "8B",
        "recommended_gpu": "A100-40GB",
        "max_temperature": 2.0,
        "context_window": 131072,
        "description": "Meta's compact instruct model with 128K context support.",
    },
    "qwen2.5-32b-instruct": {
        "type": "open_source",
        "enabled": True,
        "provider": "huggingface",
        "hf_repo_id": "Qwen/Qwen2.5-32B-Instruct",
        "display_name": "Qwen 2.5 32B Instruct",
        "parameter_count": "32.5B",
        "recommended_gpu": "A100-40GB",
        "max_temperature": 2.0,
        "context_window": 131072,
        "description": "Alibaba's large model with strong reasoning, coding, and multilingual support.",
    },
    "qwen3.5-27b": {
        "type": "open_source",
        "enabled": True,
        "provider": "huggingface",
        "hf_repo_id": "Qwen/Qwen3.5-27B",
        "display_name": "Qwen 3.5 27B",
        "parameter_count": "27B",
        "recommended_gpu": "A100-40GB",
        "max_temperature": 2.0,
        "context_window": 262144,
        "description": "Qwen's latest 27B model with native reasoning, tool calling, and 262K context.",
    },
    "llama-3.1-70b-instruct": {
        "type": "open_source",
        "enabled": True,
        "provider": "huggingface",
        "hf_repo_id": "meta-llama/Llama-3.1-70B-Instruct",
        "display_name": "Llama 3.1 70B Instruct",
        "parameter_count": "70B",
        "recommended_gpu": "A100-40GB",
        "max_temperature": 2.0,
        "context_window": 131072,
        "description": "Meta's flagship open-weight model. Requires high-end GPU.",
    },
    "llama-4-scout-17b-16e": {
        "type": "open_source",
        "enabled": True,
        "provider": "huggingface",
        "hf_repo_id": "meta-llama/Llama-4-Scout-17B-16E-Instruct",
        "display_name": "Llama 4 Scout 17B (MoE)",
        "parameter_count": "109B total / 17B active",
        "recommended_gpu": "A100-40GB",
        "max_temperature": 2.0,
        "context_window": 327680,
        "description": "Meta's MoE model — 16 experts, 17B active params, native multimodal. Needs high VRAM for full weights.",
    },
    "devstral-small-24b": {
        "type": "open_source",
        "enabled": True,
        "provider": "huggingface",
        "hf_repo_id": "mistralai/Devstral-Small-2-24B-Instruct-2512",
        "display_name": "Devstral Small 24B",
        "parameter_count": "24B",
        "recommended_gpu": "A100-40GB",
        "max_temperature": 2.0,
        "context_window": 262144,
        "description": "Mistral's agentic coding model with tool calling and 256K context. Runs on a single RTX 4090.",
    },

    # ── API models — DISABLED (enable when API keys are configured) ─────────
    "gpt-4o": {
        "type": "api",
        "enabled": False,
        "provider": "openai",
        "display_name": "GPT-4o",
        "max_temperature": 2.0,
        "context_window": 128000,
        "description": "OpenAI's flagship multimodal model.",
    },
    "gpt-4o-mini": {
        "type": "api",
        "enabled": False,
        "provider": "openai",
        "display_name": "GPT-4o Mini",
        "max_temperature": 2.0,
        "context_window": 128000,
        "description": "Lightweight, cost-effective OpenAI model.",
    },
    "claude-3.5-sonnet": {
        "type": "api",
        "enabled": False,
        "provider": "anthropic",
        "display_name": "Claude 3.5 Sonnet",
        "max_temperature": 1.0,
        "context_window": 200000,
        "description": "Anthropic's balanced intelligence model.",
    },
    "claude-3-haiku": {
        "type": "api",
        "enabled": False,
        "provider": "anthropic",
        "display_name": "Claude 3 Haiku",
        "max_temperature": 1.0,
        "context_window": 200000,
        "description": "Anthropic's fastest model.",
    },
    "gemini-1.5-pro": {
        "type": "api",
        "enabled": False,
        "provider": "google",
        "display_name": "Gemini 1.5 Pro",
        "max_temperature": 2.0,
        "context_window": 2000000,
        "description": "Google's advanced reasoning model.",
    },
}


def resolve_frontend_model(base_llm: str) -> str:
    """Resolve a frontend model alias to the canonical backend model key."""
    return FRONTEND_MODEL_MAP.get(base_llm, base_llm)


def get_enabled_models(model_type: str | None = None) -> dict:
    """Return only models that are currently enabled, optionally filtered by type."""
    return {
        k: v for k, v in SUPPORTED_MODELS.items()
        if v["enabled"] and (model_type is None or v["type"] == model_type)
    }


def get_all_models_by_type() -> dict:
    """Group all models by type with their enabled status."""
    result = {"open_source": {}, "api": {}}
    for key, m in SUPPORTED_MODELS.items():
        result[m["type"]][key] = m
    return result


# ── Defaults matching frontend DEFAULT_AGENT_VALUES ─────────────────────────
DEFAULTS = {
    "baseLLM": "mistral-7b-instruct",
    "riskTolerance": 50,
    "deception": 30,
    "personalityPrompt": "",
    "playStyle": "tight-aggressive",
    "previousGamesHistory": 0,
    "temperature": 0.7,
}

# Levels for previousGamesHistory:
#   0 — disabled (no Supermemory retrieval)
#   1 — minimal: 1 query, 2 results, brief context
#   2 — moderate: 2 queries, 4 results
#   3 — full: all queries (opponents, self-learnings, board), 10+ results
HISTORY_LEVELS = {
    0: {"label": "Disabled", "description": "No previous game history used"},
    1: {"label": "Minimal", "description": "Brief highlights from past games"},
    2: {"label": "Moderate", "description": "Key patterns and opponent notes from past games"},
    3: {"label": "Full", "description": "Comprehensive history including all opponent profiles and board analysis"},
}

# Credit costs per history level (must match frontend HISTORY_COSTS)
HISTORY_COSTS: dict[int, int] = {0: 0, 1: 25, 2: 75, 3: 150}


# ── Game constants matching frontend ────────────────────────────────────────
MAX_PLAYERS = 5
STARTING_CHIPS = 1000
SMALL_BLIND = 10
BIG_BLIND = 20
ROOM_CODE_LENGTH = 6


class Config:
    SECRET_KEY = "dev-secret-key"
    SUPPORTED_MODELS = SUPPORTED_MODELS
    MODAL_GPU_TIERS = MODAL_GPU_TIERS
    DEFAULTS = DEFAULTS
    PLAY_STYLES = PLAY_STYLES
