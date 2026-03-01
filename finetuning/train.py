"""
Fine-tune Qwen3-8B on PokerBench using Unsloth + LoRA on Modal.

Usage:
    python -m modal run finetuning/train.py                   # default config
    python -m modal run finetuning/train.py --num-epochs 3    # override
    python -m modal run finetuning/train.py --push-to-hub     # train + push

The script:
  1. Downloads PokerBench (preflop 60k + postflop 500k) from HuggingFace
  2. Formats every example as a chat conversation (system + user + assistant)
  3. Fine-tunes Qwen3-8B with 4-bit QLoRA via Unsloth's SFTTrainer
  4. Saves the LoRA adapter and optionally the merged full model
  5. Optionally pushes the merged model to HuggingFace Hub
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Optional

import modal

from config import (
    BASE_MODEL,
    BATCH_SIZE,
    EVAL_STEPS,
    GPU_TYPE,
    GRADIENT_ACCUMULATION_STEPS,
    HF_REPO_ID,
    LEARNING_RATE,
    LOGGING_STEPS,
    LORA_ALPHA,
    LORA_BIAS,
    LORA_DROPOUT,
    LORA_R,
    LORA_TARGET_MODULES,
    LR_SCHEDULER,
    MAX_RETRIES,
    MAX_SEQ_LENGTH,
    NUM_EPOCHS,
    OPTIMIZER,
    PACKING,
    SAVE_STEPS,
    SEED,
    SYSTEM_PROMPT,
    TIMEOUT_HOURS,
    USE_RSLORA,
    WARMUP_RATIO,
    WEIGHT_DECAY,
)

# ── Modal app ───────────────────────────────────────────────────────────────

app = modal.App("poker-finetune")

train_image = (
    modal.Image.debian_slim(python_version="3.11")
    .uv_pip_install(
        "accelerate==1.9.0",
        "datasets==3.6.0",
        "hf-transfer==0.1.9",
        "huggingface_hub==0.34.2",
        "peft==0.16.0",
        "transformers==4.54.0",
        "trl==0.19.1",
        "unsloth[cu128-torch270]==2025.7.8",
        "unsloth_zoo==2025.7.10",
    )
    .env({"HF_HOME": "/model_cache", "HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

with train_image.imports():
    import unsloth  # noqa: F401,I001 — must be first
    import datasets
    import torch
    from transformers import TrainingArguments
    from trl import SFTTrainer
    from unsloth import FastLanguageModel

model_cache = modal.Volume.from_name("poker-model-cache", create_if_missing=True)
dataset_cache = modal.Volume.from_name("poker-dataset-cache", create_if_missing=True)
checkpoint_vol = modal.Volume.from_name("poker-checkpoints", create_if_missing=True)

# ── Dataset formatting ──────────────────────────────────────────────────────

TEXT_COLUMN = "text"


def format_pokerbench_to_chat(examples, tokenizer):
    """Convert PokerBench instruction/output pairs into chat-formatted text."""
    texts = []
    for instruction, output in zip(examples["instruction"], examples["output"]):
        conversation = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": instruction},
            {"role": "assistant", "content": output},
        ]
        formatted = tokenizer.apply_chat_template(
            conversation, tokenize=False, add_generation_prompt=False
        )
        texts.append(formatted)
    return {TEXT_COLUMN: texts}


def load_pokerbench(tokenizer, cache_dir: pathlib.Path):
    """Load and format PokerBench dataset, with disk caching."""
    train_cache = cache_dir / "train"
    eval_cache = cache_dir / "eval"

    if train_cache.exists() and eval_cache.exists():
        print("Loading cached PokerBench dataset...")
        return (
            datasets.load_from_disk(str(train_cache)),
            datasets.load_from_disk(str(eval_cache)),
        )

    print("Downloading PokerBench from HuggingFace...")

    preflop = datasets.load_dataset(
        "RZ412/PokerBench",
        data_files="preflop_60k_train_set_prompt_and_label.json",
        split="train",
    )
    postflop = datasets.load_dataset(
        "RZ412/PokerBench",
        data_files="postflop_500k_train_set_prompt_and_label.json",
        split="train",
    )
    combined = datasets.concatenate_datasets([preflop, postflop])
    print(f"Total training examples: {len(combined):,}")

    combined = combined.shuffle(seed=SEED)
    split = combined.train_test_split(test_size=0.02, seed=SEED)
    train_ds = split["train"]
    eval_ds = split["test"]

    print("Formatting into chat template...")
    train_ds = train_ds.map(
        lambda ex: format_pokerbench_to_chat(ex, tokenizer),
        batched=True, num_proc=2,
        remove_columns=train_ds.column_names,
    )
    eval_ds = eval_ds.map(
        lambda ex: format_pokerbench_to_chat(ex, tokenizer),
        batched=True, num_proc=2,
        remove_columns=eval_ds.column_names,
    )

    cache_dir.mkdir(parents=True, exist_ok=True)
    train_ds.save_to_disk(str(train_cache))
    eval_ds.save_to_disk(str(eval_cache))
    dataset_cache.commit()

    print(f"Train: {len(train_ds):,}  Eval: {len(eval_ds):,}")
    return train_ds, eval_ds


# ── Training function (runs on Modal GPU) ───────────────────────────────────

@app.function(
    image=train_image,
    gpu=GPU_TYPE,
    volumes={
        "/model_cache": model_cache,
        "/dataset_cache": dataset_cache,
        "/checkpoints": checkpoint_vol,
    },
    secrets=[modal.Secret.from_name("huggingface-secret")],
    timeout=TIMEOUT_HOURS * 60 * 60,
    retries=modal.Retries(initial_delay=0.0, max_retries=MAX_RETRIES),
    single_use_containers=True,
)
def finetune(
    num_epochs: int = NUM_EPOCHS,
    push_to_hub: bool = False,
    hf_repo_id: str = HF_REPO_ID,
):
    import os

    ckpt_dir = pathlib.Path("/checkpoints/poker-qwen3-8b")
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    ds_cache = pathlib.Path("/dataset_cache/pokerbench")

    # Load model
    print(f"Loading {BASE_MODEL}...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=True,
    )

    # Apply LoRA
    print(f"Applying LoRA (r={LORA_R}, alpha={LORA_ALPHA})...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=LORA_R,
        target_modules=LORA_TARGET_MODULES,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        bias=LORA_BIAS,
        use_gradient_checkpointing="unsloth",
        random_state=SEED,
        use_rslora=USE_RSLORA,
    )

    # Load dataset
    train_ds, eval_ds = load_pokerbench(tokenizer, ds_cache)

    # Check for existing checkpoint
    resume_from = None
    existing = list(ckpt_dir.glob("checkpoint-*"))
    if existing:
        resume_from = str(max(existing, key=lambda p: int(p.name.split("-")[1])))
        print(f"Resuming from {resume_from}")

    # Training args
    training_args = TrainingArguments(
        output_dir=str(ckpt_dir),
        num_train_epochs=num_epochs,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,
        learning_rate=LEARNING_RATE,
        lr_scheduler_type=LR_SCHEDULER,
        warmup_ratio=WARMUP_RATIO,
        weight_decay=WEIGHT_DECAY,
        optim=OPTIMIZER,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=LOGGING_STEPS,
        save_steps=SAVE_STEPS,
        eval_strategy="steps",
        eval_steps=EVAL_STEPS,
        save_strategy="steps",
        save_total_limit=3,
        seed=SEED,
        report_to="none",
    )

    # Train
    total_params = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Total params: {total_params:,}  Trainable: {trainable:,} ({trainable/total_params*100:.2f}%)")
    print(f"Train: {len(train_ds):,}  Eval: {len(eval_ds):,}")
    print(f"Effective batch: {BATCH_SIZE * GRADIENT_ACCUMULATION_STEPS}")
    print(f"Epochs: {num_epochs}")

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        dataset_text_field=TEXT_COLUMN,
        max_seq_length=MAX_SEQ_LENGTH,
        dataset_num_proc=2,
        packing=PACKING,
        args=training_args,
    )

    if resume_from:
        trainer.train(resume_from_checkpoint=resume_from)
    else:
        print("Starting training...")
        trainer.train()

    # Save LoRA adapter
    lora_dir = ckpt_dir / "lora_adapter"
    print(f"Saving LoRA adapter to {lora_dir}...")
    model.save_pretrained(lora_dir)
    tokenizer.save_pretrained(lora_dir)
    checkpoint_vol.commit()

    # Merge and save full model (16-bit)
    merged_dir = ckpt_dir / "merged_model"
    print(f"Merging LoRA into base model → {merged_dir}...")
    model.save_pretrained_merged(
        str(merged_dir), tokenizer, save_method="merged_16bit"
    )
    checkpoint_vol.commit()

    # Push to HuggingFace Hub
    if push_to_hub:
        hf_token = os.environ.get("HF_TOKEN", "")
        if not hf_token:
            print("WARNING: HF_TOKEN not set, skipping push. Add it to 'huggingface-secret' in Modal.")
        else:
            print(f"Pushing merged model to {hf_repo_id}...")
            model.push_to_hub_merged(
                hf_repo_id, tokenizer,
                save_method="merged_16bit",
                token=hf_token,
            )
            print(f"Model published at https://huggingface.co/{hf_repo_id}")

    print("Training complete!")
    return str(merged_dir)


# ── CLI entrypoint ──────────────────────────────────────────────────────────

@app.local_entrypoint()
def main(
    num_epochs: int = NUM_EPOCHS,
    push_to_hub: bool = False,
    hf_repo_id: str = HF_REPO_ID,
):
    print("=" * 60)
    print("  Poker LLM Fine-tuning on Modal")
    print("=" * 60)
    print(f"  Base model:  {BASE_MODEL}")
    print(f"  Dataset:     PokerBench (560k examples)")
    print(f"  LoRA:        r={LORA_R}, alpha={LORA_ALPHA}")
    print(f"  Epochs:      {num_epochs}")
    print(f"  GPU:         {GPU_TYPE}")
    print(f"  Push to HF:  {push_to_hub} → {hf_repo_id}")
    print("=" * 60)

    result = finetune.remote(
        num_epochs=num_epochs,
        push_to_hub=push_to_hub,
        hf_repo_id=hf_repo_id,
    )
    print(f"\nDone! Model saved at: {result}")
