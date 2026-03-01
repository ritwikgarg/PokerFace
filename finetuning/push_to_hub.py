"""
Push the fine-tuned poker model from Modal volume to HuggingFace Hub.

Use this if you trained with --push-to-hub=false and want to push later,
or to push the LoRA adapter separately.

Usage:
    python -m modal run finetuning/push_to_hub.py
    python -m modal run finetuning/push_to_hub.py --lora-only
    python -m modal run finetuning/push_to_hub.py --hf-repo-id yourname/poker-model
"""
from __future__ import annotations

import modal

from config import BASE_MODEL, HF_REPO_ID, MAX_SEQ_LENGTH

app = modal.App("poker-push-hub")

push_image = (
    modal.Image.debian_slim(python_version="3.11")
    .uv_pip_install(
        "accelerate==1.9.0",
        "hf-transfer==0.1.9",
        "huggingface_hub==0.34.2",
        "peft==0.16.0",
        "transformers==4.54.0",
        "unsloth[cu128-torch270]==2025.7.8",
        "unsloth_zoo==2025.7.10",
    )
    .env({"HF_HOME": "/model_cache", "HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

with push_image.imports():
    import unsloth  # noqa: F401,I001
    from unsloth import FastLanguageModel

model_cache = modal.Volume.from_name("poker-model-cache", create_if_missing=True)
checkpoint_vol = modal.Volume.from_name("poker-checkpoints", create_if_missing=True)


@app.function(
    image=push_image,
    gpu="T4",
    volumes={
        "/model_cache": model_cache,
        "/checkpoints": checkpoint_vol,
    },
    secrets=[modal.Secret.from_name("huggingface-secret")],
    timeout=60 * 60,
)
def push(hf_repo_id: str = HF_REPO_ID, lora_only: bool = False):
    import os
    import pathlib

    hf_token = os.environ.get("HF_TOKEN", "")
    if not hf_token:
        raise RuntimeError(
            "HF_TOKEN not found. Add it to Modal secret 'huggingface-secret'.\n"
            "  modal secret create huggingface-secret HF_TOKEN=hf_xxx"
        )

    lora_dir = pathlib.Path("/checkpoints/poker-qwen3-8b/lora_adapter")
    if not lora_dir.exists():
        raise FileNotFoundError(
            f"LoRA adapter not found at {lora_dir}. Run train.py first."
        )

    print(f"Loading LoRA adapter from {lora_dir}...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(lora_dir),
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=True,
    )

    if lora_only:
        repo = hf_repo_id + "-lora"
        print(f"Pushing LoRA adapter to {repo}...")
        model.push_to_hub(repo, token=hf_token)
        tokenizer.push_to_hub(repo, token=hf_token)
        print(f"LoRA adapter published: https://huggingface.co/{repo}")
    else:
        print(f"Merging and pushing full model to {hf_repo_id}...")
        model.push_to_hub_merged(
            hf_repo_id, tokenizer,
            save_method="merged_16bit",
            token=hf_token,
        )
        print(f"Full model published: https://huggingface.co/{hf_repo_id}")

    # Also push GGUF quantized version for easy local testing
    gguf_repo = hf_repo_id + "-GGUF"
    print(f"Pushing GGUF Q4_K_M to {gguf_repo}...")
    try:
        model.push_to_hub_gguf(
            gguf_repo, tokenizer,
            quantization_method="q4_k_m",
            token=hf_token,
        )
        print(f"GGUF published: https://huggingface.co/{gguf_repo}")
    except Exception as e:
        print(f"GGUF push failed (non-critical): {e}")

    return hf_repo_id


@app.local_entrypoint()
def main(
    hf_repo_id: str = HF_REPO_ID,
    lora_only: bool = False,
):
    print(f"Pushing model to HuggingFace: {hf_repo_id}")
    result = push.remote(hf_repo_id=hf_repo_id, lora_only=lora_only)
    print(f"Done! → https://huggingface.co/{result}")
