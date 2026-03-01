from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.config import (
    SUPPORTED_MODELS,
    MODAL_GPU_TIERS,
    DEFAULTS,
    PLAY_STYLES,
    FRONTEND_MODELS,
    FRONTEND_MODEL_MAP,
    HISTORY_COSTS,
    get_enabled_models,
    get_all_models_by_type,
)
from app.presets.personalities import list_personalities
from app.presets.prompts import list_templates

models_bp = Blueprint("models", __name__)


def _serialize_model(key: str, m: dict) -> dict:
    base = {
        "key": key,
        "type": m["type"],
        "enabled": m["enabled"],
        "provider": m["provider"],
        "display_name": m["display_name"],
        "max_temperature": m["max_temperature"],
        "context_window": m["context_window"],
        "description": m["description"],
    }
    if m["type"] == "open_source":
        base["hf_repo_id"] = m["hf_repo_id"]
        base["parameter_count"] = m["parameter_count"]
        base["recommended_gpu"] = m["recommended_gpu"]
    return base


@models_bp.route("/models", methods=["GET"])
def get_models():
    """List backend models. For frontend model picker use /models/frontend."""
    model_type = request.args.get("type")
    enabled_only = request.args.get("enabled_only", "true").lower() == "true"

    if enabled_only:
        source = get_enabled_models(model_type)
    elif model_type:
        source = {k: v for k, v in SUPPORTED_MODELS.items() if v["type"] == model_type}
    else:
        source = SUPPORTED_MODELS

    models = [_serialize_model(k, v) for k, v in source.items()]

    return jsonify({
        "models": models,
        "default": DEFAULTS["baseLLM"],
        "total": len(models),
    })


@models_bp.route("/models/frontend", methods=["GET"])
def get_frontend_models():
    """Return the model list matching the frontend LLM_MODELS constant.

    Response shape matches frontend constants.ts LLM_MODELS:
        [{ value, label, description, resolvedBackendModel }]
    """
    enriched = []
    for m in FRONTEND_MODELS:
        enriched.append({
            **m,
            "resolvedBackendModel": FRONTEND_MODEL_MAP.get(m["value"], m["value"]),
        })
    return jsonify({"models": enriched, "default": DEFAULTS["baseLLM"]})


@models_bp.route("/models/selectable", methods=["GET"])
def get_selectable_models():
    """Return the selectable models with their credit costs and history costs.

    This is the single source of truth for the frontend agent form.
    Response:
        {
            models: [{ value, label, description, cost }],
            historyCosts: { "0": 0, "1": 25, ... },
            defaultModel: "mistral-7b-instruct",
            defaultHistory: 0
        }
    """
    return jsonify({
        "models": FRONTEND_MODELS,
        "historyCosts": {str(k): v for k, v in HISTORY_COSTS.items()},
        "defaultModel": DEFAULTS["baseLLM"],
        "defaultHistory": 0,
    })


@models_bp.route("/models/grouped", methods=["GET"])
def get_models_grouped():
    """All backend models grouped by type."""
    grouped = get_all_models_by_type()
    result = {}
    for mtype, model_dict in grouped.items():
        result[mtype] = {
            "models": [_serialize_model(k, v) for k, v in model_dict.items()],
            "enabled_count": sum(1 for v in model_dict.values() if v["enabled"]),
            "total_count": len(model_dict),
        }
    return jsonify(result)


@models_bp.route("/models/gpu-tiers", methods=["GET"])
def get_gpu_tiers():
    """List Modal GPU tiers and their specs."""
    tiers = [
        {"name": name, **spec}
        for name, spec in MODAL_GPU_TIERS.items()
    ]
    return jsonify({"gpu_tiers": tiers})


@models_bp.route("/play-styles", methods=["GET"])
def get_play_styles():
    """Return play styles matching frontend PLAY_STYLES constant."""
    styles = [
        {"value": key, "label": data["label"], "description": data["description"]}
        for key, data in PLAY_STYLES.items()
    ]
    return jsonify({"playStyles": styles})


@models_bp.route("/presets/personalities", methods=["GET"])
def get_personalities():
    return jsonify({"personalities": list_personalities()})


@models_bp.route("/presets/prompts", methods=["GET"])
def get_prompt_templates():
    return jsonify({"templates": list_templates()})


@models_bp.route("/defaults", methods=["GET"])
def get_defaults():
    return jsonify(DEFAULTS)
