# Poker LLM Fine-tuning

Fine-tune **Qwen3-8B** on the [PokerBench](https://huggingface.co/datasets/RZ412/PokerBench) dataset (560k GTO poker scenarios) using **Modal AI** GPU infrastructure, then publish to HuggingFace and use it in the poker arena.

## Dataset

[PokerBench](https://huggingface.co/datasets/RZ412/PokerBench) (AAAI 2025) contains:

| Split | Examples | Description |
|-------|----------|-------------|
| Preflop train | 60,000 | Pre-flop decision scenarios |
| Postflop train | 500,000 | Post-flop decision scenarios (flop/turn/river) |
| Preflop test | 1,000 | Evaluation set |
| Postflop test | 10,000 | Evaluation set |

Each example has an `instruction` (natural language game scenario) and `output` (GTO-optimal action computed by poker solvers).

## Setup

```bash
# Install Modal
pip install modal

# Authenticate with Modal
python -m modal setup

# Create the HuggingFace secret (for pushing models)
modal secret create huggingface-secret HF_TOKEN=hf_your_token_here
```

## Train

```bash
# Default: 2 epochs, Qwen3-8B, LoRA r=32, A100 GPU
python -m modal run finetuning/train.py

# Custom epochs
python -m modal run finetuning/train.py --num-epochs 3

# Train and push to HuggingFace in one go
python -m modal run finetuning/train.py --push-to-hub

# Custom HF repo
python -m modal run finetuning/train.py --push-to-hub --hf-repo-id yourname/poker-qwen3
```

Training takes ~2-3 hours on a single A100 GPU.

## Evaluate

```bash
# Evaluate the trained model on PokerBench test sets
python -m modal run finetuning/eval.py

# Evaluate a specific HuggingFace model
python -m modal run finetuning/eval.py --hf-model smitvasani/poker-qwen3-8b

# Quick eval with limited samples
python -m modal run finetuning/eval.py --max-samples 100
```

## Publish to HuggingFace

```bash
# Push merged 16-bit model
python -m modal run finetuning/push_to_hub.py

# Push only the LoRA adapter (smaller)
python -m modal run finetuning/push_to_hub.py --lora-only

# Custom repo name
python -m modal run finetuning/push_to_hub.py --hf-repo-id yourname/poker-qwen3
```

This also creates a GGUF Q4_K_M quantized version for local testing.

## Use in the Poker Arena

Once published, the model is already configured in the backend at `backend/app/config.py`:
- Backend model key: `poker-qwen3-8b`
- Frontend model alias: `poker-qwen3-8b` → "Poker Qwen3 8B"
- Listed first in the model picker as the recommended option

## Architecture

```
finetuning/
├── config.py          # All hyperparameters and paths
├── train.py           # Modal training script (Unsloth + LoRA + SFTTrainer)
├── eval.py            # Accuracy evaluation on PokerBench test sets
├── push_to_hub.py     # Publish to HuggingFace (merged + GGUF)
└── README.md
```

## Training Details

| Parameter | Value |
|-----------|-------|
| Base model | Qwen3-8B (4-bit quantized via Unsloth) |
| Method | QLoRA (rank 32, alpha 32) |
| Target modules | All attention + MLP projections |
| Optimizer | AdamW 8-bit |
| Learning rate | 2e-4 (cosine schedule) |
| Batch size | 8 x 4 gradient accumulation = 32 effective |
| Epochs | 2 |
| GPU | A100 40GB (Modal) |
| Sequence packing | Enabled |
| Training data | 560k examples (preflop + postflop combined) |

## Cost Estimate

On Modal with A100 GPUs:
- ~2-3 hours training time
- ~$6-10 per training run
- Eval runs ~30 min ($1-2)
