"""
Evaluate the fine-tuned poker model on PokerBench test sets.

Runs inference on the 1k preflop + 10k postflop test sets and reports
accuracy (exact match on the optimal action).

Usage:
    python -m modal run finetuning/eval.py
    python -m modal run finetuning/eval.py --model-path /checkpoints/poker-qwen3-8b/merged_model
    python -m modal run finetuning/eval.py --hf-model smitvasani/poker-qwen3-8b
"""
from __future__ import annotations

import modal

from config import BASE_MODEL, HF_REPO_ID, MAX_SEQ_LENGTH, SEED, SYSTEM_PROMPT

app = modal.App("poker-eval")

eval_image = (
    modal.Image.debian_slim(python_version="3.11")
    .uv_pip_install(
        "accelerate==1.9.0",
        "datasets==3.6.0",
        "hf-transfer==0.1.9",
        "huggingface_hub==0.34.2",
        "peft==0.16.0",
        "transformers==4.54.0",
        "unsloth[cu128-torch270]==2025.7.8",
        "unsloth_zoo==2025.7.10",
    )
    .env({"HF_HOME": "/model_cache", "HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

with eval_image.imports():
    import unsloth  # noqa: F401,I001
    import datasets
    from unsloth import FastLanguageModel

model_cache = modal.Volume.from_name("poker-model-cache", create_if_missing=True)
checkpoint_vol = modal.Volume.from_name("poker-checkpoints", create_if_missing=True)


def normalize_action(text: str) -> str:
    """Normalize an action string for comparison."""
    text = text.strip().lower()
    for prefix in ("action:", "decision:", "optimal action:", "answer:"):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    if text.startswith("bet") or text.startswith("raise"):
        return text.split()[0]
    return text


@app.function(
    image=eval_image,
    gpu="A10G",
    volumes={
        "/model_cache": model_cache,
        "/checkpoints": checkpoint_vol,
    },
    secrets=[modal.Secret.from_name("huggingface-secret")],
    timeout=2 * 60 * 60,
)
def evaluate(
    hf_model: str = "",
    model_path: str = "",
    max_samples: int = 0,
):
    import json
    import pathlib

    # Determine model source
    if hf_model:
        source = hf_model
    elif model_path:
        source = model_path
    else:
        local = pathlib.Path("/checkpoints/poker-qwen3-8b/merged_model")
        if local.exists():
            source = str(local)
        else:
            source = HF_REPO_ID

    print(f"Loading model: {source}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=source,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=True,
    )
    FastLanguageModel.for_inference(model)

    # Load test sets
    print("Loading PokerBench test sets...")
    preflop_test = datasets.load_dataset(
        "RZ412/PokerBench",
        data_files="preflop_1k_test_set_prompt_and_label.json",
        split="train",
    )
    postflop_test = datasets.load_dataset(
        "RZ412/PokerBench",
        data_files="postflop_10k_test_set_prompt_and_label.json",
        split="train",
    )

    results = {}
    for name, test_ds in [("preflop", preflop_test), ("postflop", postflop_test)]:
        if max_samples > 0:
            test_ds = test_ds.shuffle(seed=SEED).select(range(min(max_samples, len(test_ds))))

        print(f"\nEvaluating {name}: {len(test_ds)} examples...")
        correct = 0
        total = 0
        errors = []

        for i, example in enumerate(test_ds):
            instruction = example["instruction"]
            expected = normalize_action(example["output"])

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": instruction},
            ]
            input_text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            inputs = tokenizer(input_text, return_tensors="pt").to(model.device)

            with __import__("torch").no_grad():
                output_ids = model.generate(
                    **inputs,
                    max_new_tokens=64,
                    temperature=0.0,
                    do_sample=False,
                )

            generated = tokenizer.decode(
                output_ids[0][inputs["input_ids"].shape[1]:],
                skip_special_tokens=True,
            )
            predicted = normalize_action(generated)

            if predicted == expected or expected in predicted:
                correct += 1
            else:
                if len(errors) < 10:
                    errors.append({
                        "idx": i,
                        "expected": expected,
                        "predicted": predicted,
                        "raw": generated[:100],
                    })

            total += 1
            if total % 200 == 0:
                print(f"  {total}/{len(test_ds)} — accuracy so far: {correct/total*100:.1f}%")

        accuracy = correct / total * 100 if total > 0 else 0
        results[name] = {
            "total": total,
            "correct": correct,
            "accuracy": round(accuracy, 2),
            "sample_errors": errors,
        }
        print(f"  {name} accuracy: {accuracy:.1f}% ({correct}/{total})")

    # Combined
    total_all = sum(r["total"] for r in results.values())
    correct_all = sum(r["correct"] for r in results.values())
    overall = correct_all / total_all * 100 if total_all > 0 else 0

    print(f"\n{'='*50}")
    print(f"  OVERALL: {overall:.1f}% ({correct_all}/{total_all})")
    print(f"  Preflop: {results['preflop']['accuracy']}%")
    print(f"  Postflop: {results['postflop']['accuracy']}%")
    print(f"{'='*50}")

    return results


@app.local_entrypoint()
def main(
    hf_model: str = "",
    model_path: str = "",
    max_samples: int = 0,
):
    print("Running PokerBench evaluation...")
    results = evaluate.remote(
        hf_model=hf_model,
        model_path=model_path,
        max_samples=max_samples,
    )
    print("\nFinal results:")
    for name, data in results.items():
        print(f"  {name}: {data['accuracy']}% ({data['correct']}/{data['total']})")
